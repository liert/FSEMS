import asyncio

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.schemas.common import ApiResponse
from app.schemas.firmware_tools import FilesystemConvertRequest, FilesystemConvertResult
from app.services.firmware_tools import convert_filesystem

router = APIRouter(prefix="/firmware-tools", tags=["firmware-tools"])


@router.post("/filesystem/convert", response_model=ApiResponse[FilesystemConvertResult])
async def convert_filesystem_image(
    body: FilesystemConvertRequest,
    _user: str = Depends(get_current_user),
) -> ApiResponse[FilesystemConvertResult]:
    result = await asyncio.to_thread(
        convert_filesystem,
        body.source_path,
        body.source_type,
        body.target_type,
        body.output_name,
        body.size_mb,
    )
    return ApiResponse(data=FilesystemConvertResult(**result), message="文件系统转换完成")
