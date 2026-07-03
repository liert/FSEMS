from pydantic import BaseModel, ConfigDict, Field


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    arch: str
    qemu_binary: str
    machine: str
    cpu: str
    kernel_path: str
    drive_path: str
    kernel_append: str
    ram_size: int
    guest_ssh_host: str
    guest_ssh_port: int
    extra_args: str | None = None


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    arch: str = Field(..., min_length=1, max_length=20)
    qemu_binary: str = Field(..., min_length=1, max_length=50)
    machine: str = Field(..., min_length=1, max_length=50)
    cpu: str = Field(..., min_length=1, max_length=50)
    kernel_path: str = Field(..., min_length=1, max_length=512)
    drive_path: str = Field(..., min_length=1, max_length=512)
    kernel_append: str
    ram_size: int = Field(512, ge=64, le=16384)
    guest_ssh_host: str = "192.168.1.1"
    guest_ssh_port: int = Field(22, ge=1, le=65535)
    extra_args: str | None = None


class TemplateUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    arch: str | None = Field(None, min_length=1, max_length=20)
    qemu_binary: str | None = Field(None, min_length=1, max_length=50)
    machine: str | None = Field(None, min_length=1, max_length=50)
    cpu: str | None = Field(None, min_length=1, max_length=50)
    kernel_path: str | None = Field(None, min_length=1, max_length=512)
    drive_path: str | None = Field(None, min_length=1, max_length=512)
    kernel_append: str | None = None
    ram_size: int | None = Field(None, ge=64, le=16384)
    guest_ssh_host: str | None = None
    guest_ssh_port: int | None = Field(None, ge=1, le=65535)
    extra_args: str | None = None
