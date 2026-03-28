"""Temperature API routes: current readings, historical data, SSE stream."""

import json
import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.auth import auth_middleware
from app.config import LOG_DIR, MONITOR_INTERVAL

router = APIRouter(prefix="/temperatures", tags=["temperatures"], dependencies=[Depends(auth_middleware)])

# These get set by main.py at startup
_state = None
_gpio = None


def init(state, gpio):
    global _state, _gpio
    _state = state
    _gpio = gpio


@router.get("/current")
async def get_current():
    """Get the latest temperature readings and relay states."""
    snapshot = _state.get_snapshot()
    gpio_state = _gpio.get_state()
    snapshot["pump_on"] = gpio_state["pump_on"]
    snapshot["boiler_on"] = gpio_state["boiler_on"]
    snapshot["pump_on_since"] = gpio_state["pump_on_since"]
    snapshot["boiler_on_since"] = gpio_state["boiler_on_since"]
    return snapshot


@router.get("/stream")
async def temperature_stream(request: Request):
    """Server-Sent Events stream of real-time temperature and state data."""
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            snapshot = _state.get_snapshot()
            gpio_state = _gpio.get_state()
            snapshot["pump_on"] = gpio_state["pump_on"]
            snapshot["boiler_on"] = gpio_state["boiler_on"]
            snapshot["pump_on_since"] = gpio_state["pump_on_since"]
            snapshot["boiler_on_since"] = gpio_state["boiler_on_since"]
            yield f"data: {json.dumps(snapshot)}\n\n"
            await asyncio.sleep(MONITOR_INTERVAL)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{date}")
async def get_historical(date: str):
    """Get temperature data for a specific date.

    Returns downsampled to ~1-minute averages for efficiency.
    Date format: YYYY-MM-DD
    """
    # Validate date format
    if len(date) != 10 or date[4] != "-" or date[7] != "-":
        raise HTTPException(status_code=400, detail="Date format must be YYYY-MM-DD")

    log_path = Path(LOG_DIR) / f"{date}.log"
    if not log_path.exists():
        raise HTTPException(status_code=404, detail=f"No data for {date}")

    # Parse and downsample
    readings = []
    bucket_readings = []
    current_minute = None

    with open(log_path, "r") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) != 4:
                continue
            try:
                timestamp = parts[0]
                panel = float(parts[1])
                inflow = float(parts[2])
                outflow = float(parts[3])
            except (ValueError, IndexError):
                continue

            # Downsample to 1-minute averages
            minute = timestamp[:16]  # YYYY-MM-DD HH:MM
            if minute != current_minute:
                if bucket_readings:
                    readings.append(_average_bucket(current_minute, bucket_readings))
                current_minute = minute
                bucket_readings = []
            bucket_readings.append((panel, inflow, outflow))

    # Don't forget the last bucket
    if bucket_readings:
        readings.append(_average_bucket(current_minute, bucket_readings))

    return {"date": date, "count": len(readings), "readings": readings}


def _average_bucket(minute: str, bucket: list[tuple]) -> dict:
    """Average a bucket of readings into a single data point."""
    n = len(bucket)
    return {
        "time": minute,
        "panel": round(sum(r[0] for r in bucket) / n, 2),
        "inflow": round(sum(r[1] for r in bucket) / n, 2),
        "outflow": round(sum(r[2] for r in bucket) / n, 2),
    }
