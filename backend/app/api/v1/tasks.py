# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_current_user, get_db
from app.schemas.common import ApiResponse
from app.schemas.task import TaskStatusOut
from app.models.task import Task

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.get("/{task_id}/status", response_model=ApiResponse[TaskStatusOut])
async def get_task_status(
    task_id: str,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[TaskStatusOut]:
    """
    根据任务 ID 查询 Celery 文件传输任务的进度及状态。
    """
    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "INSTANCE_NOT_FOUND", "message": "Task not found"},
        )
        
    return ApiResponse(
        data=TaskStatusOut(
            task_id=task.id,
            status=task.status,
            progress=task.progress,
            error_msg=task.error_msg
        ),
        message="Task status queried",
    )
