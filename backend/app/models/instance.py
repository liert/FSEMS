from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.snapshot import Snapshot
    from app.models.template import Template


class Instance(Base):
    __tablename__ = "instances"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("templates.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="STOPPED")
    drive_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tap_name: Mapped[str | None] = mapped_column(String(32), nullable=True)
    guest_ssh_host: Mapped[str | None] = mapped_column(String(45), nullable=True)
    network_type: Mapped[str | None] = mapped_column(String(20), default="same", server_default="same")
    bridge_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    filesystem_type: Mapped[str] = mapped_column(String(20), default="ext4", server_default="ext4")
    use_custom_rootfs: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    custom_rootfs_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    serial_socket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    template: Mapped[Template] = relationship(back_populates="instances")
    snapshots: Mapped[list[Snapshot]] = relationship(back_populates="instance", cascade="all, delete-orphan")
