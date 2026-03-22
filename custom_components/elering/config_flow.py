"""Config flow for Elering."""

from __future__ import annotations

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EleringApiClient, EleringApiError, EleringAuthenticationError
from .const import CONF_ACCESS_TOKEN, CONF_METER_EIC, DOMAIN


async def async_validate_input(hass, user_input) -> str:
    """Validate the provided credentials against the upstream API."""
    client = EleringApiClient(
        session=async_get_clientsession(hass),
        access_token=user_input[CONF_ACCESS_TOKEN],
        meter_eic=user_input[CONF_METER_EIC],
    )
    await client.async_fetch_meter_data()
    return f"Elering {user_input[CONF_METER_EIC]}"


class EleringConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elering."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                title = await async_validate_input(self.hass, user_input)
            except EleringAuthenticationError:
                errors["base"] = "invalid_auth"
            except (EleringApiError, aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_METER_EIC])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=title, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_ACCESS_TOKEN): str,
                vol.Required(CONF_METER_EIC): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
