"""Sensors for Coop Sverige."""

import datetime as dt
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

try:
    from homeassistant.helpers.device_registry import DeviceEntryType
except ImportError:
    DeviceEntryType = None
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CoopCoordinator

_LOGGER = logging.getLogger(__name__)


def parse_store_deals(raw_data: Any) -> list[dict[str, Any]]:
    """Parse deals and sorting groups into structured list."""
    groups = []
    if isinstance(raw_data, list):
        groups = raw_data
    elif isinstance(raw_data, dict):
        groups = raw_data.get("sortingGroups") or raw_data.get("offers") or raw_data.get("items") or []

    deals: list[dict[str, Any]] = []
    for g in groups:
        campaigns = g.get("campaigns") or g.get("offers") or g.get("items") or [g]
        for c in campaigns:
            if isinstance(c, dict):
                continue
            title = c.get("heading") or c.get("title") or c.get("name")
            if not title:
                continue

            price_info = c.get("priceInformation") or {}
            splash = price_info.get("unifiedSplash") or {}
            val = splash.get("value", "")
            unit = splash.get("unit", "")
            tag = splash.get("tag", "")
            price_display = f"{val} {unit} {tag}".strip() if val else str(price_info.get("price", ""))

            # Cluster items (GTIN/EANs and products)
            deals.append({
                "title": title,
                "price_display": price_display,
                "eans": c.get("eans") or [c.get("ean")] if c.get("ean") else [],
            })

    return deals    articles = []
            for item in c.get("clusterItems") or []:
                if isinstance(item, dict):
                    vol_parts = []
                    if item.get("netVolume"):
                        vol_parts.append(str(item["netVolume"]))
                    if item.get("netContentUnit"):
                        vol_parts.append(str(item["netContentUnit"]))
                    articles.append({
                        "ean": item.get("externalId"),
                        "volume": " ".join(vol_parts),
                        "campaign_id": item.get("campaignId") or item.get("id"),
                        "image_url": item.get("imageUrl") or item.get("image"),
                    })

            deals.append({
                "title": title,
                "price": price_display,
                "unified_splash": splash,
                "is_member_price": bool(price_info.get("isMemberPrice")),
                "deal_type": price_info.get("dealType"),
                "limit": price_info.get("dealOfferLimitText"),
                "comparative_price": (
                    price_info.get("comparativePriceText")
                    or price_info.get("enrichedComparisonPrice")
                ),
                "image_url": c.get("imageUrl") or c.get("image"),
                "articles": articles,
            })
    return deals


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Coop Sverige sensors from a config entry."""
    coordinator: CoopCoordinator = entry.runtime_data

    # Standard bonus sensors
    sensors: list[SensorEntity] = [
        CoopBonusSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            key="total_kr",
            name="Total Bonus (kr)",
            icon="mdi:cash-multiple",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="kr",
        ),
        CoopBonusSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            key="total_points",
            name="Total Bonus (poäng)",
            icon="mdi:counter",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="p",
        ),
        CoopBonusSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            key="monthly_bonus_kr",
            name="Månadsbonus (kr)",
            icon="mdi:calendar-month",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="kr",
        ),
        CoopBonusSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            key="monthly_bonus_points",
            name="Månadsbonus (poäng)",
            icon="mdi:star",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="p",
        ),
        CoopBonusSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            key="member_prices_kr",
            name="Medlemspriser (kr)",
            icon="mdi:tag",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="kr",
        ),
        CoopBonusSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            key="member_prices_points",
            name="Medlemspriser (poäng)",
            icon="mdi:tag",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="p",
        ),
        CoopBonusSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            key="extra_bonus_kr",
            name="Extrabonus (kr)",
            icon="mdi:fire",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="kr",
        ),
        CoopBonusSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            key="extra_bonus_points",
            name="Extrabonus (poäng)",
            icon="mdi:fire",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="p",
        ),
        CoopBonusSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            key="next_level_kr",
            name="Nästa nivå (kr)",
            icon="mdi:trending-up",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="kr",
        ),
        CoopBonusSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            key="days_until_next_level",
            name="Dagar till nästa nivå",
            icon="mdi:clock-alert",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="dagar",
        ),
        CoopBonusSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            key="last_login",
            name="Senaste inloggning",
            icon="mdi:login",
            is_text=True,
        ),
        CoopBonusSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            key="member_id",
            name="Medlems-ID",
            icon="mdi:card-account-details",
            is_text=True,
        ),
        # Extended API Sensors
        CoopPersonalOffersSensor(coordinator, entry.entry_id),
        CoopFavoriteStoreSensor(coordinator, entry.entry_id),
        CoopStoreDealsSensor(coordinator, entry.entry_id),
        CoopShoppingListsSummarySensor(coordinator, entry.entry_id),
    ]

    async_add_entities(sensors)


class CoopBaseSensor(CoordinatorEntity[CoopCoordinator], SensorEntity):
    """Base sensor for Coop Sverige entities with device info."""

    def __init__(self, coordinator: CoopCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information linking all entities to a single Coop device."""
        member_id = self.coordinator.data.get("member_id") if self.coordinator.data else None
        name = f"Coop Sverige ({member_id})" if member_id else "Coop Sverige"
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=name,
            manufacturer="Coop Sverige",
            model="Coop Medlem & Butik",
        )


