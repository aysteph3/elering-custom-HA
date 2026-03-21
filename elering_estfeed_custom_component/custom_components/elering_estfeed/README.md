# Elering Estfeed custom component

This is a starter Home Assistant custom component that exposes:
- Grid import energy (kWh, total_increasing, when a cumulative meter reading is present in the upstream payload)
- Monthly grid import energy (kWh)
- Daily grid import energy (kWh)

## Install
Copy `custom_components/elering_estfeed` into your Home Assistant config directory.

## Configure
Restart Home Assistant, then add the integration from:
Settings -> Devices & Services -> Add Integration

## Required values
- Access token: capture from your logged-in browser session
- Meter EIC: your metering point identifier

## Important
You will probably need to inspect the real JSON payload returned by Elering and adjust
`_parse_meter_snapshot()` in `api.py`.
