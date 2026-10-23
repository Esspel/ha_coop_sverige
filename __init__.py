import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS
from .coordinator import CoopBonusCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Coop Bonus component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up Coop Bonus from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = CoopBonusCoordinator(
        hass=hass,
        session=async_get_clientsession(hass),
        session_cookie=entry.data["session_cookie"],
        sub_key=entry.data.get("ocp_apim_subscription_key"),
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator in config entry for access
    entry.runtime_data = coordinator

    # Forward to sensor platform
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