class CoopBonusSensor(CoopBaseSensor):
    """Representation of a Coop Bonus sensor."""

    def __init__(
        self,
        coordinator: CoopCoordinator,
        entry_id: str,
        key: str,
        name: str,
        icon: str,
        device_class: SensorDeviceClass | None = None,
        state_class: SensorStateClass | None = None,
        native_unit_of_measurement: str | None = None,
        is_text: bool = False,
    ) -> None:
        super().__init__(coordinator, entry_id)
        self._key = key
        self._name = name
        self._icon = icon
        self._device_class = device_class
        self._state_class = state_class
        self._native_unit_of_measurement = native_unit_of_measurement
        self._is_text = is_text
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        if device_class:
            self._attr_device_class = device_class
        if state_class:
            self._attr_state_class = state_class
        if native_unit_of_measurement:
            self._attr_native_unit_of_measurement = native_unit_of_measurement

    @property
    def native_value(self) -> Any:
        """Return the state."""
        data = self.coordinator.data
        if data is None:
            return None
        value = data.get(self._key)
        if self._is_text:
            return str(value) if value is not None else None
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return round(value, 2)
        try:
            return round(float(value), 2)
        except (ValueError, TypeError):
            return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        data = self.coordinator.data
        if data is None:
            return {}
        if self._key in ("total_kr", "total_points"):
            return {
                "månadsbonus_kr": data.get("monthly_bonus_kr"),
                "månadsbonus_poäng": data.get("monthly_bonus_points"),
                "medlemspriser_kr": data.get("member_prices_kr"),
                "medlemspriser_poäng": data.get("member_prices_points"),
                "extrabonus_kr": data.get("extra_bonus_kr"),
                "extrabonus_poäng": data.get("extra_bonus_points"),
            }
        return {}


