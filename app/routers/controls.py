"""Control routes: pump, boiler, and mode switching."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import auth_middleware

router = APIRouter(prefix="/controls", tags=["controls"], dependencies=[Depends(auth_middleware)])

_state = None
_gpio = None


def init(state, gpio):
    global _state, _gpio
    _state = state
    _gpio = gpio


class ToggleRequest(BaseModel):
    on: bool


class ModeRequest(BaseModel):
    mode: str  # "auto" or "manual"


@router.post("/pump")
async def set_pump(req: ToggleRequest):
    """Toggle the pump. Only works in manual mode."""
    if _state.mode != "manual":
        raise HTTPException(status_code=400, detail="Switch to manual mode first")
    _gpio.set_pump(req.on)
    return _gpio.get_state()


@router.post("/boiler")
async def set_boiler(req: ToggleRequest):
    """Toggle the boiler. Only works in manual mode."""
    if _state.mode != "manual":
        raise HTTPException(status_code=400, detail="Switch to manual mode first")
    _gpio.set_boiler(req.on)
    return _gpio.get_state()


@router.post("/mode")
async def set_mode(req: ModeRequest):
    """Switch between auto and manual mode."""
    if req.mode not in ("auto", "manual"):
        raise HTTPException(status_code=400, detail="Mode must be 'auto' or 'manual'")
    await _state.set_mode(req.mode)
    return {"mode": _state.mode, "manual_timeout_remaining": _state._manual_timeout_remaining()}
