"""Authentication routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.auth import verify_password, create_token, set_password, verify_token

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/login")
async def login(req: LoginRequest):
    if not await verify_password(req.password):
        raise HTTPException(status_code=401, detail="Invalid password")
    token = await create_token()
    return {"token": token}


@router.post("/change-password")
async def change_password(req: ChangePasswordRequest):
    """Change the admin password. Requires current password for verification."""
    if not await verify_password(req.current_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    await set_password(req.new_password)
    return {"status": "ok"}
