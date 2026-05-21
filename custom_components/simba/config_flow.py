"""Config flow for SimBa."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CAPACITY_KWH,
    CONF_CHARGE_EFFICIENCY,
    CONF_DISCHARGE_EFFICIENCY,
    CONF_INITIAL_SOC_PERCENT,
    CONF_MAX_CHARGE_KW,
    CONF_MAX_DISCHARGE_KW,
    CONF_MAX_DT_SECONDS,
    CONF_MAX_SOC_PERCENT,
    CONF_MIN_SOC_PERCENT,
    CONF_POWER_SIGN,
    CONF_SOURCE_ENTITY,
    CONF_UPDATE_INTERVAL,
    DEFAULT_CAPACITY_KWH,
    DEFAULT_CHARGE_EFFICIENCY,
    DEFAULT_DISCHARGE_EFFICIENCY,
    DEFAULT_INITIAL_SOC_PERCENT,
    DEFAULT_MAX_CHARGE_KW,
    DEFAULT_MAX_DISCHARGE_KW,
    DEFAULT_MAX_DT_SECONDS,
    DEFAULT_MAX_SOC_PERCENT,
    DEFAULT_MIN_SOC_PERCENT,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    NAME,
    POWER_SIGN_OPTIONS,
    POWER_SIGN_POSITIVE_IMPORT,
)


def _number(min_value: float, max_value: float | None, step: float, unit: str | None):
    """Build a number selector."""
    config: dict[str, Any] = {
        "min": min_value,
        "step": step,
        "mode": selector.NumberSelectorMode.BOX,
    }
    if max_value is not None:
        config["max"] = max_value
    if unit is not None:
        config["unit_of_measurement"] = unit
    return selector.NumberSelector(selector.NumberSelectorConfig(**config))


def _config_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the config/options schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, NAME)): str,
            vol.Required(
                CONF_SOURCE_ENTITY,
                default=defaults.get(CONF_SOURCE_ENTITY),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class=SensorDeviceClass.POWER,
                )
            ),
            vol.Required(
                CONF_POWER_SIGN,
                default=defaults.get(CONF_POWER_SIGN, POWER_SIGN_POSITIVE_IMPORT),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=POWER_SIGN_OPTIONS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_CAPACITY_KWH,
                default=defaults.get(CONF_CAPACITY_KWH, DEFAULT_CAPACITY_KWH),
            ): _number(0.1, None, 0.1, "kWh"),
            vol.Required(
                CONF_CHARGE_EFFICIENCY,
                default=defaults.get(
                    CONF_CHARGE_EFFICIENCY, DEFAULT_CHARGE_EFFICIENCY
                ),
            ): _number(1.0, 100.0, 0.1, "%"),
            vol.Required(
                CONF_DISCHARGE_EFFICIENCY,
                default=defaults.get(
                    CONF_DISCHARGE_EFFICIENCY, DEFAULT_DISCHARGE_EFFICIENCY
                ),
            ): _number(1.0, 100.0, 0.1, "%"),
            vol.Required(
                CONF_MAX_CHARGE_KW,
                default=defaults.get(CONF_MAX_CHARGE_KW, DEFAULT_MAX_CHARGE_KW),
            ): _number(0.0, None, 0.1, "kW"),
            vol.Required(
                CONF_MAX_DISCHARGE_KW,
                default=defaults.get(CONF_MAX_DISCHARGE_KW, DEFAULT_MAX_DISCHARGE_KW),
            ): _number(0.0, None, 0.1, "kW"),
            vol.Required(
                CONF_INITIAL_SOC_PERCENT,
                default=defaults.get(
                    CONF_INITIAL_SOC_PERCENT, DEFAULT_INITIAL_SOC_PERCENT
                ),
            ): _number(0.0, 100.0, 1.0, "%"),
            vol.Required(
                CONF_MIN_SOC_PERCENT,
                default=defaults.get(CONF_MIN_SOC_PERCENT, DEFAULT_MIN_SOC_PERCENT),
            ): _number(0.0, 100.0, 1.0, "%"),
            vol.Required(
                CONF_MAX_SOC_PERCENT,
                default=defaults.get(CONF_MAX_SOC_PERCENT, DEFAULT_MAX_SOC_PERCENT),
            ): _number(0.0, 100.0, 1.0, "%"),
            vol.Required(
                CONF_UPDATE_INTERVAL,
                default=defaults.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            ): _number(1, 3600, 1, "s"),
            vol.Required(
                CONF_MAX_DT_SECONDS,
                default=defaults.get(CONF_MAX_DT_SECONDS, DEFAULT_MAX_DT_SECONDS),
            ): _number(1, 86400, 1, "s"),
        }
    )


def _validate_input(user_input: dict[str, Any]) -> str | None:
    """Validate user input and return an error key if invalid."""
    min_soc = float(user_input[CONF_MIN_SOC_PERCENT])
    max_soc = float(user_input[CONF_MAX_SOC_PERCENT])
    initial_soc = float(user_input[CONF_INITIAL_SOC_PERCENT])

    if min_soc > max_soc:
        return "invalid_soc_limits"
    if not min_soc <= initial_soc <= max_soc:
        return "invalid_initial_soc"
    if float(user_input[CONF_CHARGE_EFFICIENCY]) <= 0.0:
        return "invalid_efficiency"
    if float(user_input[CONF_DISCHARGE_EFFICIENCY]) <= 0.0:
        return "invalid_efficiency"
    return None


class SimBaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a SimBa config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return the options flow."""
        return SimBaOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            error = _validate_input(user_input)
            if error is None:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=_config_schema(user_input),
            errors=errors,
        )


class SimBaOptionsFlow(config_entries.OptionsFlow):
    """Handle SimBa options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            error = _validate_input(user_input)
            if error is None:
                return self.async_create_entry(title="", data=user_input)
            errors["base"] = error

        defaults = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_config_schema(defaults),
            errors=errors,
        )
