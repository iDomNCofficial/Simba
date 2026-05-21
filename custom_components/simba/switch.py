"""Switches for SimBa."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import SimBaRuntime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SimBa switches."""
    runtime: SimBaRuntime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SimBaPauseSwitch(runtime)])


class SimBaPauseSwitch(RestoreEntity, SwitchEntity):
    """Pause or resume the SimBa simulation."""

    _attr_has_entity_name = True
    _attr_name = "Pause"
    _attr_icon = "mdi:pause"

    def __init__(self, runtime: SimBaRuntime) -> None:
        """Initialize the switch."""
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.entry.entry_id}_pause"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, runtime.entry.entry_id)},
            "name": runtime.entry.title,
            "manufacturer": "SimBa",
        }

    async def async_added_to_hass(self) -> None:
        """Restore switch state and subscribe for runtime updates."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self.runtime.paused = last_state.state == "on"

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.runtime.signal_update,
                self._handle_runtime_update,
            )
        )

    @property
    def is_on(self) -> bool:
        """Return true if the simulation is paused."""
        return self.runtime.paused

    async def async_turn_on(self, **kwargs) -> None:
        """Pause the simulation."""
        self.runtime.set_paused(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Resume the simulation."""
        self.runtime.set_paused(False)

    @callback
    def _handle_runtime_update(self) -> None:
        """Handle runtime update."""
        self.async_write_ha_state()
