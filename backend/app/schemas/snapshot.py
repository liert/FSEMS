from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SnapshotCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    instance_id: str
    name: str
    image_path: str
    size_bytes: int
    created_at: datetime


class SnapshotListOut(BaseModel):
    list: list[SnapshotOut]


class SnapshotRestoreResult(BaseModel):
    id: str
    instance_id: str
    restored_from: str
    drive_path: str


class SnapshotTaskResponse(BaseModel):
    task_id: str
    snapshot_id: str | None = None
