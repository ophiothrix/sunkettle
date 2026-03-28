"""Alert condition checking for the solar hot water system."""

from datetime import datetime

from app.config import DEFAULT_ALERT_THRESHOLDS


async def check_alerts(state, gpio):
    """Check all alert conditions and store any triggered alerts.

    Called every control decision cycle (60 seconds).
    Respects per-alert-type enable/disable from state.alerts_enabled.
    """
    thresholds = state.alert_thresholds
    enabled = state.alerts_enabled
    calibrated = state.calibrated_temps

    # Sensor failure: N consecutive failures
    if enabled.get("sensor_failure", True):
        max_failures = thresholds["sensor_failure_count"]
        for name, count in state.sensor_failures.items():
            if count == max_failures:  # alert exactly once at the threshold
                await state.add_alert(
                    "sensor_failure",
                    f"Sensor '{name}' has failed {count} consecutive reads",
                )

    # Panel overtemperature
    if enabled.get("overtemp", True):
        panel_temp = calibrated.get("panel")
        if panel_temp is not None and panel_temp > thresholds["max_panel_temp"]:
            await state.add_alert(
                "overtemp",
                f"Panel temperature {panel_temp:.1f}\u00b0C exceeds {thresholds['max_panel_temp']:.0f}\u00b0C limit",
            )

    # Pump running too long
    if enabled.get("pump_runtime", True):
        if gpio.pump_on and gpio.pump_on_since:
            runtime = (datetime.now() - gpio.pump_on_since).total_seconds()
            # Alert at the threshold (within one control cycle of the limit)
            if abs(runtime - thresholds["max_pump_runtime"]) < 65:
                await state.add_alert(
                    "pump_runtime",
                    f"Pump has been running for {runtime / 3600:.1f} hours",
                )

    # No temperature rise after pumping
    if enabled.get("no_temp_rise", True):
        outflow = calibrated.get("outflow")
        if gpio.pump_on and gpio.pump_on_since and outflow is not None:
            runtime = (datetime.now() - gpio.pump_on_since).total_seconds()
            if runtime > thresholds["no_rise_timeout"]:
                # Track starting temperature
                if state.pump_on_temp_at_start is None:
                    state.pump_on_temp_at_start = outflow
                elif outflow <= state.pump_on_temp_at_start:
                    await state.add_alert(
                        "no_temp_rise",
                        f"Outflow temperature has not risen after {runtime / 60:.0f} minutes of pumping",
                    )
                    # Reset to avoid repeated alerts
                    state.pump_on_temp_at_start = outflow
        else:
            state.pump_on_temp_at_start = None
    else:
        state.pump_on_temp_at_start = None
