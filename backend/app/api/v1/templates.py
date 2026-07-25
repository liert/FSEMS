from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.template import Template
from app.schemas.common import ApiResponse
from app.schemas.template import TemplateCreate, TemplateOut, TemplateUpdate
from app.services import template_service
from app.services.openwrt_firmware import OpenWrtError
from app.services.qemu_probe import QemuProbeError, list_cpu_models

router = APIRouter(prefix="/templates", tags=["templates"])


class QemuCpuModelsOut(BaseModel):
    qemu_binary: str
    resolved_path: str
    cpus: list[str] = Field(default_factory=list)


class OpenWrtVersionsOut(BaseModel):
    versions: list[str] = Field(default_factory=list)
    arch_targets: dict[str, str] = Field(default_factory=dict)
    # 明确告诉前端：此处只有元数据，不含固件
    metadata_only: bool = True


class OpenWrtKernelItem(BaseModel):
    name: str
    url: str
    size: int | None = None
    local: bool = False
    local_path: str | None = None


class OpenWrtKernelsOut(BaseModel):
    version: str
    arch: str
    target: str
    kernels_dir: str
    kernels: list[OpenWrtKernelItem] = Field(default_factory=list)
    metadata_only: bool = True


class OpenWrtLocalKernelsOut(BaseModel):
    kernels_dir: str
    kernels: list[dict] = Field(default_factory=list)


class OpenWrtDownloadBody(BaseModel):
    version: str = Field(..., min_length=1, max_length=64)
    arch: str = Field(..., min_length=1, max_length=32)
    filename: str = Field(..., min_length=1, max_length=256)


class OpenWrtDownloadOut(BaseModel):
    name: str
    path: str
    size: int
    downloaded: bool
    url: str


@router.get("", response_model=ApiResponse[list[TemplateOut]])
async def list_templates(
    arch: str | None = Query(None, description="按架构过滤，如 aarch64 / mips / mipsel / x86_64"),
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[list[TemplateOut]]:
    query = select(Template).order_by(Template.id)
    if arch:
        query = query.where(Template.arch == arch)
    result = await session.execute(query)
    templates = result.scalars().all()
    return ApiResponse(data=[TemplateOut.model_validate(t) for t in templates], message="Templates fetched")


@router.get("/meta/cpu-models", response_model=ApiResponse[QemuCpuModelsOut])
async def get_qemu_cpu_models(
    qemu_binary: str = Query(..., min_length=1, max_length=128, description="QEMU 二进制，如 qemu-system-aarch64"),
    _user: str = Depends(get_current_user),
) -> ApiResponse[QemuCpuModelsOut]:
    """根据指定 QEMU 二进制执行 `-cpu help`，返回可用 CPU 型号列表。"""
    from app.services.qemu_probe import resolve_qemu_binary

    try:
        resolved = resolve_qemu_binary(qemu_binary)
        cpus = await list_cpu_models(qemu_binary)
    except QemuProbeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "QEMU_PROBE_FAILED", "message": str(exc)},
        ) from exc

    return ApiResponse(
        data=QemuCpuModelsOut(
            qemu_binary=qemu_binary.strip(),
            resolved_path=str(resolved),
            cpus=cpus,
        ),
        message="CPU models fetched",
    )


@router.get("/meta/openwrt/versions", response_model=ApiResponse[OpenWrtVersionsOut])
async def openwrt_versions(
    force: bool = Query(False, description="跳过缓存强制刷新"),
    _user: str = Depends(get_current_user),
) -> ApiResponse[OpenWrtVersionsOut]:
    """列出 OpenWrt 官方发布版本（含 snapshot）。"""
    from app.services import openwrt_firmware as ow

    try:
        versions = await ow.list_versions(force=force)
    except OpenWrtError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error_code": "OPENWRT_LIST_FAILED", "message": str(exc)},
        ) from exc
    return ApiResponse(
        data=OpenWrtVersionsOut(
            versions=versions,
            arch_targets=dict(ow.ARCH_OPENWRT_TARGET),
            metadata_only=True,
        ),
        message="OpenWrt version metadata fetched (no firmware downloaded)",
    )


