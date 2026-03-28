"""Configuration constants for the Solar Hot Water system."""

import os
from pathlib import Path

# Environment
MOCK_HARDWARE = os.environ.get("MOCK_HARDWARE", "0") == "1"

# Paths
PROJECT_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = Path(os.environ.get("SOLAR_LOG_DIR", PROJECT_DIR / "hotwater"))
DB_PATH = Path(os.environ.get("SOLAR_DB_PATH", PROJECT_DIR / "app" / "solar.db"))

# Default sensor device IDs (DS18B20 on 1-wire bus)
# These are used on first run; once saved to SQLite, the DB values take precedence.
DEFAULT_SENSORS = {
    "panel": "28-01191239b6b8",
    "inflow": "28-01191246472a",
    "outflow": "28-0119124690d2",
}

# Roles that can be assigned to sensors
SENSOR_ROLES = ["panel", "inflow", "outflow"]

# Calibration offsets applied for control decisions and display (NOT in log files)
SENSOR_OFFSETS = {
    "panel": -6.0,
    "inflow": 0.0,
    "outflow": 0.0,
}

# 1-wire base path
W1_DEVICES_DIR = Path("/sys/bus/w1/devices")

# GPIO pin assignments (BOARD numbering)
PUMP_PIN = "BOARD13"
BOILER_PIN = "BOARD11"

# Control loop timing
MONITOR_INTERVAL = 10   # seconds between sensor reads / log writes
CONTROL_INTERVAL = 60   # seconds between control decisions

# Default schedule (hours, 24h format)
DEFAULT_SCHEDULE = {
    "solar_start": 10,   # pump can activate from this hour
    "solar_end": 16,     # pump deactivates after this hour (18 in summer)
    "boiler_start": 17,  # boiler activates from this hour
    "boiler_end": 6,     # boiler deactivates after this hour (next day)
}

# Control thresholds
DEFAULT_THRESHOLDS = {
    "pump_on_differential": 10.0,   # panel-inflow delta to turn pump on
    "pump_on_abs_temp": 40.0,       # absolute panel temp to turn pump on
    "pump_off_differential": -1.0,  # panel-outflow delta to turn pump off
}

# Manual mode safety timeout (seconds)
MANUAL_MODE_TIMEOUT = 2 * 60 * 60  # 2 hours

# Alert thresholds
DEFAULT_ALERT_THRESHOLDS = {
    "max_panel_temp": 95.0,         # °C
    "max_pump_runtime": 2 * 60 * 60,  # seconds (2 hours)
    "no_rise_timeout": 30 * 60,     # seconds (30 min pumping with no temp rise)
    "sensor_failure_count": 3,      # consecutive failures before alert
}

# Per-alert-type enable/disable (all on by default)
DEFAULT_ALERTS_ENABLED = {
    "sensor_failure": True,
    "overtemp": True,
    "pump_runtime": True,
    "no_temp_rise": True,
}

# Auth
TOKEN_EXPIRY_DAYS = 30

# Server
HOST = "0.0.0.0"
PORT = 8080
