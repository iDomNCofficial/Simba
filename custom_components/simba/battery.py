"""Pure battery simulation engine for SimBa."""

from __future__ import annotations

from dataclasses import dataclass

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
    DEFAULT_CAPACITY_KWH,
    DEFAULT_CHARGE_EFFICIENCY,
    DEFAULT_DISCHARGE_EFFICIENCY,
    DEFAULT_INITIAL_SOC_PERCENT,
    DEFAULT_MAX_CHARGE_KW,
    DEFAULT_MAX_DISCHARGE_KW,
    DEFAULT_MAX_DT_SECONDS,
    DEFAULT_MAX_SOC_PERCENT,
    DEFAULT_MIN_SOC_PERCENT,
    STATUS_CHARGING,
    STATUS_DISCHARGING,
    STATUS_EMPTY,
    STATUS_FULL,
    STATUS_IDLE,
    STATUS_PAUSED,
STATUS_SOURCE_UNAVAILABLE,
)

TIME_ESTIMATE_THRESHOLD_KW = 0.05


def clamp(value: float, low: float, high: float) -> float:
    """Clamp a value into a closed interval."""
    return max(low, min(high, value))


@dataclass(slots=True)
class SimBaEngine:
    """Simulate a battery from an instantaneous net grid power."""

    capacity_kwh: float
    charge_efficiency: float
    discharge_efficiency: float
    max_charge_kw: float
    max_discharge_kw: float
    min_soc_percent: float
    max_soc_percent: float
    max_dt_seconds: float
    charge_kwh: float
    simulated_import_energy_kwh: float = 0.0
    simulated_export_energy_kwh: float = 0.0
    battery_power_kw: float = 0.0
    simulated_grid_power_kw: float = 0.0
    simulated_import_power_kw: float = 0.0
    simulated_export_power_kw: float = 0.0
    status: str = STATUS_IDLE

    @classmethod
    def from_config(cls, config: dict) -> "SimBaEngine":
        """Create an engine from Home Assistant config data."""
        capacity_kwh = float(config.get(CONF_CAPACITY_KWH, DEFAULT_CAPACITY_KWH))
        initial_soc_percent = float(
            config.get(CONF_INITIAL_SOC_PERCENT, DEFAULT_INITIAL_SOC_PERCENT)
        )
        min_soc_percent = float(
            config.get(CONF_MIN_SOC_PERCENT, DEFAULT_MIN_SOC_PERCENT)
        )
        max_soc_percent = float(
            config.get(CONF_MAX_SOC_PERCENT, DEFAULT_MAX_SOC_PERCENT)
        )
        charge_kwh = capacity_kwh * clamp(initial_soc_percent, 0.0, 100.0) / 100.0

        engine = cls(
            capacity_kwh=capacity_kwh,
            charge_efficiency=float(
                config.get(CONF_CHARGE_EFFICIENCY, DEFAULT_CHARGE_EFFICIENCY)
            )
            / 100.0,
            discharge_efficiency=float(
                config.get(CONF_DISCHARGE_EFFICIENCY, DEFAULT_DISCHARGE_EFFICIENCY)
            )
            / 100.0,
            max_charge_kw=float(config.get(CONF_MAX_CHARGE_KW, DEFAULT_MAX_CHARGE_KW)),
            max_discharge_kw=float(
                config.get(CONF_MAX_DISCHARGE_KW, DEFAULT_MAX_DISCHARGE_KW)
            ),
            min_soc_percent=min_soc_percent,
            max_soc_percent=max_soc_percent,
            max_dt_seconds=float(
                config.get(CONF_MAX_DT_SECONDS, DEFAULT_MAX_DT_SECONDS)
            ),
            charge_kwh=charge_kwh,
        )
        engine._clamp_charge()
        return engine

    @property
    def min_charge_kwh(self) -> float:
        """Return the minimum allowed stored energy."""
        return self.capacity_kwh * self.min_soc_percent / 100.0

    @property
    def max_charge_kwh(self) -> float:
        """Return the maximum allowed stored energy."""
        return self.capacity_kwh * self.max_soc_percent / 100.0

    @property
    def charge_percent(self) -> float:
        """Return current state of charge as a percentage."""
        if self.capacity_kwh <= 0:
            return 0.0
        return 100.0 * self.charge_kwh / self.capacity_kwh

    @property
    def time_estimate(self) -> str:
        """Return a human-readable charge/discharge time estimate."""
        if (
            self.battery_power_kw > TIME_ESTIMATE_THRESHOLD_KW
            and self.charge_kwh < self.max_charge_kwh
        ):
            remaining_kwh = max(self.max_charge_kwh - self.charge_kwh, 0.0)
            stored_power_kw = self.battery_power_kw * self.charge_efficiency
            if stored_power_kw > 0.0:
                return (
                    "Temps de charge restant : "
                    f"{self._format_hours(remaining_kwh / stored_power_kw)}"
                )

        if (
            self.battery_power_kw < -TIME_ESTIMATE_THRESHOLD_KW
            and self.charge_kwh > self.min_charge_kwh
        ):
            usable_kwh = max(self.charge_kwh - self.min_charge_kwh, 0.0)
            internal_discharge_kw = (
                -self.battery_power_kw / self.discharge_efficiency
                if self.discharge_efficiency > 0.0
                else 0.0
            )
            if internal_discharge_kw > 0.0:
                return f"Autonomie : {self._format_hours(usable_kwh / internal_discharge_kw)}"

        if self._is_full():
            return "Charge terminee"
        if self._is_empty():
            return "Batterie vide"
        return "Batterie au repos"

    def set_charge_kwh(self, charge_kwh: float) -> None:
        """Set the battery charge in kWh."""
        self.charge_kwh = float(charge_kwh)
        self._clamp_charge()

    def set_charge_percent(self, charge_percent: float) -> None:
        """Set the battery charge in percent."""
        self.charge_kwh = self.capacity_kwh * float(charge_percent) / 100.0
        self._clamp_charge()

    def reset_energy_counters(self) -> None:
        """Reset simulated grid energy counters."""
        self.simulated_import_energy_kwh = 0.0
        self.simulated_export_energy_kwh = 0.0

    def mark_source_unavailable(self) -> None:
        """Freeze simulation when the source sensor cannot be used."""
        self.battery_power_kw = 0.0
        self.simulated_grid_power_kw = 0.0
        self.simulated_import_power_kw = 0.0
        self.simulated_export_power_kw = 0.0
        self.status = STATUS_SOURCE_UNAVAILABLE

    def tick(self, grid_power_kw: float, dt_seconds: float, paused: bool = False) -> None:
        """Advance the simulation.

        grid_power_kw is normalized so positive means grid import and negative
        means grid export. battery_power_kw is positive while charging and
        negative while discharging.
        """
        self._clamp_charge()
        dt_seconds = clamp(float(dt_seconds), 0.0, float(self.max_dt_seconds))

        if paused:
            self._set_pass_through_power(grid_power_kw)
            self.status = STATUS_PAUSED
            return

        hours = dt_seconds / 3600.0
        if hours <= 0.0:
            self._set_pass_through_power(grid_power_kw)
            self._set_idle_status()
            return

        battery_power_kw = 0.0
        simulated_grid_power_kw = grid_power_kw

        if grid_power_kw < 0.0:
            surplus_kw = -grid_power_kw
            charge_headroom_kwh = max(self.max_charge_kwh - self.charge_kwh, 0.0)
            max_input_by_capacity_kw = (
                charge_headroom_kwh / self.charge_efficiency / hours
                if self.charge_efficiency > 0.0
                else 0.0
            )
            charge_power_kw = min(
                surplus_kw,
                self.max_charge_kw,
                max_input_by_capacity_kw,
            )

            if charge_power_kw > 0.0:
                self.charge_kwh += charge_power_kw * hours * self.charge_efficiency
                battery_power_kw = charge_power_kw
                simulated_grid_power_kw = grid_power_kw + charge_power_kw
                self.status = STATUS_CHARGING
            else:
                self.status = STATUS_FULL if self._is_full() else STATUS_IDLE

        elif grid_power_kw > 0.0:
            import_kw = grid_power_kw
            discharge_available_kwh = max(self.charge_kwh - self.min_charge_kwh, 0.0)
            max_output_by_capacity_kw = (
                discharge_available_kwh * self.discharge_efficiency / hours
            )
            discharge_power_kw = min(
                import_kw,
                self.max_discharge_kw,
                max_output_by_capacity_kw,
            )

            if discharge_power_kw > 0.0:
                self.charge_kwh -= discharge_power_kw * hours / self.discharge_efficiency
                battery_power_kw = -discharge_power_kw
                simulated_grid_power_kw = grid_power_kw - discharge_power_kw
                self.status = STATUS_DISCHARGING
            else:
                self.status = STATUS_EMPTY if self._is_empty() else STATUS_IDLE

        else:
            self.status = STATUS_IDLE

        self._clamp_charge()
        self.battery_power_kw = battery_power_kw
        self.simulated_grid_power_kw = simulated_grid_power_kw
        self.simulated_import_power_kw = max(simulated_grid_power_kw, 0.0)
        self.simulated_export_power_kw = max(-simulated_grid_power_kw, 0.0)
        self.simulated_import_energy_kwh += self.simulated_import_power_kw * hours
        self.simulated_export_energy_kwh += self.simulated_export_power_kw * hours

        if battery_power_kw == 0.0 and simulated_grid_power_kw == 0.0:
            self._set_idle_status()

    def _set_pass_through_power(self, grid_power_kw: float) -> None:
        """Set instantaneous outputs with no battery action."""
        self.battery_power_kw = 0.0
        self.simulated_grid_power_kw = grid_power_kw
        self.simulated_import_power_kw = max(grid_power_kw, 0.0)
        self.simulated_export_power_kw = max(-grid_power_kw, 0.0)

    def _set_idle_status(self) -> None:
        """Set an idle/full/empty status according to current charge."""
        if self._is_full():
            self.status = STATUS_FULL
        elif self._is_empty():
            self.status = STATUS_EMPTY
        else:
            self.status = STATUS_IDLE

    def _clamp_charge(self) -> None:
        """Clamp stored energy to configured battery limits."""
        self.charge_kwh = clamp(self.charge_kwh, self.min_charge_kwh, self.max_charge_kwh)

    def _is_full(self) -> bool:
        """Return true when the battery is effectively full."""
        return self.charge_kwh >= self.max_charge_kwh - 0.000001

    def _is_empty(self) -> bool:
        """Return true when the battery is effectively empty."""
        return self.charge_kwh <= self.min_charge_kwh + 0.000001

    @staticmethod
    def _format_hours(hours: float) -> str:
        """Format a duration in hours as HH:MM."""
        total_minutes = int(round(max(hours, 0.0) * 60.0))
        return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"
