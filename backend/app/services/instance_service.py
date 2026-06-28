import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.instance import Instance
from app.models.template import Template
from app.services import qemu_manager
from app.services.network_setup import bridge_exists

logger = logging.getLogger(__name__)

RUNNING_STATUSES = {"STARTING", "RUNNING", "STOPPING"}


def instance_to_out(instance: Instance) -> dict:
    template = instance.template
    return {
        "id": instance.id,
        "name": instance.name,
        "template_id": instance.template_id,
        "status": instance.status,
        "tap_name": instance.tap_name,
        "guest_ssh_host": instance.guest_ssh_host or (template.guest_ssh_host if template else None),
        "guest_ssh_port": template.guest_ssh_port if template else 22,
        "pid": instance.pid,
        "created_at": instance.created_at,
    }


async def list_instances(session: AsyncSession, page: int, limit: int) -> tuple[int, list[Instance]]:
    total = await session.scalar(select(func.count()).select_from(Instance))
    result = await session.execute(
        select(Instance)
        .options(selectinload(Instance.template))
        .order_by(Instance.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    instances = list(result.scalars().all())
    
    # 校验并同步列表中实例的实际状态
    dirty = False
    for inst in instances:
        if inst.status in RUNNING_STATUSES:
            if not inst.pid or not qemu_manager.is_pid_alive(inst.pid):
                logger.warning(f"检测到实例 {inst.id} 进程 {inst.pid} 已关闭，正在自动清理并更新状态...")
                await qemu_manager.cleanup_instance_resources(inst)
                inst.status = "STOPPED"
                inst.pid = None
                inst.tap_name = None
                inst.updated_at = datetime.utcnow()
                dirty = True
    if dirty:
        await session.commit()

    return total or 0, instances


async def get_instance(session: AsyncSession, instance_id: str) -> Instance:
    result = await session.execute(
        select(Instance)
        .options(selectinload(Instance.template))
        .where(Instance.id == instance_id)
    )
    instance = result.scalar_one_or_none()
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "INSTANCE_NOT_FOUND", "message": "Instance not found"},
        )

    # 校验并同步当前查询实例的实际状态
    if instance.status in RUNNING_STATUSES:
        if not instance.pid or not qemu_manager.is_pid_alive(instance.pid):
            logger.warning(f"检测到实例 {instance.id} 进程 {instance.pid} 已关闭，正在自动清理并更新状态...")
            await qemu_manager.cleanup_instance_resources(instance)
            instance.status = "STOPPED"
            instance.pid = None
            instance.tap_name = None
            instance.updated_at = datetime.utcnow()
            await session.commit()

    return instance


import tarfile
import zipfile
import shutil

def extract_archive(archive_path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = archive_path.suffix.lower()
    name = archive_path.name.lower()
    
    if name.endswith(".tar.gz") or name.endswith(".tgz"):
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(path=dest_dir)
    elif name.endswith(".tar.xz"):
        with tarfile.open(archive_path, "r:xz") as tar:
            tar.extractall(path=dest_dir)
    elif name.endswith(".tar.bz2"):
        with tarfile.open(archive_path, "r:bz2") as tar:
            tar.extractall(path=dest_dir)
    elif suffix == ".tar":
        with tarfile.open(archive_path, "r:") as tar:
            tar.extractall(path=dest_dir)
    elif suffix == ".zip":
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            zip_ref.extractall(dest_dir)
    elif name.endswith(".img.gz") or suffix == ".gz":
        import gzip
        import subprocess
        # 1. 解压 gz 得到临时的 raw img 文件
        temp_img = dest_dir.parent / f"temp_{archive_path.stem}"
        with gzip.open(archive_path, "rb") as f_in:
            with open(temp_img, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # 2. 调用 debugfs 在用户空间免挂载递归提取 ext4 分区内容到 dest_dir
        cmd = ["debugfs", "-R", f"rdump / {dest_dir}", str(temp_img)]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"debugfs rdump failed: {e.stderr}")
            raise RuntimeError(f"debugfs rdump 提取失败: {e.stderr}")
        finally:
            if temp_img.exists():
                temp_img.unlink()
    else:
        raise ValueError(f"不支持的根文件系统压缩包格式: {archive_path.name}")


async def create_instance(
    session: AsyncSession,
    name: str,
    template_id: int,
    rootfs_path: str | None = None,
) -> Instance:
    template = await session.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    settings = get_settings()
    settings.ensure_dirs()
    instance_id = f"inst_{uuid.uuid4()}"
    inst_workspace = Path(settings.FSEMS_WORKSPACE) / instance_id
    inst_workspace.mkdir(parents=True, exist_ok=True)
    
    # 优先部署用户指定的自定义 RootFS 路径，若未指定则自动定位模板匹配的默认 RootFS
    if rootfs_path and rootfs_path.strip():
        custom_rootfs = Path(rootfs_path.strip())
        if not custom_rootfs.exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "PATH_NOT_FOUND", "message": f"指定的 RootFS 自定义路径不存在: {rootfs_path}"},
            )
        try:
            if custom_rootfs.is_file():
                logger.info(f"为新实例部署用户指定的 RootFS 压缩包: {custom_rootfs} -> {inst_workspace}")
                extract_archive(custom_rootfs, inst_workspace)
            elif custom_rootfs.is_dir():
                logger.info(f"为新实例部署用户指定的 RootFS 文件夹目录: {custom_rootfs} -> {inst_workspace}")
                shutil.copytree(custom_rootfs, inst_workspace, symlinks=True, dirs_exist_ok=True)
        except Exception as e:
            logger.error(f"部署自定义 RootFS 失败: {e}")
            if inst_workspace.exists():
                shutil.rmtree(inst_workspace, ignore_errors=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error_code": "ROOTFS_SETUP_FAILED", "message": f"部署自定义根文件系统失败: {str(e)}"},
            )
    else:
        # 自动定位模板匹配的默认 RootFS 压缩包
        drive_path_obj = Path(template.drive_path)
        rootfs_archive = drive_path_obj.parent.parent / "rootfs" / f"{drive_path_obj.name}.gz"
        
        if not rootfs_archive.exists():
            logger.warning(f"模板对应的 RootFS 预置压缩包不存在: {rootfs_archive}，工作空间暂不部署预置文件系统")
        else:
            try:
                logger.info(f"自动为新实例解包部署模板匹配的默认 RootFS: {rootfs_archive} -> {inst_workspace}")
                extract_archive(rootfs_archive, inst_workspace)
            except Exception as e:
                logger.error(f"解包默认文件系统失败: {e}")
                if inst_workspace.exists():
                    shutil.rmtree(inst_workspace, ignore_errors=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={"error_code": "ROOTFS_SETUP_FAILED", "message": f"默认文件系统部署失败: {str(e)}"},
                )

    instance = Instance(
        id=instance_id,
        name=name,
        template_id=template_id,
        status="STOPPED",
        drive_path=None,  # 启动时自动安全回退到 template.drive_path
        guest_ssh_host=template.guest_ssh_host,
    )
    session.add(instance)
    await session.commit()
    await session.refresh(instance, attribute_names=["template"])
    return instance


