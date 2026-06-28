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
    
    # 获取模板预置的默认 .img.gz 物理归档包
    default_rootfs_gz = Path(template.drive_path)
    instance_drive_path = inst_workspace / "rootfs.img"
    
    # 1. 自动为该实例部署属于它自己的独立 QEMU 启动磁盘（从默认模板解压或者自定义路径解压）
    try:
        if rootfs_path and rootfs_path.strip():
            custom_rootfs = Path(rootfs_path.strip())
            if not custom_rootfs.exists():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "PATH_NOT_FOUND", "message": f"指定的 RootFS 自定义路径不存在: {rootfs_path}"},
                )
            
            if custom_rootfs.is_file():
                # 如果用户提供的是一个文件
                logger.info(f"为新实例部署用户指定的 RootFS 文件: {custom_rootfs}")
                suffix = custom_rootfs.suffix.lower()
                name_lower = custom_rootfs.name.lower()
                
                if name_lower.endswith(".img.gz") or suffix == ".gz":
                    # 如果是 .img.gz 格式镜像包，解压得到该实例的独立启动盘
                    import gzip
                    logger.info(f"解压自定义镜像包得到实例的启动磁盘: {custom_rootfs} -> {instance_drive_path}")
                    with gzip.open(custom_rootfs, "rb") as f_in:
                        with open(instance_drive_path, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    # 同时提取该磁盘镜像的文件树到工作区以供宿主机 VFS 浏览器访问
                    logger.info(f"提取自定义磁盘文件系统到工作区: {instance_drive_path} -> {inst_workspace}")
                    extract_archive(custom_rootfs, inst_workspace)
                else:
                    # 其他格式的文件包（如 .tar.gz），直接解包至工作区
                    extract_archive(custom_rootfs, inst_workspace)
                    # 同时，将默认模板的 .img.gz 解包作为独立系统磁盘
                    if default_rootfs_gz.exists():
                        import gzip
                        with gzip.open(default_rootfs_gz, "rb") as f_in:
                            with open(instance_drive_path, "wb") as f_out:
                                shutil.copyfileobj(f_in, f_out)
            elif custom_rootfs.is_dir():
                # 如果用户提供的是文件夹，递归复制其全部文件系统树到工作区
                logger.info(f"拷贝自定义文件系统根文件夹到工作区: {custom_rootfs} -> {inst_workspace}")
                shutil.copytree(custom_rootfs, inst_workspace, symlinks=True, dirs_exist_ok=True)
                # 同时，将默认模板的 .img.gz 解压作为该实例的独立 QEMU 启动磁盘
                if default_rootfs_gz.exists():
                    import gzip
                    with gzip.open(default_rootfs_gz, "rb") as f_in:
                        with open(instance_drive_path, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)
        else:
            # 用户未指定自定义 RootFS，自动使用该模板匹配的默认 RootFS 压缩包进行解压部署
            if not default_rootfs_gz.exists():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={"error_code": "DEFAULT_ROOTFS_MISSING", "message": f"模板预设磁盘文件系统不存在: {default_rootfs_gz}"},
                )
            # a. 解压 .img.gz 为该实例独立的系统盘镜像 rootfs.img
            import gzip
            logger.info(f"自动解压预置镜像包到实例工作区作为独立系统磁盘: {default_rootfs_gz} -> {instance_drive_path}")
            with gzip.open(default_rootfs_gz, "rb") as f_in:
                with open(instance_drive_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            # b. 使用 debugfs 将该系统盘的文件树递归释放到工作区
            logger.info(f"自动提取实例独立磁盘的文件树到工作区: {instance_drive_path} -> {inst_workspace}")
            extract_archive(default_rootfs_gz, inst_workspace)
            
    except Exception as e:
        logger.error(f"部署实例专属文件系统失败: {e}")
        if inst_workspace.exists():
            shutil.rmtree(inst_workspace, ignore_errors=True)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "ROOTFS_SETUP_FAILED", "message": f"部署专属文件系统失败: {str(e)}"},
        )

    # 实例专属 QEMU 磁盘镜像路径
    drive_path = str(instance_drive_path.resolve()) if instance_drive_path.exists() else None

    instance = Instance(
        id=instance_id,
        name=name,
        template_id=template_id,
        status="STOPPED",
        drive_path=drive_path,  # 启动时使用该实例专属的 rootfs.img 磁盘块设备
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
