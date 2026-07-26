from pydantic import BaseModel


class FileEntry(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int
    mtime: int
    # 符号链接信息：rootfs 里大量条目是指向 busybox 的链接，展示出来便于辨认
    is_link: bool = False
    link_target: str | None = None


class HostDirListing(BaseModel):
    current_path: str
    files: list[FileEntry]
    host_root_path: str | None = None


class GuestDirListing(BaseModel):
    instance_id: str
    current_path: str
    files: list[FileEntry]
    mode: str | None = None


class TransferRequest(BaseModel):
    instance_id: str
    direction: str  # host_to_guest 或 guest_to_host
    src: str
    dest: str


class TransferResponse(BaseModel):
    task_id: str


class HostUploadResult(BaseModel):
    path: str
    name: str
    size: int


class GuestFsOpRequest(BaseModel):
    op: str  # mkdir, delete, rename
    path: str
    dest_path: str | None = None


class GuestFsOpResult(BaseModel):
    op: str
    path: str
    dest_path: str | None = None


class HostFsOpRequest(BaseModel):
    op: str  # mkdir, delete, rename
    path: str
    dest_path: str | None = None


class HostFsOpResult(BaseModel):
    op: str
    path: str
    dest_path: str | None = None
