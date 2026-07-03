from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.template import Template
from app.schemas.common import ApiResponse
from app.schemas.template import TemplateCreate, TemplateOut, TemplateUpdate
from app.services import template_service

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=ApiResponse[list[TemplateOut]])
async def list_templates(
    arch: str | None = Query(None, description="按架构过滤，如 aarch64 / mips / mipsel / x86_64"),
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[list[TemplateOut]]:
    query = select(Template).order_by(Template.id)
    if arch:
        query = query.where(Template.arch == arch)
    result = await session.execute(query)
    templates = result.scalars().all()
    return ApiResponse(data=[TemplateOut.model_validate(t) for t in templates], message="Templates fetched")


@router.get("/{template_id}", response_model=ApiResponse[TemplateOut])
async def get_template_detail(
    template_id: int,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[TemplateOut]:
    template = await template_service.get_template(session, template_id)
    return ApiResponse(data=TemplateOut.model_validate(template), message="Template fetched")


@router.post("", response_model=ApiResponse[TemplateOut], status_code=status.HTTP_201_CREATED)
async def create_template(
    body: TemplateCreate,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[TemplateOut]:
    template = await template_service.create_template(session, body)
    return ApiResponse(data=TemplateOut.model_validate(template), message="Template created")


@router.put("/{template_id}", response_model=ApiResponse[TemplateOut])
async def update_template(
    template_id: int,
    body: TemplateUpdate,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[TemplateOut]:
    template = await template_service.update_template(session, template_id, body)
    return ApiResponse(data=TemplateOut.model_validate(template), message="Template updated")


@router.delete("/{template_id}", response_model=ApiResponse[dict])
async def delete_template(
    template_id: int,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    await template_service.delete_template(session, template_id)
    return ApiResponse(data={}, message="Template deleted")
