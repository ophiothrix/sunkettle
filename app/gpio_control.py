"""GPIO relay control for pump and boiler."""

from datetime import datetime

from app.config import PUMP_PIN, BOILER_PIN, MOCK_HARDWARE


class GPIOController:
    """Controls pump and boiler relays with safety interlocks.

    Boiler is wired as Normally Closed (NC): pin OFF = boiler ON, pin ON = boiler OFF.
    Pump and boiler are mutually exclusive: pump ON forces boiler OFF.
    """

    def __init__(self):
        self._pump_on = False
        self._boiler_on = True  # NC relay defaults to ON
        self._pump_on_since: datetime | None = None
        self._boiler_on_since: datetime | None = datetime.now()

        if not MOCK_HARDWARE:
            from gpiozero import LED
            self._pump_pin = LED(PUMP_PIN)
            self._boiler_pin = LED(BOILER_PIN)
            # Initialize: pump off, boiler on (NC default)
            self._pump_pin.off()
            self._boiler_pin.off()  # off = NC closed = boiler ON
        else:
            self._pump_pin = None
            self._boiler_pin = None

    @property
    def pump_on(self) -> bool:
        return self._pump_on

    @property
    def boiler_on(self) -> bool:
        return self._boiler_on

    @property
    def pump_on_since(self) -> datetime | None:
        return self._pump_on_since

    @property
    def boiler_on_since(self) -> datetime | None:
        return self._boiler_on_since

    def set_pump(self, on: bool):
        """Set pump state. Turning pump ON forces boiler OFF."""
        if on and not self._pump_on:
            if not MOCK_HARDWARE:
                self._pump_pin.on()
            self._pump_on = True
            self._pump_on_since = datetime.now()
            # Mutual exclusion: pump ON forces boiler OFF
            self._set_boiler_direct(False)
        elif not on and self._pump_on:
            if not MOCK_HARDWARE:
                self._pump_pin.off()
            self._pump_on = False
            self._pump_on_since = None

    def set_boiler(self, on: bool):
        """Set boiler state. Turning boiler ON forces pump OFF."""
        if on and self._pump_on:
            self.set_pump(False)
        self._set_boiler_direct(on)

    def _set_boiler_direct(self, on: bool):
        """Internal: set boiler state with inverted logic for NC relay."""
        if on and not self._boiler_on:
            if not MOCK_HARDWARE:
                self._boiler_pin.off()  # NC relay: pin off = boiler ON
            self._boiler_on = True
            self._boiler_on_since = datetime.now()
        elif not on and self._boiler_on:
            if not MOCK_HARDWARE:
                self._boiler_pin.on()  # NC relay: pin on = boiler OFF
            self._boiler_on = False
            self._boiler_on_since = None

    def get_state(self) -> dict:
        """Return current relay states and timestamps."""
        return {
            "pump_on": self._pump_on,
            "boiler_on": self._boiler_on,
            "pump_on_since": self._pump_on_since.isoformat() if self._pump_on_since else None,
            "boiler_on_since": self._boiler_on_since.isoformat() if self._boiler_on_since else None,
        }
