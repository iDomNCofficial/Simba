"""Constants for the SimBa integration."""

from homeassistant.const import Platform

DOMAIN = "simba"
NAME = "SimBa"
VERSION = "0.1.0"

PLATFORMS = [Platform.SENSOR, Platform.SWITCH]

CONF_SOURCE_ENTITY = "source_entity"
CONF_POWER_SIGN = "power_sign"
CONF_CAPACITY_KWH = "capacity_kwh"
CONF_CHARGE_EFFICIENCY = "charge_efficiency"
CONF_DISCHARGE_EFFICIENCY = "discharge_efficiency"
CONF_MAX_CHARGE_KW = "max_charge_kw"
CONF_MAX_DISCHARGE_KW = "max_discharge_kw"
CONF_INITIAL_SOC_PERCENT = "initial_soc_percent"
CONF_MIN_SOC_PERCENT = "min_soc_percent"
CONF_MAX_SOC_PERCENT = "max_soc_percent"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_MAX_DT_SECONDS = "max_dt_seconds"

POWER_SIGN_POSITIVE_IMPORT = "positive_import"
POWER_SIGN_POSITIVE_EXPORT = "positive_export"
POWER_SIGN_OPTIONS = [
    POWER_SIGN_POSITIVE_IMPORT,
    POWER_SIGN_POSITIVE_EXPORT,
]

DEFAULT_CAPACITY_KWH = 13.5
DEFAULT_CHARGE_EFFICIENCY = 95.0
DEFAULT_DISCHARGE_EFFICIENCY = 95.0
DEFAULT_MAX_CHARGE_KW = 5.0
DEFAULT_MAX_DISCHARGE_KW = 5.0
DEFAULT_INITIAL_SOC_PERCENT = 50.0
DEFAULT_MIN_SOC_PERCENT = 0.0
DEFAULT_MAX_SOC_PERCENT = 100.0
DEFAULT_UPDATE_INTERVAL = 5
DEFAULT_MAX_DT_SECONDS = 60

STATUS_CHARGING = "charging"
STATUS_DISCHARGING = "discharging"
STATUS_IDLE = "idle"
STATUS_PAUSED = "paused"
STATUS_FULL = "full"
STATUS_EMPTY = "empty"
STATUS_SOURCE_UNAVAILABLE = "source_unavailable"
STATUS_OPTIONS = [
    STATUS_CHARGING,
    STATUS_DISCHARGING,
    STATUS_IDLE,
    STATUS_PAUSED,
    STATUS_FULL,
    STATUS_EMPTY,
    STATUS_SOURCE_UNAVAILABLE,
]

SERVICE_SET_SOC = "set_soc"
SERVICE_RESET_ENERGY_COUNTERS = "reset_energy_counters"

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_CHARGE_PERCENT = "charge_percent"
ATTR_CHARGE_KWH = "charge_kwh"


def signal_update(entry_id: str) -> str:
    """Return the dispatcher signal for an entry."""
    return f"{DOMAIN}_{entry_id}_update"
