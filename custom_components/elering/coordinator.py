"""Coordinator for Elering."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EleringAuthenticationError, EleringAuthorizationError
from .const import DEFAULT_SCAN_INTERVAL_MINUTES, DOMAIN

_LOGGER = logging.getLogger(__name__)


class EleringCoordinator(DataUpdateCoordinator):
    """Handle fetching data from the API."""

    def __init__(self, hass, client):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES),
        )
        self.client = client

    async def _async_update_data(self):
        """Fetch the latest data."""
        try:
            return await self.client.async_fetch_meter_data()
        except EleringAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                "Elering client credentials are invalid or misconfigured. Update client_id/client_secret in integration options."
            ) from err
        except EleringAuthorizationError as err:
            raise UpdateFailed(
                "Elering token is valid but Datahub denied access to the requested meter. "
                "Verify Datahub role/permissions and market-participant authorization."
            ) from err
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Elering DataHub: {err}") from err
