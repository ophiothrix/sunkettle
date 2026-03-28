"""Application state management with SQLite persistence."""

import json
import aiosqlite
from datetime import datetime

from app.config import DB_PATH, DEFAULT_SCHEDULE, DEFAULT_THRESHOLDS, DEFAULT_ALERT_THRESHOLDS, DEFAULT_ALERTS_ENABLED, DEFAULT_SENSORS, SENSOR_OFFSETS, MANUAL_MODE_TIMEOUT


SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    dismissed INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""


class AppState:
    """Central application state — volatile in-memory data plus SQLite persistence."""

    def __init__(self):
        # Volatile (in-memory)
        self.temperatures: dict = {}        # latest raw readings
        self.calibrated_temps: dict = {}    # latest with offsets applied
        self.last_sensor_read: datetime | None = None
        self.sensor_failures: dict = {"panel": 0, "inflow": 0, "outflow": 0}
        self.controller_started: datetime = datetime.now()

        # Persisted (loaded from SQLite on init)
        self.mode: str = "auto"
        self.manual_mode_set_at: datetime | None = None
        self.manual_timeout: int = MANUAL_MODE_TIMEOUT
        self.schedule: dict = dict(DEFAULT_SCHEDULE)
        self.thresholds: dict = dict(DEFAULT_THRESHOLDS)
        self.alert_thresholds: dict = dict(DEFAULT_ALERT_THRESHOLDS)
        self.alerts_enabled: dict = dict(DEFAULT_ALERTS_ENABLED)
        self.sensor_map: dict = dict(DEFAULT_SENSORS)
        self.sensor_offsets: dict = dict(SENSOR_OFFSETS)

        # Tracking for alerts
        self.pump_on_temp_at_start: float | None = None

    async def init_db(self):
        """Initialize the database and load persisted settings."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.executescript(SCHEMA)
            await db.commit()
        await self._load_settings()

    async def _load_settings(self):
        """Load persisted settings from SQLite."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT key, value FROM settings") as cursor:
                async for row in cursor:
                    key, value = row[0], json.loads(row[1])
                    if key == "mode":
                        self.mode = value
                    elif key == "schedule":
                        self.schedule.update(value)
                    elif key == "thresholds":
                        self.thresholds.update(value)
                    elif key == "alert_thresholds":
                        self.alert_thresholds.update(value)
                    elif key == "alerts_enabled":
                        self.alerts_enabled.update(value)
                    elif key == "sensor_map":
                        self.sensor_map.update(value)
                    elif key == "sensor_offsets":
                        self.sensor_offsets.update(value)
                    elif key == "manual_timeout":
                        self.manual_timeout = value

    async def save_setting(self, key: str, value):
        """Persist a setting to SQLite."""
        now = datetime.now().isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                (key, json.dumps(value), now),
            )
            await db.commit()

    def update_temperatures(self, raw_temps: dict, calibrated_temps: dict):
        """Update the in-memory temperature state."""
        self.temperatures = raw_temps
        self.calibrated_temps = calibrated_temps
        self.last_sensor_read = datetime.now()

        # Track sensor failures
        for name in ["panel", "inflow", "outflow"]:
            if raw_temps.get(name) is None:
                self.sensor_failures[name] += 1
            else:
                self.sensor_failures[name] = 0

    async def set_mode(self, mode: str):
        """Switch between auto and manual mode."""
        self.mode = mode
        if mode == "manual":
            self.manual_mode_set_at = datetime.now()
        else:
            self.manual_mode_set_at = None
        await self.save_setting("mode", mode)

    def check_manual_timeout(self) -> bool:
        """Check if manual mode should revert to auto. Returns True if reverted."""
        if self.mode == "manual" and self.manual_mode_set_at:
            elapsed = (datetime.now() - self.manual_mode_set_at).total_seconds()
            if elapsed >= self.manual_timeout:
                self.mode = "auto"
                self.manual_mode_set_at = None
                return True
        return False

    async def add_alert(self, alert_type: str, message: str):
        """Store an alert in SQLite."""
        now = datetime.now().isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO alerts (type, message, created_at) VALUES (?, ?, ?)",
                (alert_type, message, now),
            )
            await db.commit()

    async def get_active_alerts(self) -> list[dict]:
        """Get undismissed alerts."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT id, type, message, created_at FROM alerts WHERE dismissed = 0 ORDER BY created_at DESC LIMIT 50"
            ) as cursor:
                return [dict(row) async for row in cursor]

    async def dismiss_alert(self, alert_id: int):
        """Dismiss an alert by ID."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE alerts SET dismissed = 1 WHERE id = ?", (alert_id,))
            await db.commit()

    def get_snapshot(self) -> dict:
        """Return a complete snapshot of current state for the API/SSE."""
        return {
            "temperatures": self.calibrated_temps,
            "raw_temperatures": self.temperatures,
            "pump_on": False,   # filled in by caller with gpio state
            "boiler_on": False,
            "mode": self.mode,
            "manual_timeout_remaining": self._manual_timeout_remaining(),
            "last_sensor_read": self.last_sensor_read.isoformat() if self.last_sensor_read else None,
            "schedule": self.schedule,
        }

    def _manual_timeout_remaining(self) -> int | None:
        """Seconds remaining before manual mode reverts to auto."""
        if self.mode != "manual" or not self.manual_mode_set_at:
            return None
        elapsed = (datetime.now() - self.manual_mode_set_at).total_seconds()
        remaining = self.manual_timeout - elapsed
        return max(0, int(remaining))
