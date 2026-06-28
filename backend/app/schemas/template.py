from pydantic import BaseModel, ConfigDict


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
