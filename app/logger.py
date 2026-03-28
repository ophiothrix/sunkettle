"""Temperature log file writer — backwards compatible with existing R scripts.

Writes tab-separated: datetime\tPanel\tInflow\tOutflow
Panel column contains RAW temperature (no -6 offset) — R scripts apply offset themselves.
"""

from datetime import datetime
from pathlib import Path

from app.config import LOG_DIR


class TemperatureLogger:
    """Writes temperature readings to daily log files."""

    def __init__(self):
        self._current_date: str | None = None
        self._file = None

    def write(self, raw_temps: dict):
        """Write a single log line with raw (uncalibrated) temperatures.

        Args:
            raw_temps: dict with keys panel, inflow, outflow, timestamp.
                       Values may be None for failed reads (skipped).
        """
        panel = raw_temps.get("panel")
        inflow = raw_temps.get("inflow")
        outflow = raw_temps.get("outflow")

        # Skip if any sensor failed
        if panel is None or inflow is None or outflow is None:
            return

        today = datetime.now().strftime("%Y-%m-%d")

        # Rotate file on date change
        if today != self._current_date:
            self.close()
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            log_path = LOG_DIR / f"{today}.log"
            self._file = open(log_path, "a")
            self._current_date = today

        timestamp = datetime.now()
        line = f"{timestamp}\t{panel:.2f}\t{inflow:.2f}\t{outflow:.2f}\n"
        self._file.write(line)
        self._file.flush()

    def close(self):
        """Close the current log file."""
        if self._file:
            self._file.close()
            self._file = None
            self._current_date = None