@router.get("/meta/openwrt/kernels", response_model=ApiResponse[OpenWrtKernelsOut])
async def openwrt_kernels(
    version: str = Query(..., min_length=1, max_length=64),
    arch: str = Query(..., min_length=1, max_length=32),
    force: bool = Query(False),
    _user: str = Depends(get_current_user),
) -> ApiResponse[OpenWrtKernelsOut]:
    """按版本 + 架构列出 OpenWrt 内核文件，并标注是否已下载到本地。"""
    from app.services import openwrt_firmware as ow

    try:
        target = ow.target_for_arch(arch)
        kernels = await ow.list_kernels(version, arch, force=force)
    except OpenWrtError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "OPENWRT_KERNELS_FAILED", "message": str(exc)},
        ) from exc

    return ApiResponse(
        data=OpenWrtKernelsOut(
            version=version.strip(),
            arch=arch.strip(),
            target=target,
            kernels_dir=str(ow.kernels_dir()),
            kernels=[
                OpenWrtKernelItem(
                    name=k.name,
                    url=k.url,
                    size=k.size,
                    local=k.local,
                    local_path=k.local_path,
                )
                for k in kernels
            ],
            metadata_only=True,
        ),
        message="OpenWrt kernel directory index fetched (no firmware downloaded)",
    )


@router.get("/meta/openwrt/local-kernels", response_model=ApiResponse[OpenWrtLocalKernelsOut])
async def openwrt_local_kernels(
    _user: str = Depends(get_current_user),
) -> ApiResponse[OpenWrtLocalKernelsOut]:
    """列出本地 data/kernels 已有内核。"""
    from app.services import openwrt_firmware as ow

    items = ow.list_local_kernels()
    return ApiResponse(
        data=OpenWrtLocalKernelsOut(kernels_dir=str(ow.kernels_dir()), kernels=items),
        message="Local kernels listed",
    )


@router.post("/meta/openwrt/download", response_model=ApiResponse[OpenWrtDownloadOut])
async def openwrt_download_kernel(
    body: OpenWrtDownloadBody,
    _user: str = Depends(get_current_user),
) -> ApiResponse[OpenWrtDownloadOut]:
    """下载指定内核到 data/kernels（已存在则直接返回路径）。"""
    from app.services import openwrt_firmware as ow

    try:
        result = await ow.download_kernel(body.version, body.arch, body.filename)
    except OpenWrtError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "OPENWRT_DOWNLOAD_FAILED", "message": str(exc)},
        ) from exc

    return ApiResponse(data=OpenWrtDownloadOut(**result), message="Kernel ready")


@router.get("/{template_id}", response_model=ApiResponse[TemplateOut])
async def get_template_detail(
    template_id: int,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[TemplateOut]:
    template = await template_service.get_template(session, template_id)
    return ApiResponse(data=TemplateOut.model_validate(template), message="Template fetched")


@router.post("", response_model=ApiResponse[TemplateOut], status_code=status.HTTP_201_CREATED)
async def create_template(
    body: TemplateCreate,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[TemplateOut]:
    template = await template_service.create_template(session, body)
    return ApiResponse(data=TemplateOut.model_validate(template), message="Template created")


@router.put("/{template_id}", response_model=ApiResponse[TemplateOut])
async def update_template(
    template_id: int,
    body: TemplateUpdate,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[TemplateOut]:
    template = await template_service.update_template(session, template_id, body)
    return ApiResponse(data=TemplateOut.model_validate(template), message="Template updated")


@router.delete("/{template_id}", response_model=ApiResponse[dict])
async def delete_template(
    template_id: int,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    await template_service.delete_template(session, template_id)
    return ApiResponse(data={}, message="Template deleted")
