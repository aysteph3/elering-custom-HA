# Elering for Home Assistant

Elering is a Home Assistant custom integration that fetches meter consumption data through the Elering DataHub API using Client Portal API credentials (`client_id` + `client_secret`) and a meter EIC. It exposes import-energy sensors for the latest available cumulative, monthly, and daily totals.

## Features

- Validates the supplied OAuth2 client credentials and meter EIC during config flow setup.
- Obtains an OAuth2 access token using client-credentials flow and uses bearer auth for DataHub requests.
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

Create a new GitHub release for version `0.4.0` so HACS can detect and offer the update. HACS can also install from the repository's default branch if needed.

### Troubleshooting: `Failed to download zipball`

If HACS shows:

`[<Integration aysteph3/elering-custom-HA>] Failed to download zipball`

check the following:

1. The repository URL in **HACS -> Custom repositories** is exactly `https://github.com/aysteph3/elering-custom-HA`.
2. The repository is public, and the default branch exists.
3. Home Assistant can reach GitHub (no DNS/proxy/firewall blocks).
4. You are not currently rate-limited by GitHub API (set a GitHub token in HACS settings if needed).
5. Remove and re-add the custom repository in HACS, then restart Home Assistant.

## Configuration

After installation:

1. Go to **Settings -> Devices & Services**.
2. Click **Add Integration**.
3. Search for **Elering**.
4. Enter:
   - **Client ID**: from Elering Client Portal API key setup.
   - **Client secret**: from Elering Client Portal API key setup.
   - **Meter EIC**: your metering point identifier.

During setup, the integration validates credentials by obtaining an access token and calling the meter-data endpoint.

## Authentication and token handling

This integration uses OAuth2 client credentials:

- The user creates API credentials in Elering Client Portal.
- The integration requests access tokens from Keycloak using `grant_type=client_credentials`.
- Access tokens are cached in memory and renewed by requesting a new token when needed.
- If authentication fails (for example `401`/`403`), update `client_id`/`client_secret` from Home Assistant integration options.
- No browser-cookie/JWT copy flow is used.

## Notes for maintainers

- `manifest.json` includes version `0.4.0`; publish a matching GitHub tag/release so HACS detects the update.
- For the best HACS experience, make the GitHub repository public and add releases later if you want versioned installs.
- Inclusion in the default HACS repositories is a separate review process; this repository is only prepared for HACS custom-repository usage.
