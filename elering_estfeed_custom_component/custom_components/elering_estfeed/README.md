# Elering Estfeed custom component

This is a starter Home Assistant custom component that currently:
- Fetches up to the latest 7 days of meter data from the Estfeed API
- Exposes `Grid import energy` as a `total_increasing` sensor only when the upstream payload includes a cumulative import reading
- Exposes `Monthly grid import energy` by summing import intervals from the latest month present in the fetched payload
- Exposes `Daily grid import energy` by summing import intervals from the latest day present in the fetched payload

## Install
Copy `custom_components/elering_estfeed` into your Home Assistant config directory.

## Configure
Restart Home Assistant, then add the integration from:
Settings -> Devices & Services -> Add Integration

## Required values
- Access token: capture from your logged-in browser session
- Meter EIC: your metering point identifier

## Important
The payload parser is still heuristic. It tries several likely row keys and cumulative-reading
fields, but you may still need to inspect the real JSON returned by Elering and adjust
`_parse_meter_snapshot()` in `api.py` to match your account's payload shape.
