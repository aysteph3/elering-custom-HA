"""Config flow for Elering."""

from __future__ import annotations

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EleringApiClient, EleringApiError, EleringAuthenticationError
from .const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_METER_EIC, DOMAIN


async def async_validate_input(hass, user_input) -> str:
    """Validate the provided credentials against the upstream API."""
    client = EleringApiClient(
        session=async_get_clientsession(hass),
        client_id=user_input[CONF_CLIENT_ID],
        client_secret=user_input[CONF_CLIENT_SECRET],
        meter_eic=user_input[CONF_METER_EIC],
    )
    await client.async_fetch_meter_data()
    return f"Elering {user_input[CONF_METER_EIC]}"


class EleringConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elering."""

    VERSION = 4

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

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                    vol.Required(CONF_METER_EIC): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return EleringOptionsFlow(config_entry)


class EleringOptionsFlow(config_entries.OptionsFlow):
    """Allow updating OAuth2 credentials from the UI."""

    def __init__(self, config_entry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Manage the integration options."""
        errors = {}

        if user_input is not None:
            try:
                await async_validate_input(self.hass, user_input)
            except EleringAuthenticationError:
                errors["base"] = "invalid_auth"
            except (EleringApiError, aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(data=user_input)

        current_client_id = self.config_entry.options.get(
            CONF_CLIENT_ID,
            self.config_entry.data.get(CONF_CLIENT_ID, ""),
        )
        current_client_secret = self.config_entry.options.get(
            CONF_CLIENT_SECRET,
            self.config_entry.data.get(CONF_CLIENT_SECRET, ""),
        )
        current_meter_eic = self.config_entry.options.get(
            CONF_METER_EIC,
            self.config_entry.data.get(CONF_METER_EIC, ""),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID, default=current_client_id): str,
                    vol.Required(CONF_CLIENT_SECRET, default=current_client_secret): str,
                    vol.Required(CONF_METER_EIC, default=current_meter_eic): str,
                }
            ),
            errors=errors,
        )
