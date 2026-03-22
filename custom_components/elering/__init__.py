"""Elering custom integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EleringApiClient
from .const import CONF_COOKIE_HEADER, CONF_METER_EIC, DOMAIN
from .coordinator import EleringCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass, entry):
    """Set up Elering from a config entry."""
    session = async_get_clientsession(hass)

    client = EleringApiClient(
        session=session,
        cookie_header=entry.options.get(CONF_COOKIE_HEADER, entry.data[CONF_COOKIE_HEADER]),
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
