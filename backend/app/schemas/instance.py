from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InstanceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    template_id: int
    rootfs_path: str | None = None


class InstanceAction(BaseModel):
    action: str = Field(pattern="^(start|stop|reset)$")


class InstanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    template_id: int
    status: str
    tap_name: str | None = None
    guest_ssh_host: str | None = None
    guest_ssh_port: int = 22
    pid: int | None = None
    created_at: datetime


class InstanceListOut(BaseModel):
    total: int
    list: list[InstanceOut]


class InstanceCreated(BaseModel):
    id: str
    status: str


class InstanceActionResult(BaseModel):
    id: str
    status: str
