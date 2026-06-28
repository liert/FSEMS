# -*- coding: utf-8 -*-
from pydantic import BaseModel

class TaskStatusOut(BaseModel):
    task_id: str
    status: str  # PENDING, RUNNING, SUCCESS, FAILURE
    progress: int
    error_msg: str | None = None
