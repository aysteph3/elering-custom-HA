# Elering for Home Assistant

Elering is a Home Assistant custom integration that fetches meter consumption data through the Elering DataHub API using an authenticated browser session cookie header and a meter EIC. It exposes import-energy sensors for the latest available cumulative, monthly, and daily totals.

## Features

- Validates the supplied cookie header and meter EIC during config flow setup.
- Fetches up to the latest seven days of meter data from the upstream API.
- Provides three energy sensors:
  - `Grid import energy`
  - `Monthly grid import energy`
  - `Daily grid import energy`
- Keeps stable sensor names and unique ID suffixes for the energy entities.

## Repository layout

This repository is structured for HACS as a custom integration repository:

```text
custom_components/
  elering/
    __init__.py
    manifest.json
    ...
README.md
hacs.json
```

## Installation with HACS (custom repository)

1. Open HACS in Home Assistant.
2. Go to **Integrations**.
3. Open the three-dot menu and choose **Custom repositories**.
4. Add this repository URL.
5. Select **Integration** as the category.
6. Search for **Elering** and install it.
7. Restart Home Assistant.

Create a new GitHub release for version `0.2.0` so HACS can detect and offer the update. HACS can also install from the repository's default branch if needed.

## Configuration

After installation:

1. Go to **Settings -> Devices & Services**.
2. Click **Add Integration**.
3. Search for **Elering**.
4. Enter:
   - **Cookie header**: paste the full cookie string from your logged-in browser session, for example `JSESSIONID=...; XSRF-TOKEN=...`.
   - **Meter EIC**: your metering point identifier.

During setup, the integration validates the cookie header and meter EIC against the upstream API before creating the config entry.

## Authentication and session limitations

This integration currently depends on browser-derived session cookies for the upstream Elering DataHub session.

- Cookies may expire without warning.
- Session handling is controlled by Elering, not by Home Assistant.
- If authentication stops working, you can update the cookie header from the Home Assistant integration options without removing and re-adding the integration.
- Any upstream login-flow, API, or payload changes can require updates to this custom integration.

## Notes for maintainers

- `manifest.json` includes version `0.2.0`; publish a matching GitHub tag/release so HACS detects the update.
- For the best HACS experience, make the GitHub repository public and add releases later if you want versioned installs.
- Inclusion in the default HACS repositories is a separate review process; this repository is only prepared for HACS custom-repository usage.
