"""Temperature sensor reading for DS18B20 sensors on 1-wire bus."""

import glob as globmod
import time
import random
from datetime import datetime
from pathlib import Path

from app.config import SENSOR_OFFSETS, W1_DEVICES_DIR, MOCK_HARDWARE

MAX_CRC_RETRIES = 5
CRC_RETRY_DELAY = 1.0  # seconds


def _read_raw(device_file: Path) -> list[str]:
    """Read raw lines from a 1-wire device file."""
    with open(device_file, "r") as f:
        return f.readlines()


def _read_temp(device_file: Path) -> float | None:
    """Read temperature from a single DS18B20 sensor.

    Returns temperature in °C, or None if the read fails after retries.
    """
    for _ in range(MAX_CRC_RETRIES):
        try:
            lines = _read_raw(device_file)
        except (OSError, IOError):
            return None

        if len(lines) >= 2 and lines[0].strip().endswith("YES"):
            equals_pos = lines[1].find("t=")
            if equals_pos != -1:
                temp_string = lines[1][equals_pos + 2:]
                return float(temp_string) / 1000.0
        time.sleep(CRC_RETRY_DELAY)

    return None


def _mock_temps() -> dict:
    """Generate simulated temperatures for development."""
    hour = datetime.now().hour
    # Simulate: panel hot during day, inflow/outflow track with lag
    base_panel = 25 + 30 * max(0, 1 - abs(hour - 13) / 5) + random.uniform(-1, 1)
    base_inflow = 35 + random.uniform(-0.5, 0.5)
    base_outflow = 38 + random.uniform(-0.5, 0.5)
    return {
        "panel": round(base_panel, 2),
        "inflow": round(base_inflow, 2),
        "outflow": round(base_outflow, 2),
    }


def scan_available() -> list[str]:
    """Scan the 1-wire bus and return a list of DS18B20 device IDs.

    In mock mode, returns a few fake IDs for testing.
    """
    if MOCK_HARDWARE:
        return ["28-01191239b6b8", "28-01191246472a", "28-0119124690d2", "28-ffff00001111"]

    pattern = str(W1_DEVICES_DIR / "28-*")
    return sorted(Path(p).name for p in globmod.glob(pattern))


def read_all_raw(sensor_map: dict) -> dict:
    """Read all sensors and return raw temperatures (no calibration offset).

    Args:
        sensor_map: dict mapping role names to device IDs,
                    e.g. {"panel": "28-...", "inflow": "28-...", "outflow": "28-..."}

    Returns dict with keys: panel, inflow, outflow, timestamp.
    Values are None for any sensor that failed to read.
    """
    if MOCK_HARDWARE:
        temps = _mock_temps()
        temps["timestamp"] = datetime.now().isoformat()
        return temps

    result = {"timestamp": datetime.now().isoformat()}
    for name, device_id in sensor_map.items():
        device_file = W1_DEVICES_DIR / device_id / "w1_slave"
        result[name] = _read_temp(device_file)
    return result


def apply_offsets(raw_temps: dict, offsets: dict | None = None) -> dict:
    """Apply calibration offsets for display and control decisions.

    Returns a new dict with offset-adjusted temperatures.
    Raw temps that are None remain None.
    """
    if offsets is None:
        offsets = SENSOR_OFFSETS
    result = {"timestamp": raw_temps["timestamp"]}
    for name in ["panel", "inflow", "outflow"]:
        raw = raw_temps.get(name)
        if raw is not None:
            result[name] = round(raw + offsets.get(name, 0.0), 2)
        else:
            result[name] = None
    return result
