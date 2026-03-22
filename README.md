# Elektrilevi Meter for Home Assistant

Elektrilevi Meter is a Home Assistant custom integration that fetches meter consumption data through the Elering DataHub API using an authenticated browser access token and a meter EIC. It exposes import-energy sensors for the latest available cumulative, monthly, and daily totals.

## Features

- Validates the supplied access token and meter EIC during config flow setup.
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
  elektrilevi_meter/
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
6. Search for **Elektrilevi Meter** and install it.
7. Restart Home Assistant.

If you do not publish GitHub releases, HACS can still install from the repository's default branch.

## Configuration

After installation:

1. Go to **Settings -> Devices & Services**.
2. Click **Add Integration**.
3. Search for **Elektrilevi Meter**.
4. Enter:
   - **Access token**: paste only the token value from your logged-in browser session, without the `Bearer` prefix.
   - **Meter EIC**: your metering point identifier.

During setup, the integration validates the token and meter EIC against the upstream API before creating the config entry.

## Authentication and session limitations

This integration currently depends on a browser-derived access token for the upstream Elering DataHub session.

- Tokens may expire without warning.
- Session handling is controlled by Elektrilevi/Elering, not by Home Assistant.
- If authentication stops working, you may need to obtain a fresh token from a logged-in browser session and reconfigure the integration.
- Any upstream login-flow, API, or payload changes can require updates to this custom integration.

## Notes for maintainers

- `manifest.json` includes a version so the repository is ready for future GitHub tags/releases.
- For the best HACS experience, make the GitHub repository public and add releases later if you want versioned installs.
- Inclusion in the default HACS repositories is a separate review process; this repository is only prepared for HACS custom-repository usage.
