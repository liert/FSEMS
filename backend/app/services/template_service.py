from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instance import Instance
from app.models.template import Template
from app.schemas.template import TemplateCreate, TemplateUpdate


def _validate_template_paths(kernel_path: str, drive_path: str) -> None:
    kernel = Path(kernel_path)
    drive = Path(drive_path)
    if not kernel.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "PATH_NOT_FOUND", "message": f"Kernel not found: {kernel_path}"},
        )
    if not drive.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "PATH_NOT_FOUND", "message": f"Drive image not found: {drive_path}"},
        )


async def get_template(session: AsyncSession, template_id: int) -> Template:
    template = await session.get(Template, template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "TEMPLATE_NOT_FOUND", "message": "Template not found"},
        )
    return template


async def create_template(session: AsyncSession, body: TemplateCreate) -> Template:
    existing = await session.scalar(select(Template).where(Template.name == body.name))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "TEMPLATE_NAME_CONFLICT", "message": "Template name already exists"},
        )

    _validate_template_paths(body.kernel_path, body.drive_path)
    template = Template(**body.model_dump())
    session.add(template)
    await session.commit()
    await session.refresh(template)
    return template


async def update_template(session: AsyncSession, template_id: int, body: TemplateUpdate) -> Template:
    template = await get_template(session, template_id)
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return template

    if "name" in updates:
        duplicate = await session.scalar(
            select(Template).where(Template.name == updates["name"], Template.id != template_id)
        )
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error_code": "TEMPLATE_NAME_CONFLICT", "message": "Template name already exists"},
            )

    kernel_path = updates.get("kernel_path", template.kernel_path)
    drive_path = updates.get("drive_path", template.drive_path)
    if "kernel_path" in updates or "drive_path" in updates:
        _validate_template_paths(kernel_path, drive_path)

    for field, value in updates.items():
        setattr(template, field, value)

    await session.commit()
    await session.refresh(template)
    return template


async def delete_template(session: AsyncSession, template_id: int) -> None:
    template = await get_template(session, template_id)
    in_use = await session.scalar(
        select(func.count()).select_from(Instance).where(Instance.template_id == template_id)
    )
    if in_use:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "TEMPLATE_IN_USE",
                "message": f"Template is referenced by {in_use} instance(s)",
            },
        )
    await session.delete(template)
    await session.commit()
