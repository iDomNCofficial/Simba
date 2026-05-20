"""SimBa integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import HomeAssistantError

from .const import (
    ATTR_CHARGE_KWH,
    ATTR_CHARGE_PERCENT,
    ATTR_CONFIG_ENTRY_ID,
    DOMAIN,
    PLATFORMS,
    SERVICE_RESET_ENERGY_COUNTERS,
    SERVICE_SET_SOC,
)
from .coordinator import SimBaRuntime, async_reload_entry

_LOGGER = logging.getLogger(__name__)

SET_SOC_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(ATTR_CHARGE_PERCENT): vol.All(
            vol.Coerce(float), vol.Range(min=0.0, max=100.0)
        ),
        vol.Optional(ATTR_CHARGE_KWH): vol.All(vol.Coerce(float), vol.Range(min=0.0)),
    }
)

RESET_COUNTERS_SCHEMA = vol.Schema({vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string})


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up SimBa services."""
    hass.data.setdefault(DOMAIN, {})

    async def async_set_soc(call: ServiceCall) -> None:
        """Set state of charge on one or all SimBa batteries."""
        has_percent = ATTR_CHARGE_PERCENT in call.data
        has_kwh = ATTR_CHARGE_KWH in call.data
        if has_percent == has_kwh:
            raise HomeAssistantError(
                f"Provide exactly one of {ATTR_CHARGE_PERCENT} or {ATTR_CHARGE_KWH}"
            )

        for runtime in _target_runtimes(hass, call):
            if has_percent:
                runtime.set_soc_percent(call.data[ATTR_CHARGE_PERCENT])
            else:
                runtime.set_soc_kwh(call.data[ATTR_CHARGE_KWH])

    async def async_reset_energy_counters(call: ServiceCall) -> None:
        """Reset simulated import/export energy counters."""
        for runtime in _target_runtimes(hass, call):
            runtime.reset_energy_counters()

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SOC,
        async_set_soc,
        schema=SET_SOC_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_ENERGY_COUNTERS,
        async_reset_energy_counters,
        schema=RESET_COUNTERS_SCHEMA,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SimBa from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    runtime = SimBaRuntime(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = runtime

    runtime.set_update_listener(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await runtime.async_start()
    _LOGGER.debug("SimBa entry %s started", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a SimBa config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    runtime: SimBaRuntime | None = hass.data[DOMAIN].get(entry.entry_id)
    if runtime is not None:
        await runtime.async_unload()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


def _target_runtimes(hass: HomeAssistant, call: ServiceCall) -> list[SimBaRuntime]:
    """Resolve service targets."""
    entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
    runtimes: dict[str, SimBaRuntime] = hass.data.get(DOMAIN, {})

    if entry_id:
        runtime = runtimes.get(entry_id)
        if runtime is None:
            raise HomeAssistantError(f"No SimBa config entry found for {entry_id}")
        return [runtime]

    return list(runtimes.values())
