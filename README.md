# SimBa

SimBa is a Home Assistant custom integration that simulates a battery from an
instantaneous net grid power sensor.

The source sensor must represent net grid power. SimBa normalizes it internally
so positive means import and negative means export. The sign convention is
configurable in the UI.

## Features

- Config flow UI.
- Battery size, charge efficiency, discharge efficiency, max charge power and
  max discharge power.
- Minimum and maximum state of charge.
- Periodic simulation from instantaneous power.
- Maximum integrated duration to avoid large jumps after restart or source
  sensor downtime.
- Restored state of charge and simulated energy counters.
- Pause switch.
- Services to set state of charge and reset counters.

## Entities

SimBa creates these entities for each configured battery:

- Battery charge in kWh.
- Battery charge in percent.
- Battery power in kW. Positive means charging, negative means discharging.
- Simulated grid power in kW. Positive means import, negative means export.
- Simulated grid import power in kW.
- Simulated grid export power in kW.
- Simulated grid import energy in kWh.
- Simulated grid export energy in kWh.
- Status.
- Time estimate.
- Pause switch.

## Installation

Copy this folder to:

```text
custom_components/simba
```

Restart Home Assistant, then add the integration from:

```text
Settings > Devices & services > Add integration > SimBa
```

For a HACS repository, keep this integration under
`custom_components/simba` and place `hacs.json` at the repository root.

## Defaults

- Battery size: 13.5 kWh
- Charge efficiency: 95 %
- Discharge efficiency: 95 %
- Maximum charge power: 5 kW
- Maximum discharge power: 5 kW
- Initial charge: 50 %
- Minimum charge: 0 %
- Maximum charge: 100 %
- Update interval: 5 s
- Maximum integrated duration: 60 s
