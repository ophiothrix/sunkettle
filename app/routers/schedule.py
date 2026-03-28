"""Schedule configuration routes."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import auth_middleware

router = APIRouter(prefix="/schedule", tags=["schedule"], dependencies=[Depends(auth_middleware)])

_state = None


def init(state):
    global _state
    _state = state


class ScheduleUpdate(BaseModel):
    solar_start: int = Field(ge=0, le=23)
    solar_end: int = Field(ge=0, le=23)
    boiler_start: int = Field(ge=0, le=23)
    boiler_end: int = Field(ge=0, le=23)


@router.get("")
async def get_schedule():
    return _state.schedule


@router.put("")
async def update_schedule(req: ScheduleUpdate):
    _state.schedule = req.model_dump()
    await _state.save_setting("schedule", _state.schedule)
    return _state.schedule
