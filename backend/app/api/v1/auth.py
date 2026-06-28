from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.auth import LoginRequest, TokenData
from app.schemas.common import ApiResponse
from app.core.security import authenticate_user, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=ApiResponse[TokenData])
async def login(body: LoginRequest) -> ApiResponse[TokenData]:
    if not authenticate_user(body.username, body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "data": None,
                "error_code": "AUTH_INVALID_CREDENTIALS",
                "message": "Invalid username or password",
            },
        )
    token, expires = create_access_token(body.username)
    return ApiResponse(
        data=TokenData(access_token=token, expires_in=expires),
        message="Login success",
    )
