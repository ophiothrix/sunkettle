"""Sensor configuration routes: scan bus, get/set assignments and offsets."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import auth_middleware
from app import sensors as sensor_module

router = APIRouter(prefix="/sensors", tags=["sensors"], dependencies=[Depends(auth_middleware)])

_state = None


def init(state):
    global _state
    _state = state


class SensorAssignment(BaseModel):
    panel: str
    inflow: str
    outflow: str


class SensorOffsets(BaseModel):
    panel: float
    inflow: float
    outflow: float


@router.get("")
async def get_sensor_config():
    """Get current sensor assignments, offsets, and available devices."""
    available = sensor_module.scan_available()
    return {
        "assignments": _state.sensor_map,
        "offsets": _state.sensor_offsets,
        "available": available,
    }


@router.put("/assignments")
async def update_assignments(req: SensorAssignment):
    """Update which physical sensor is assigned to each role."""
    new_map = req.model_dump()
    # Validate: all IDs must be non-empty strings
    for role, device_id in new_map.items():
        if not device_id or not device_id.startswith("28-"):
            raise HTTPException(status_code=400, detail=f"Invalid sensor ID for {role}: {device_id}")
    _state.sensor_map = new_map
    await _state.save_setting("sensor_map", new_map)
    return _state.sensor_map


@router.put("/offsets")
async def update_offsets(req: SensorOffsets):
    """Update calibration offsets for each sensor role."""
    new_offsets = req.model_dump()
    _state.sensor_offsets = new_offsets
    await _state.save_setting("sensor_offsets", new_offsets)
    return _state.sensor_offsets
