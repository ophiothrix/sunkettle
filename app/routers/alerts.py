"""Alert routes."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import auth_middleware

router = APIRouter(prefix="/alerts", tags=["alerts"], dependencies=[Depends(auth_middleware)])

_state = None


def init(state):
    global _state
    _state = state


class AlertsEnabledUpdate(BaseModel):
    sensor_failure: bool
    overtemp: bool
    pump_runtime: bool
    no_temp_rise: bool


@router.get("")
async def get_active_alerts():
    """Get all undismissed alerts."""
    return await _state.get_active_alerts()


@router.post("/{alert_id}/dismiss")
async def dismiss_alert(alert_id: int):
    """Dismiss an alert by ID."""
    await _state.dismiss_alert(alert_id)
    return {"status": "ok"}


@router.get("/settings")
async def get_alerts_settings():
    """Get alert enable/disable settings."""
    return _state.alerts_enabled


@router.put("/settings")
async def update_alerts_settings(req: AlertsEnabledUpdate):
    """Update which alert types are enabled."""
    _state.alerts_enabled = req.model_dump()
    await _state.save_setting("alerts_enabled", _state.alerts_enabled)
    return _state.alerts_enabled
