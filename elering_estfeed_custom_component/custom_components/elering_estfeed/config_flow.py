"""Config flow for Elering Estfeed."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_ACCESS_TOKEN, CONF_METER_EIC, DOMAIN


class EleringEstfeedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elering Estfeed."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_METER_EIC])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Elering {user_input[CONF_METER_EIC]}",
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_ACCESS_TOKEN): str,
                vol.Required(CONF_METER_EIC): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