async def _ensure_single_running(session: AsyncSession, exclude_id: str | None = None) -> None:
    query = select(Instance).where(Instance.status.in_(("RUNNING", "STARTING")))
    if exclude_id:
        query = query.where(Instance.id != exclude_id)
    result = await session.execute(query)
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "INSTANCE_STATE_CONFLICT",
                "message": "Phase 1 allows only one running instance",
            },
        )


async def _boot_watch(session_factory, instance_id: str) -> None:
    settings = get_settings()
    async with session_factory() as session:
        instance = await get_instance(session, instance_id)
        template = instance.template
        host = instance.guest_ssh_host or template.guest_ssh_host
        port = template.guest_ssh_port
        ok = await qemu_manager.wait_boot(host, port, settings.BOOT_TIMEOUT_SEC)
        instance = await get_instance(session, instance_id)
        if ok:
            instance.status = "RUNNING"
            instance.error_msg = None
        else:
            await qemu_manager.cleanup_instance_resources(instance)
            instance.status = "STOPPED"
            instance.pid = None
            instance.tap_name = None
            instance.error_msg = "Boot timeout"
        instance.updated_at = datetime.utcnow()
        await session.commit()


async def perform_action(session: AsyncSession, instance: Instance, action: str) -> Instance:
    settings = get_settings()
    template = instance.template

    if action == "start":
        if instance.status in RUNNING_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error_code": "INSTANCE_STATE_CONFLICT", "message": "Already running"},
            )
        await _ensure_single_running(session, exclude_id=instance.id)
        if not await bridge_exists(settings.FSEMS_BRIDGE):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error_code": "TAP_SETUP_FAILED", "message": f"Bridge {settings.FSEMS_BRIDGE} missing"},
            )
        kernel = Path(template.kernel_path)
        drive = Path(instance.drive_path or template.drive_path)
        if not kernel.exists() or not drive.exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "INSTANCE_BOOT_TIMEOUT",
                    "message": f"Kernel or drive missing: {kernel} / {drive}",
                },
            )
        instance.status = "STARTING"
        instance.error_msg = None
        instance.updated_at = datetime.utcnow()
        await session.commit()
        try:
            pid = await qemu_manager.start_instance(instance, template)
            instance.pid = pid
            await session.commit()
        except Exception as exc:
            logger.exception("QEMU start failed")
            instance.status = "STOPPED"
            instance.error_msg = str(exc)
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error_code": "TAP_SETUP_FAILED", "message": str(exc)},
            ) from exc

        from app.core.database import SessionLocal

        asyncio.create_task(_boot_watch(SessionLocal, instance.id))
        await session.refresh(instance, attribute_names=["template"])
        return instance

    if action == "stop":
        if instance.status not in RUNNING_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error_code": "INSTANCE_STATE_CONFLICT", "message": "Not running"},
            )
        instance.status = "STOPPING"
        await session.commit()
        await qemu_manager.cleanup_instance_resources(instance)
        instance.status = "STOPPED"
        instance.pid = None
        instance.tap_name = None
        instance.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(instance, attribute_names=["template"])
        return instance

    if action == "reset":
        await perform_action(session, instance, "stop")
        instance = await get_instance(session, instance.id)
        return await perform_action(session, instance, "start")

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid action")
