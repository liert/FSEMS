from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def verify_password(plain: str, expected: str) -> bool:
    settings = get_settings()
    if plain == settings.FSEMS_ADMIN_PASSWORD and expected == settings.FSEMS_ADMIN_PASSWORD:
        return True
    return pwd_context.verify(plain, expected) if expected.startswith("$2") else plain == expected


def authenticate_user(username: str, password: str) -> bool:
    settings = get_settings()
    return username == settings.FSEMS_ADMIN_USER and password == settings.FSEMS_ADMIN_PASSWORD


def create_access_token(subject: str) -> tuple[str, int]:
    settings = get_settings()
    expires = settings.JWT_EXPIRE_SECONDS
    expire = datetime.now(timezone.utc) + timedelta(seconds=expires)
    token = jwt.encode(
        {"sub": subject, "exp": expire},
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )
    return token, expires


def decode_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
