"""Control loop logic for the solar hot water system.

Faithfully ports the logic from hotwater/controller.temperature.py into a
testable pure function plus an async loop that integrates with the FastAPI app.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from functools import partial

from app import sensors
from app.gpio_control import GPIOController
from app.logger import TemperatureLogger
from app.state import AppState
from app.alerts import check_alerts
from app.config import MONITOR_INTERVAL, CONTROL_INTERVAL


@dataclass
class ControlAction:
    pump: bool
    boiler: bool


def compute_control_action(
    panel: float | None,
    inflow: float | None,
    outflow: float | None,
    hour: int,
    schedule: dict,
    thresholds: dict,
    current_pump: bool,
    current_boiler: bool,
) -> ControlAction:
    """Pure function: compute desired pump/boiler state from temperatures and time.

    Uses calibrated temperatures (panel has -6 offset already applied).
    Returns the desired state — caller is responsible for applying it.
    """
    solar_start = schedule["solar_start"]
    solar_end = schedule["solar_end"]
    boiler_start = schedule["boiler_start"]
    boiler_end = schedule["boiler_end"]

    pump_on_diff = thresholds["pump_on_differential"]
    pump_on_abs = thresholds["pump_on_abs_temp"]
    pump_off_diff = thresholds["pump_off_differential"]

    pump = current_pump
    boiler = current_boiler

    # Solar window: control pump based on temperature differentials
    if solar_start <= hour < solar_end:
        boiler = False  # keep boiler off during solar window

        if panel is not None and inflow is not None and outflow is not None:
            # Pump ON conditions (both must be true):
            # 1. Panel is significantly hotter than inflow OR above absolute threshold
            # 2. Panel is hotter than outflow (sanity check)
            if (panel - inflow > pump_on_diff or panel > pump_on_abs) and panel > outflow:
                pump = True

            # Pump OFF condition: panel cooler than outflow (heat exchanger saturated)
            if panel - outflow < pump_off_diff:
                pump = False

    # Boiler window: boiler on, pump off
    elif _in_boiler_window(hour, boiler_start, boiler_end):
        pump = False
        boiler = True

    # Transition periods: both off
    else:
        pump = False
        boiler = False

    return ControlAction(pump=pump, boiler=boiler)


def _in_boiler_window(hour: int, start: int, end: int) -> bool:
    """Check if current hour is in the boiler heating window.

    Handles overnight windows (e.g. 17:00 to 06:00).
    """
    if start <= end:
        return start <= hour < end
    else:
        # Overnight: e.g. start=17, end=6 → 17-23 or 0-5
        return hour >= start or hour < end


async def run_control_loop(state: AppState, gpio: GPIOController, logger: TemperatureLogger):
    """Main control loop — runs every MONITOR_INTERVAL seconds.

    Reads sensors and logs every iteration (10s).
    Makes control decisions every CONTROL_INTERVAL / MONITOR_INTERVAL iterations (60s).
    """
    iterations_per_decision = CONTROL_INTERVAL // MONITOR_INTERVAL
    iteration = 0

    while True:
        try:
            # Read sensors in a thread to avoid blocking the async event loop
            loop = asyncio.get_running_loop()
            raw_temps = await loop.run_in_executor(None, sensors.read_all_raw, state.sensor_map)
            calibrated = sensors.apply_offsets(raw_temps, state.sensor_offsets)
            state.update_temperatures(raw_temps, calibrated)

            # Log raw temperatures every iteration (in thread to avoid blocking)
            await loop.run_in_executor(None, logger.write, raw_temps)

            # Control decision every 6th iteration (60s)
            if iteration % iterations_per_decision == 0:
                # Check manual mode timeout
                if state.check_manual_timeout():
                    await state.add_alert("mode_change", "Manual mode timed out — reverted to auto")
                    await state.save_setting("mode", "auto")

                if state.mode == "auto":
                    action = compute_control_action(
                        panel=calibrated.get("panel"),
                        inflow=calibrated.get("inflow"),
                        outflow=calibrated.get("outflow"),
                        hour=datetime.now().hour,
                        schedule=state.schedule,
                        thresholds=state.thresholds,
                        current_pump=gpio.pump_on,
                        current_boiler=gpio.boiler_on,
                    )
                    gpio.set_pump(action.pump)
                    gpio.set_boiler(action.boiler)

                # Check alert conditions
                await check_alerts(state, gpio)

            iteration += 1

        except Exception as e:
            # Log but don't crash — the control loop must keep running
            print(f"Control loop error: {e}")

        await asyncio.sleep(MONITOR_INTERVAL)
