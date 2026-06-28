from fastapi import APIRouter

from app.api.v1 import auth, fs, instances, templates, logs, tasks

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(templates.router)
api_router.include_router(instances.router)
api_router.include_router(fs.router)
api_router.include_router(logs.router)
api_router.include_router(tasks.router)
