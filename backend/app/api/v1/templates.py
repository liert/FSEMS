from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.template import Template
from app.schemas.common import ApiResponse
from app.schemas.template import TemplateOut

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=ApiResponse[list[TemplateOut]])
async def list_templates(
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[list[TemplateOut]]:
    result = await session.execute(select(Template).order_by(Template.id))
    templates = result.scalars().all()
    return ApiResponse(data=[TemplateOut.model_validate(t) for t in templates], message="Templates fetched")
