from typing import Literal

from pydantic import BaseModel, Field


FilesystemType = Literal["ext4", "squashfs", "f2fs"]
SourceFilesystemType = Literal["auto", "ext4", "squashfs", "f2fs"]


class FilesystemConvertRequest(BaseModel):
    source_path: str = Field(min_length=1, max_length=512)
    source_type: SourceFilesystemType = "auto"
    target_type: FilesystemType
    output_name: str | None = Field(default=None, max_length=128)
    size_mb: int | None = Field(default=None, ge=32, le=131072)


class FilesystemConvertResult(BaseModel):
    source_path: str
    source_type: str
    target_type: str
    output_path: str
    output_size_bytes: int
    duration_ms: int
