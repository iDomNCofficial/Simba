"""Sensors for SimBa."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType

from .battery import SimBaEngine
from .const import DOMAIN, STATUS_OPTIONS
from .coordinator import SimBaRuntime

RESTORE_CHARGE_KWH = "charge_kwh"
RESTORE_IMPORT_ENERGY = "import_energy"
RESTORE_EXPORT_ENERGY = "export_energy"


@dataclass(frozen=True, kw_only=True)
class SimBaSensorDescription(SensorEntityDescription):
    """Describe a SimBa sensor."""

    value_fn: Callable[[SimBaEngine], StateType]
    restore_key: str | None = None


SENSORS: tuple[SimBaSensorDescription, ...] = (
    SimBaSensorDescription(
        key="battery_charge_kwh",
        name="Battery charge",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda engine: round(engine.charge_kwh, 3),
        restore_key=RESTORE_CHARGE_KWH,
    ),
    SimBaSensorDescription(
        key="battery_charge_percent",
        name="Battery charge percent",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda engine: round(engine.charge_percent, 0),
    ),
    SimBaSensorDescription(
        key="battery_power",
        name="Battery power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda engine: round(engine.battery_power_kw, 3),
    ),
    SimBaSensorDescription(
        key="simulated_grid_power",
        name="Simulated grid power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda engine: round(engine.simulated_grid_power_kw, 3),
    ),
    SimBaSensorDescription(
        key="simulated_grid_import_power",
        name="Simulated grid import power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda engine: round(engine.simulated_import_power_kw, 3),
    ),
    SimBaSensorDescription(
        key="simulated_grid_export_power",
        name="Simulated grid export power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda engine: round(engine.simulated_export_power_kw, 3),
    ),
    SimBaSensorDescription(
        key="simulated_grid_import_energy",
        name="Simulated grid import energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_fn=lambda engine: round(engine.simulated_import_energy_kwh, 3),
        restore_key=RESTORE_IMPORT_ENERGY,
    ),
    SimBaSensorDescription(
        key="simulated_grid_export_energy",
        name="Simulated grid export energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_fn=lambda engine: round(engine.simulated_export_energy_kwh, 3),
        restore_key=RESTORE_EXPORT_ENERGY,
    ),
    SimBaSensorDescription(
        key="status",
        name="Status",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda engine: engine.status,
    ),
    SimBaSensorDescription(
        key="time_estimate",
        name="Time estimate",
        value_fn=lambda engine: engine.time_estimate,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SimBa sensors."""
    runtime: SimBaRuntime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(SimBaSensor(runtime, description) for description in SENSORS)


class SimBaSensor(RestoreEntity, SensorEntity):
    """A SimBa sensor."""

    entity_description: SimBaSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        runtime: SimBaRuntime,
        description: SimBaSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        self.runtime = runtime
        self.entity_description = description
        self._attr_unique_id = f"{runtime.entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, runtime.entry.entry_id)},
            "name": runtime.entry.title,
            "manufacturer": "SimBa",
        }
        if description.key == "status":
            self._attr_options = STATUS_OPTIONS

    async def async_added_to_hass(self) -> None:
        """Restore state and subscribe for runtime updates."""
        await super().async_added_to_hass()
        await self._async_restore_state()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.runtime.signal_update,
                self._handle_runtime_update,
            )
        )

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.runtime.engine)

    @callback
    def _handle_runtime_update(self) -> None:
        """Handle runtime update."""
        self.async_write_ha_state()

    async def _async_restore_state(self) -> None:
        """Restore persisted runtime values from selected sensors."""
        restore_key = self.entity_description.restore_key
        if restore_key is None:
            return

        last_state = await self.async_get_last_state()
        if last_state is None or last_state.state in {"unknown", "unavailable"}:
            return

        try:
            value = float(last_state.state)
        except (TypeError, ValueError):
            return

        if restore_key == RESTORE_CHARGE_KWH:
            self.runtime.engine.set_charge_kwh(value)
        elif restore_key == RESTORE_IMPORT_ENERGY:
            self.runtime.engine.simulated_import_energy_kwh = max(value, 0.0)
        elif restore_key == RESTORE_EXPORT_ENERGY:
            self.runtime.engine.simulated_export_energy_kwh = max(value, 0.0)
