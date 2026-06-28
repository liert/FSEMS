from pydantic import BaseModel

class BackendLogsOut(BaseModel):
    log_type: str
    total_lines: int
    lines: list[str]

class FrontendLogCreate(BaseModel):
    level: str
    message: str
    stack: str | None = None
    url: str | None = None

class FrontendLogOut(BaseModel):
    id: int
    level: str
    message: str
    stack: str | None = None
    url: str | None = None
    created_at: str

class FrontendLogsOut(BaseModel):
    logs: list[FrontendLogOut]
