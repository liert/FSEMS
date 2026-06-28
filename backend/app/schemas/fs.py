from pydantic import BaseModel


class FileEntry(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int
    mtime: int


class HostDirListing(BaseModel):
    current_path: str
    files: list[FileEntry]


class GuestDirListing(BaseModel):
    instance_id: str
    current_path: str
    files: list[FileEntry]


class TransferRequest(BaseModel):
    instance_id: str
    direction: str  # host_to_guest 或 guest_to_host
    src: str
    dest: str


class TransferResponse(BaseModel):
    task_id: str
