# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Raspberry Pi-based solar hot water system with a FastAPI web app (PWA) for remote monitoring and control via Tailscale VPN.

## Running the App

```bash
# Development (mock hardware, no Pi required)
MOCK_HARDWARE=1 python3 -m app.main

# Production (on Pi, as systemd service)
sudo cp solar-hotwater.service /etc/systemd/system/
sudo systemctl enable --now solar-hotwater

# Dependencies
pip install fastapi 'uvicorn[standard]' aiosqlite

# R analysis scripts (standalone, read from hotwater/ log files)
Rscript plot.temperature.R
Rscript plot.voltages.R
Rscript temperature_record.R
```

## Architecture

### Web App (`app/`)
- **`main.py`**: FastAPI entry point, lifespan manages the control loop background task
- **`controller.py`**: Unified control loop (replaces old separate scripts). `compute_control_action()` is a pure function for testability. Runs every 10s (logging), makes control decisions every 60s
- **`sensors.py`**: DS18B20 reading by explicit device ID (not glob order). `read_all_raw()` for logging, `apply_offsets()` for display/control
- **`gpio_control.py`**: Pump (BOARD13) and boiler (BOARD11, NC/inverted) with mutual exclusion
- **`state.py`**: In-memory state + SQLite persistence for settings, alerts, auth
- **`auth.py`**: Password + HMAC token auth (stdlib only, no PyJWT)
- **`logger.py`**: Writes `hotwater/YYYY-MM-DD.log` in same format as legacy scripts
- **`routers/`**: API endpoints for temperatures, controls, schedule, system, alerts, auth
- **`static/`**: Vanilla JS PWA with Chart.js (no build step)

### Hardware
- **Sensors**: 3× DS18B20 on 1-wire bus (GPIO pin 17)
  - Panel (`28-01191239b6b8`): -6°C calibration offset for control/display, raw in logs
  - Inflow (`28-01191246472a`): no offset
  - Outflow (`28-0119124690d2`): no offset
- **Actuators**: Pump on BOARD13, Boiler on BOARD11 (NC relay: `pin.off()` = ON, `pin.on()` = OFF)

### Control Logic
- Solar window (default 10:00–16:00): pump controlled by temp differentials, boiler forced off
- **Pump ON**: `(panel - inflow > 10 OR panel > 40) AND panel > outflow`
- **Pump OFF**: `panel - outflow < -1`
- Boiler window (default 17:00–06:00): boiler on, pump off
- Pump and boiler are mutually exclusive
- Manual mode with configurable auto-revert timeout (default 2h)

### Log Format
Tab-separated RAW temperatures (no calibration offset): `DateTime\tPanel\tInflow\tOutflow`
R scripts apply the -6°C panel offset themselves when reading.
```
2025-11-12 00:00:10.949063	13.75	42.88	26.25
```

### Key Design Decisions
- `MOCK_HARDWARE=1` env var enables full app testing without Pi hardware
- SSE (not WebSocket) for real-time temp streaming — simpler, auto-reconnects
- SQLite for persistent state — survives power loss unlike JSON files
- Sensors read by explicit ID, not `glob.glob` order — eliminates filesystem dependency
- Single process replaces old separate controller + monitor scripts (avoids 1-wire bus contention)

### Legacy Scripts (`hotwater/`)
Original standalone scripts preserved for reference: `controller.temperature.py`, `temp.monitor.py`, `time_controller.py`. The new `app/` supersedes these.
