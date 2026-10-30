"""Password hashing (bcrypt) and JWT (HS256)."""
from __future__ import annotations

import time
from pathlib import Path

import bcrypt
import jwt

from ..config import Settings

_JWT_FILE = Path(__file__).resolve().parents[2] / "instance" / ".jwt_secret"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def _secret(settings: Settings) -> str:
    if settings.jwt_secret:
        return settings.jwt_secret
    _JWT_FILE.parent.mkdir(exist_ok=True)
    if _JWT_FILE.exists():
        return _JWT_FILE.read_text().strip()
    import secrets
    val = secrets.token_urlsafe(48)
    _JWT_FILE.write_text(val)
    return val


def create_token(settings: Settings, *, user_id: str, tenant_id: str, role: str) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id, "tid": tenant_id, "role": role,
        "iat": now, "exp": now + settings.jwt_expire_minutes * 60,
    }
    return jwt.encode(payload, _secret(settings), algorithm="HS256")


def decode_token(settings: Settings, token: str) -> dict:
    return jwt.decode(token, _secret(settings), algorithms=["HS256"])
