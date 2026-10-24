import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .client import CoopAPIClient
from .const import CONF_SESSION_COOKIE, CONF_SUB_KEY, DEFAULT_SUB_KEY, DOMAIN, PLATFORMS
from .coordinator import CoopCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Coop Sverige component."""
    hass.data.setdefault(DOMAIN, {})
    await async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Coop Sverige from a config entry."""
    session_cookie = (
        entry.options.get(CONF_SESSION_COOKIE) or entry.data[CONF_SESSION_COOKIE]
    )
    sub_key = (
        entry.options.get(CONF_SUB_KEY)
        or entry.data.get(CONF_SUB_KEY)
        or DEFAULT_SUB_KEY
    )

    client = CoopAPIClient(
        session=async_get_clientsession(hass),
        session_cookie=session_cookie,
        sub_key=sub_key,
    )

    # Skicka med entry=entry för att ställbart intervall och manuellt butiksnummer ska fungera
    coordinator = CoopCoordinator(
        hass=hass,
        api_client=client,
        entry=entry,
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator for access
    hass.data[DOMAIN][entry.entry_id] = coordinator
    entry.runtime_data = coordinator

    # Explicitly register member device in Home Assistant Device Registry
    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title or "Coop integration",
        manufacturer="Coop Sverige Unofficial",
        model="Unofficial",
        entry_type=dr.DeviceEntryType.SERVICE,
        configuration_url="https://github.com/Esspel/ha_coop_sverige",
    )

    # If store info is available, register store device
    store_info = coordinator.data.get("primary_store_info") or {}
    favs = coordinator.data.get("favorite_stores") or []
    first_store = favs[0] if isinstance(favs, list) and favs else {}
    store_ledger = (
        store_info.get("ledgerAccountNumber")
        or first_store.get("ledgerAccountNumber")
        or first_store.get("storeId")
        or first_store.get("id")
    )
    if store_ledger:
        store_name = store_info.get("name") or first_store.get("name") or "Coop Butik"
        raw_url = store_info.get("url") or store_info.get("webUrl") or ""
        conf_url = f"https://www.coop.se{raw_url}" if raw_url.startswith("/") else (raw_url or "https://www.coop.se")
        
        dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"store_{store_ledger}")},
            name=f"Favoritbutik {store_name}",
            manufacturer="Coop Sverige Unofficial",
            model="Unofficial",
            entry_type=dr.DeviceEntryType.SERVICE,
            via_device=(DOMAIN, entry.entry_id),
            configuration_url=conf_url,
        )

    # Forward to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
