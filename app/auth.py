"""Authentication: password + HMAC token, using only Python stdlib."""

import hashlib
import hmac
import json
import secrets
import time

import aiosqlite
from fastapi import Request, HTTPException

from app.config import DB_PATH, TOKEN_EXPIRY_DAYS

_TOKEN_EXPIRY_SECONDS = TOKEN_EXPIRY_DAYS * 24 * 60 * 60


async def _get_or_create_secret() -> str:
    """Get the server HMAC secret, creating one on first run."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT value FROM settings WHERE key = 'auth_secret'"
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return json.loads(row[0])

        secret = secrets.token_hex(32)
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("auth_secret", json.dumps(secret), time.strftime("%Y-%m-%dT%H:%M:%S")),
        )
        await db.commit()
        return secret


async def _get_password_hash() -> str | None:
    """Get the stored password hash, or None if not set."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT value FROM settings WHERE key = 'password_hash'"
        ) as cursor:
            row = await cursor.fetchone()
            return json.loads(row[0]) if row else None


async def set_password(password: str):
    """Hash and store the admin password."""
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("password_hash", json.dumps(pw_hash), time.strftime("%Y-%m-%dT%H:%M:%S")),
        )
        await db.commit()


async def init_auth():
    """Initialize auth on first run. Generates a random password if none exists."""
    existing = await _get_password_hash()
    if not existing:
        password = secrets.token_urlsafe(16)
        await set_password(password)
        print("=" * 60)
        print(f"  INITIAL ADMIN PASSWORD: {password}")
        print("  Change this via Settings in the web app.")
        print("=" * 60)
    await _get_or_create_secret()


async def verify_password(password: str) -> bool:
    """Check a password against the stored hash."""
    stored_hash = await _get_password_hash()
    if not stored_hash:
        return False
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    return hmac.compare_digest(pw_hash, stored_hash)


async def create_token() -> str:
    """Create a signed authentication token."""
    secret = await _get_or_create_secret()
    payload = f"{int(time.time())}"
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


async def verify_token(token: str) -> bool:
    """Verify a token's signature and expiry."""
    try:
        payload, signature = token.rsplit(".", 1)
        secret = await _get_or_create_secret()
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return False
        created_at = int(payload)
        return (time.time() - created_at) < _TOKEN_EXPIRY_SECONDS
    except (ValueError, AttributeError):
        return False


async def auth_middleware(request: Request):
    """FastAPI dependency that verifies the auth token on protected routes.

    Accepts token via Authorization header or ?token= query param (for SSE/EventSource).
    """
    token_value = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token_value = auth_header[7:]
    else:
        token_value = request.query_params.get("token")

    if not token_value:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    if not await verify_token(token_value):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
