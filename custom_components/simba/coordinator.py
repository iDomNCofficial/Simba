"""Runtime coordinator for SimBa."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .battery import SimBaEngine
from .const import (
    CONF_POWER_SIGN,
    CONF_SOURCE_ENTITY,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    POWER_SIGN_POSITIVE_EXPORT,
    STATUS_PAUSED,
    signal_update,
)

_LOGGER = logging.getLogger(__name__)


class SimBaRuntime:
    """Keep a SimBa engine connected to Home Assistant."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize runtime state."""
        self.hass = hass
        self.entry = entry
        self.config = {**entry.data, **entry.options}
        self.engine = SimBaEngine.from_config(self.config)
        self.paused = False
        self._last_update_ts: float | None = None
        self._unsub_interval = None
        self._unsub_update_listener = None

    @property
    def signal_update(self) -> str:
        """Return this entry's dispatcher signal."""
        return signal_update(self.entry.entry_id)

    async def async_start(self) -> None:
        """Start periodic simulation ticks."""
        interval = int(self.config.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL))
        self._unsub_interval = async_track_time_interval(
            self.hass,
            self._async_tick,
            timedelta(seconds=max(interval, 1)),
        )

    async def async_unload(self) -> None:
        """Stop periodic work."""
        if self._unsub_interval is not None:
            self._unsub_interval()
            self._unsub_interval = None
        if self._unsub_update_listener is not None:
            self._unsub_update_listener()
            self._unsub_update_listener = None

    def set_update_listener(self, unsub_update_listener) -> None:
        """Store the config entry update listener unsubscribe callback."""
        self._unsub_update_listener = unsub_update_listener

    def set_paused(self, paused: bool) -> None:
        """Pause or resume the simulation."""
        self.paused = paused
        if paused:
            self.engine.status = STATUS_PAUSED
            self.engine.battery_power_kw = 0.0
        self.async_write_state()

    def set_soc_percent(self, charge_percent: float) -> None:
        """Set state of charge by percentage."""
        self.engine.set_charge_percent(charge_percent)
        self.async_write_state()

    def set_soc_kwh(self, charge_kwh: float) -> None:
        """Set state of charge by stored energy."""
        self.engine.set_charge_kwh(charge_kwh)
        self.async_write_state()

    def reset_energy_counters(self) -> None:
        """Reset simulated grid energy counters."""
        self.engine.reset_energy_counters()
        self.async_write_state()

    @callback
    def async_write_state(self) -> None:
        """Notify entities that runtime state changed."""
        async_dispatcher_send(self.hass, self.signal_update)

    @callback
    def _async_tick(self, now: datetime) -> None:
        """Run one simulation tick."""
        now_ts = now.timestamp()
        if self._last_update_ts is None:
            self._last_update_ts = now_ts
            self.async_write_state()
            return

        dt_seconds = max(now_ts - self._last_update_ts, 0.0)
        self._last_update_ts = now_ts

        state = self.hass.states.get(self.config[CONF_SOURCE_ENTITY])
        if state is None or state.state in {"unknown", "unavailable"}:
            self.engine.mark_source_unavailable()
            self.async_write_state()
            return

        try:
            source_power_kw = self._state_to_kw(state.state, state.attributes)
        except (TypeError, ValueError):
            _LOGGER.debug("Could not parse source power state: %s", state.state)
            self.engine.mark_source_unavailable()
            self.async_write_state()
            return

        if self.config.get(CONF_POWER_SIGN) == POWER_SIGN_POSITIVE_EXPORT:
            source_power_kw *= -1.0

        self.engine.tick(source_power_kw, dt_seconds, self.paused)
        self.async_write_state()

    def _state_to_kw(self, state: str, attributes: dict) -> float:
        """Convert a source sensor state to kW."""
        value = float(state)
        unit = attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        if unit == UnitOfPower.WATT or unit == "W":
            return value / 1000.0
        if unit == UnitOfPower.KILO_WATT or unit == "kW":
            return value

        unit_text = str(unit or "").lower()
        if unit_text in {"w", "watt", "watts"}:
            return value / 1000.0
        if unit_text in {"kw", "kilowatt", "kilowatts"}:
            return value

        _LOGGER.debug(
            "Unknown source power unit %r for %s; assuming W",
            unit,
            self.config[CONF_SOURCE_ENTITY],
        )
        return value / 1000.0


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload a config entry after options changes."""
    await hass.config_entries.async_reload(entry.entry_id)
