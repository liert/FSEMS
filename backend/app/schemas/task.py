# -*- coding: utf-8 -*-
from pydantic import BaseModel

class TaskStatusOut(BaseModel):
    task_id: str
    task_type: str | None = None
    status: str  # PENDING, RUNNING, SUCCESS, FAILURE
    progress: int
    result_ref: str | None = None
    error_msg: str | None = None
