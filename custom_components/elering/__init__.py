"""Elering custom integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EleringApiClient
from .const import CONF_API_TOKEN, CONF_COOKIE_HEADER, CONF_METER_EIC, DOMAIN
from .coordinator import EleringCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entries to API-token based schema."""
    if entry.version >= 3:
        return True

    data = dict(entry.data)
    options = dict(entry.options)

    if CONF_API_TOKEN not in data and CONF_COOKIE_HEADER in data:
        data[CONF_API_TOKEN] = data[CONF_COOKIE_HEADER]
    if CONF_API_TOKEN not in options and CONF_COOKIE_HEADER in options:
        options[CONF_API_TOKEN] = options[CONF_COOKIE_HEADER]

    hass.config_entries.async_update_entry(entry, data=data, options=options, version=3)
    return True


async def async_setup_entry(hass, entry):
    """Set up Elering from a config entry."""
    session = async_get_clientsession(hass)

    api_token = entry.options.get(
        CONF_API_TOKEN,
        entry.data.get(CONF_API_TOKEN, entry.options.get(CONF_COOKIE_HEADER, entry.data.get(CONF_COOKIE_HEADER, ""))),
    )

    client = EleringApiClient(
        session=session,
        api_token=api_token,
        meter_eic=entry.options.get(CONF_METER_EIC, entry.data[CONF_METER_EIC]),
    )

    coordinator = EleringCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
