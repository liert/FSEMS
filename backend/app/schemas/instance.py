from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InstanceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    template_id: int
    rootfs_path: str | None = None
    network_type: str | None = "same"  # "same" (同一局域网) 或 "different" (不同局域网)
    filesystem_type: Literal["ext4", "squashfs", "f2fs"] = "ext4"
    use_custom_rootfs: bool = False


class InstanceCpuUpdate(BaseModel):
    """创建后修改实例 QEMU CPU；空字符串或 null 表示恢复模板默认值。"""
    cpu: str | None = Field(default=None, max_length=50)


class InstanceAction(BaseModel):
    action: str = Field(pattern="^(start|stop|reset)$")
    allow_sigkill: bool | None = None


class InstanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    template_id: int
    status: str
    tap_name: str | None = None
    guest_ssh_host: str | None = None
    guest_ssh_port: int = 22
    network_type: str | None = None
    bridge_name: str | None = None
    filesystem_type: str = "ext4"
    use_custom_rootfs: bool = False
    cpu: str | None = None
    pid: int | None = None
    created_at: datetime


class InstanceDetailOut(InstanceOut):
    template_name: str
    template_arch: str
    template_cpu: str | None = None
    effective_cpu: str | None = None
    ram_size_mb: int
    ram_used_mb: float | None = None
    drive_path: str | None = None
    drive_fs_total_bytes: int | None = None
    drive_fs_used_bytes: int | None = None
    custom_rootfs_source_path: str | None = None
    custom_rootfs_dir_path: str | None = None
    custom_rootfs_dir_size_bytes: int | None = None
    workspace_path: str
    kernel_path: str
    error_msg: str | None = None


class InstanceListOut(BaseModel):
    total: int
    list: list[InstanceOut]


class InstanceCreated(BaseModel):
    id: str
    status: str


class InstanceActionResult(BaseModel):
    id: str
    status: str


class DriveExpandRequest(BaseModel):
    expand_mb: int = Field(ge=1, le=4096, description="扩容增量 (MB)")
    manage_lifecycle: bool = True


class DriveExpandResult(BaseModel):
    expanded_mb: int
    drive_path: str
    drive_fs_total_bytes: int | None = None
    drive_fs_used_bytes: int | None = None
    stopped_for_expand: bool = False
    restarted: bool = False
    status: str


class CustomRootfsUpdate(BaseModel):
    """创建后修改自定义 RootFS 源路径；空字符串表示清除。"""
    rootfs_path: str | None = Field(None, max_length=512)
