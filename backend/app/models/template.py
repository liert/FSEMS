from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    arch: Mapped[str] = mapped_column(String(20), nullable=False)
    qemu_binary: Mapped[str] = mapped_column(String(50), nullable=False)
    machine: Mapped[str] = mapped_column(String(50), nullable=False)
    cpu: Mapped[str] = mapped_column(String(50), nullable=False)
    kernel_path: Mapped[str] = mapped_column(String(512), nullable=False)
    drive_path: Mapped[str] = mapped_column(String(512), nullable=False)
    kernel_append: Mapped[str] = mapped_column(Text, nullable=False)
    ram_size: Mapped[int] = mapped_column(Integer, default=512)
    guest_ssh_host: Mapped[str] = mapped_column(String(45), default="192.168.1.1")
    guest_ssh_port: Mapped[int] = mapped_column(Integer, default=22)
    extra_args: Mapped[str | None] = mapped_column(Text, nullable=True)

    instances: Mapped[list[Instance]] = relationship(back_populates="template")
