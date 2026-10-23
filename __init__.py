import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS, CONF_SESSION_COOKIE, CONF_SUB_KEY
from .coordinator import CoopCoordinator
from .client import CoopAPIClient
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Coop Sverige component."""
    hass.data.setdefault(DOMAIN, {})
    await async_setup_services(hass)
    return True

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up Coop Sverige from a config entry."""
    client = CoopAPIClient(
        session=async_get_clientsession(hass),
        session_cookie=entry.data[CONF_SESSION_COOKIE],
        sub_key=entry.data.get(CONF_SUB_KEY),
    )

    coordinator = CoopCoordinator(
        hass=hass,
        api_client=client,
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator for access
    hass.data[DOMAIN][entry.entry_id] = coordinator
    entry.runtime_data = coordinator

    # Forward to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
