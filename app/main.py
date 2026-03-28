"""FastAPI application entry point for the Solar Hot Water system."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import HOST, PORT
from app.state import AppState
from app.gpio_control import GPIOController
from app.logger import TemperatureLogger
from app.controller import run_control_loop
from app.auth import init_auth
from app.routers import temperatures, controls, schedule, system, alerts, auth, sensors


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # Initialize
    state = AppState()
    gpio = GPIOController()
    logger = TemperatureLogger()
    await state.init_db()
    await init_auth()

    # Wire state into routers
    temperatures.init(state, gpio)
    controls.init(state, gpio)
    schedule.init(state)
    system.init(state, gpio)
    alerts.init(state)
    sensors.init(state)

    # Start control loop as background task
    loop_task = asyncio.create_task(run_control_loop(state, gpio, logger))

    print(f"Solar Hot Water Controller running on http://{HOST}:{PORT}")
    yield

    # Shutdown
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass
    logger.close()


app = FastAPI(title="Solar Hot Water", lifespan=lifespan)

# API routers
app.include_router(auth.router, prefix="/api")
app.include_router(temperatures.router, prefix="/api")
app.include_router(controls.router, prefix="/api")
app.include_router(schedule.router, prefix="/api")
app.include_router(system.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(sensors.router, prefix="/api")

# Static files (PWA) — must be last so it doesn't shadow API routes
static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