class CoopPersonalOffersSensor(CoopBaseSensor):
    """Sensor showing active targeted personal member offers."""

    _attr_icon = "mdi:ticket-percent"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "st"

    def __init__(self, coordinator: CoopCoordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_active_personal_offers"
        self._attr_name = "Aktiva personliga erbjudanden"

    @property
    def native_value(self) -> int:
        """Return the count of active personal offers."""
        if not self.coordinator.data:
            return 0
        active_offers = self.coordinator.data.get("active_personal_offers") or []
        return len(active_offers)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return formatted offers as attributes."""
        if not self.coordinator.data:
            return {}

        raw_offers = self.coordinator.data.get("personal_offers") or []
        active_offers = self.coordinator.data.get("active_personal_offers") or []

        formatted_offers = []
        for o in active_offers:
            if isinstance(o, dict):
                formatted_offers.append({
                    "title": o.get("title") or o.get("heading") or o.get("name") or "Erbjudande",
                    "description": o.get("description") or o.get("body") or "",
                    "rebate": o.get("rebate") or o.get("discountText") or "",
                    "scoring_type": o.get("dealScoringType") or "STANDARD",
                    "remaining_use": o.get("remainingUse", 1),
                    "status": o.get("status"),
                    "valid_to": o.get("validTo") or o.get("endDate"),
                    "channels": o.get("channels", []),
                    "eans": o.get("eans", []),
                })

        return {
            "total_personal_offers": len(raw_offers) if isinstance(raw_offers, list) else 0,
            "active_offers": formatted_offers,
        }


class CoopFavoriteStoreSensor(CoopBaseSensor):
    """Sensor showing details, amenities, and holiday opening hours for the store."""

    _attr_icon = "mdi:store"

    def __init__(self, coordinator: CoopCoordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_favorite_store"
        self._attr_name = "Coop Butik"

    def _get_store_info(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        info = self.coordinator.data.get("primary_store_info")
        return info if isinstance(info, dict) else {}

    def _get_fav_store_summary(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        favs = self.coordinator.data.get("favorite_stores") or []
        return favs[0] if isinstance(favs, list) and favs else {}

    @property
    def native_value(self) -> str:
        """Return store name."""
        info = self._get_store_info()
        if info and info.get("name"):
            return str(info["name"])

        fav = self._get_fav_store_summary()
        if fav and fav.get("name"):
            return str(fav["name"])

        return "Ingen butik vald"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return rich store information, services and irregular opening hours."""
        info = self._get_store_info()
        fav = self._get_fav_store_summary()

        ledger = (
            info.get("ledgerAccountNumber")
            or fav.get("ledgerAccountNumber")
            or fav.get("storeId")
            or fav.get("id")
        )

        # Address & Contact
        address_info = info.get("address") if isinstance(info.get("address"), dict) else {}
        street = address_info.get("street") or info.get("streetAddress") or fav.get("street")
        zip_code = address_info.get("zip") or address_info.get("postalCode") or info.get("zip")
        city = address_info.get("city") or info.get("city") or fav.get("city")
        phone = info.get("phone") or info.get("telephone") or fav.get("phone")
        web_url = info.get("url") or info.get("webUrl")

        # Coordinates
        location = info.get("location") or info.get("coordinates") or {}
        lat = location.get("latitude") if isinstance(location, dict) else info.get("latitude")
        lon = location.get("longitude") if isinstance(location, dict) else info.get("longitude")

        # Services offered (e.g. Scan & Pay, Snabbkassa, Salladsbar, Postombud)
        services = info.get("services") or []
        services_lower = [str(s).lower() for s in services] if isinstance(services, list) else []

        service_flags = {
            "scan_and_pay": any("scan" in s or "shopexpress" in s for s in services_lower),
            "self_checkout": any("snabbkassa" in s or "självbetjäning" in s for s in services_lower),
            "salad_bar": any("sallad" in s for s in services_lower),
            "postal_services": any("post" in s or "paket" in s for s in services_lower),
            "instabox": any("instabox" in s for s in services_lower),
            "budbee": any("budbee" in s for s in services_lower),
            "atg": any("atg" in s for s in services_lower),
            "svenska_spel": any("svenska spel" in s for s in services_lower),
        }

        # Irregular Opening Hours (holidays calendar)
        irregular_hours = (
            info.get("futureIrregularOpeningHours")
            or info.get("irregularOpeningHours")
            or []
        )
        user_warnings = [
            h for h in irregular_hours
            if isinstance(h, dict) and h.get("visibleForEndUsers")
        ] if isinstance(irregular_hours, list) else []

        # Regular Opening Hours
        regular_hours = info.get("openingHours") or info.get("regularOpeningHours") or []

        # Current campaigns count if available
        deals = parse_store_deals(self.coordinator.data.get("primary_store_offers"))

        attrs: dict[str, Any] = {
            "ledger_account_number": ledger,
            "address": street,
            "zip_code": zip_code,
            "city": city,
            "phone": phone,
            "web_url": web_url,
            "latitude": lat,
            "longitude": lon,
            "services": services,
            **service_flags,
            "regular_opening_hours": regular_hours,
            "irregular_opening_hours": irregular_hours,
            "upcoming_holiday_warnings": user_warnings,
            "active_campaigns_count": len(deals),
        }

        return {k: v for k, v in attrs.items() if v is not None}

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information linking to the Coop Store device."""
        info = self._get_store_info()
        fav = self._get_fav_store_summary()
        ledger = (
            info.get("ledgerAccountNumber")
            or fav.get("ledgerAccountNumber")
            or fav.get("storeId")
            or fav.get("id")
        )
        if ledger:
            store_name = info.get("name") or fav.get("name") or "Coop Butik"
            web_url = info.get("url") or info.get("webUrl") or "https://www.coop.se"
            dev_info = DeviceInfo(
                identifiers={(DOMAIN, f"store_{ledger}")},
                name=f"Coop {store_name}",
                manufacturer="Coop Sverige",
                model="Butik & Öppettider",
                via_device=(DOMAIN, self._entry_id),
                configuration_url=web_url,
            )
            if DeviceEntryType is not None:
                dev_info["entry_type"] = DeviceEntryType.SERVICE
            return dev_info
        return super().device_info


class CoopStoreDealsSensor(CoopBaseSensor):
    """Sensor showing active store deals, unifiedSplash pricing and GTIN/EAN barcodes."""

    _attr_icon = "mdi:tag-multiple"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "erbjudanden"

    def __init__(self, coordinator: CoopCoordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_store_deals"
        self._attr_name = "Coop Butikserbjudanden"

    @property
    def native_value(self) -> int:
        """Return the count of active deals."""
        if not self.coordinator.data:
            return 0
        deals = parse_store_deals(self.coordinator.data.get("primary_store_offers"))
        return len(deals)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return list of top deals with price and EAN details."""
        if not self.coordinator.data:
            return {}

        deals = parse_store_deals(self.coordinator.data.get("primary_store_offers"))
        store_info = self.coordinator.data.get("primary_store_info")
        store_info = store_info if isinstance(store_info, dict) else {}

        return {
            "store_name": store_info.get("name"),
            "total_deals_count": len(deals),
            "deals": deals[:30],  # Top 30 deals to maintain HA state size limits
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information linking to the Coop Store device."""
        store_info = self.coordinator.data.get("primary_store_info") or {}
        favs = self.coordinator.data.get("favorite_stores") or []
        first_store = favs[0] if isinstance(favs, list) and favs else {}
        ledger = (
            store_info.get("ledgerAccountNumber")
            or first_store.get("ledgerAccountNumber")
            or first_store.get("storeId")
            or first_store.get("id")
        )
        if ledger:
            store_name = store_info.get("name") or first_store.get("name") or "Coop Butik"
            web_url = store_info.get("url") or store_info.get("webUrl") or "https://www.coop.se"
            dev_info = DeviceInfo(
                identifiers={(DOMAIN, f"store_{ledger}")},
                name=f"Coop {store_name}",
                manufacturer="Coop Sverige",
                model="Butik & Öppettider",
                via_device=(DOMAIN, self._entry_id),
                configuration_url=web_url,
            )
            if DeviceEntryType is not None:
                dev_info["entry_type"] = DeviceEntryType.SERVICE
            return dev_info
        return super().device_info


class CoopShoppingListsSummarySensor(CoopBaseSensor):
    """Sensor providing a summary of all shopping lists."""

    _attr_icon = "mdi:format-list-checks"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "listor"

    def __init__(self, coordinator: CoopCoordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_shopping_lists_summary"
        self._attr_name = "Coop Inköpslistor"

    @property
    def native_value(self) -> int:
        """Return the number of shopping lists."""
        if not self.coordinator.data:
            return 0
        shopping_lists = self.coordinator.data.get("shopping_lists") or []
        if isinstance(shopping_lists, dict):
            shopping_lists = shopping_lists.get("shoppingLists") or shopping_lists.get("lists") or []
        return len(shopping_lists) if isinstance(shopping_lists, list) else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return summary attributes for shopping lists."""
        if not self.coordinator.data:
            return {}

        shopping_lists = self.coordinator.data.get("shopping_lists") or []
        if isinstance(shopping_lists, dict):
            shopping_lists = shopping_lists.get("shoppingLists") or shopping_lists.get("lists") or []
        if not isinstance(shopping_lists, list):
            shopping_lists = []

        lists_summary = []
        for s_list in shopping_lists:
            if isinstance(s_list, dict):
                lid = str(s_list.get("id") or s_list.get("shoppingListID") or "")
                name = s_list.get("name") or "Inköpslista"
                products = s_list.get("products") or []
                products = products if isinstance(products, list) else []
                checked_count = sum(1 for p in products if isinstance(p, dict) and (p.get("isChecked") or p.get("checked")))
                lists_summary.append({
                    "id": lid,
                    "name": name,
                    "total_items": len(products),
                    "unchecked_items": len(products) - checked_count,
                    "checked_items": checked_count,
                })

        return {
            "total_items_count": self.coordinator.data.get("total_shopping_items", 0),
            "unchecked_items_count": self.coordinator.data.get("unchecked_shopping_items", 0),
            "lists": lists_summary,
        }
