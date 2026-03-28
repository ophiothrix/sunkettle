"""System status routes."""

import platform
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends

from app.auth import auth_middleware
from app.config import MOCK_HARDWARE

router = APIRouter(prefix="/system", tags=["system"], dependencies=[Depends(auth_middleware)])

_state = None
_gpio = None


def init(state, gpio):
    global _state, _gpio
    _state = state
    _gpio = gpio


@router.get("")
async def get_system_status():
    """System information: uptime, CPU temperature, controller status."""
    cpu_temp = _read_cpu_temp()
    uptime = _read_uptime()

    return {
        "cpu_temp": cpu_temp,
        "uptime_seconds": uptime,
        "uptime_human": _format_uptime(uptime),
        "controller_started": _state.controller_started.isoformat(),
        "controller_uptime": (datetime.now() - _state.controller_started).total_seconds(),
        "last_sensor_read": _state.last_sensor_read.isoformat() if _state.last_sensor_read else None,
        "sensor_failures": _state.sensor_failures,
        "mode": _state.mode,
        "mock_hardware": MOCK_HARDWARE,
        "platform": platform.machine(),
        "gpio_state": _gpio.get_state(),
    }


def _read_cpu_temp() -> float | None:
    """Read Raspberry Pi CPU temperature."""
    thermal_path = Path("/sys/class/thermal/thermal_zone0/temp")
    if thermal_path.exists():
        try:
            return int(thermal_path.read_text().strip()) / 1000.0
        except (ValueError, OSError):
            return None
    return None


def _read_uptime() -> float | None:
    """Read system uptime in seconds."""
    uptime_path = Path("/proc/uptime")
    if uptime_path.exists():
        try:
            return float(uptime_path.read_text().strip().split()[0])
        except (ValueError, OSError):
            return None
    return None


def _format_uptime(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"
