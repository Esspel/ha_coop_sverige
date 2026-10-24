"""Sensors for Coop Sverige."""

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
        groups = (
            raw_data.get("sortingGroups")
            or raw_data.get("offers")
            or raw_data.get("items")
            or []
        )

    deals: list[dict[str, Any]] = []

    def _build_deal_from_obj(obj: dict[str, Any], parent: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if not isinstance(obj, dict):
            return None
        parent = parent or {}
        content = obj.get("content") or parent.get("content") or {}
        title = (
            obj.get("heading")
            or obj.get("title")
            or obj.get("name")
            or content.get("title")
            or parent.get("heading")
            or parent.get("title")
            or parent.get("name")
            or (parent.get("content") or {}).get("title")
        )
        if not title:
            return None

        price_info = obj.get("priceInformation") or parent.get("priceInformation") or {}
        splash = price_info.get("unifiedSplash") or {}
        if not splash and isinstance(parent.get("priceInformation"), dict):
            splash = parent.get("priceInformation", {}).get("unifiedSplash") or {}
        val = splash.get("value", "")
        unit = splash.get("unit", "")
        tag = splash.get("tag", "")
        price_display = (
            f"{val} {unit} {tag}".strip()
            if val
            else str(price_info.get("price") or price_info.get("discountValue") or "")
        )

        articles = []
        for item in obj.get("clusterInteriorOffers") or obj.get("clusterItems") or parent.get("clusterInteriorOffers") or parent.get("clusterItems") or []:
            if isinstance(item, dict) and item is not obj:
                item_content = item.get("content") or {}
                vol_parts = []
                if item_content.get("weightVolume") or item.get("netVolume"):
                    vol_parts.append(str(item_content.get("weightVolume") or item.get("netVolume")))
                if item_content.get("netContentUnit") or item.get("netContentUnit"):
                    vol_parts.append(str(item_content.get("netContentUnit") or item.get("netContentUnit")))
                articles.append(
                    {
                        "ean": item.get("externalId") or item_content.get("externalId"),
                        "volume": " ".join(vol_parts).strip(),
                        "campaign_id": item.get("campaignId") or item.get("id"),
                        "image_url": item_content.get("imageUrl") or item.get("image"),
                        "title": item_content.get("title") or item.get("title"),
                    }
                )

        image_url = (
            obj.get("imageUrl")
            or content.get("imageUrl")
            or obj.get("image")
            or parent.get("imageUrl")
            or (parent.get("content") or {}).get("imageUrl")
            or parent.get("image")
        )

        return {
            "id": obj.get("id") or parent.get("id"),
            "parent_id": parent.get("id") if parent else None,
            "title": title,
            "brand": content.get("brand") or (parent.get("content") or {}).get("brand"),
            "description": content.get("description") or (parent.get("content") or {}).get("description"),
            "price": price_display,
            "price_information": price_info,
            "unified_splash": splash,
            "is_member_price": bool(price_info.get("isMemberPrice")),
            "deal_type": price_info.get("dealType"),
            "limit": price_info.get("dealOfferLimitText")
            or price_info.get("limit")
            or (parent.get("priceInformation") or {}).get("dealOfferLimitText"),
            "comparative_price": (
                price_info.get("comparativePriceText")
                or price_info.get("enrichedComparisonPrice")
                or content.get("comparativePriceText")
                or (parent.get("priceInformation") or {}).get("comparativePriceText")
            ),
            "image_url": image_url,
            "articles": articles,
            "amount_information": content.get("amountInformation") or (parent.get("content") or {}).get("amountInformation"),
            "external_id": obj.get("externalId") or content.get("externalId"),
            "category_team": obj.get("categoryTeam") or parent.get("categoryTeam"),
            "category_group": obj.get("categoryGroup") or parent.get("categoryGroup"),
            "week_number": obj.get("weekNumber") or parent.get("weekNumber"),
            "campaign_start_date": obj.get("campaignStartDate") or parent.get("campaignStartDate"),
            "campaign_end_date": obj.get("campaignEndDate") or parent.get("campaignEndDate"),
            "store_ledger_account_number": obj.get("storeLedgerAccountNumber") or parent.get("storeLedgerAccountNumber"),
            "channel_codes": obj.get("channelCodes") or parent.get("channelCodes"),
            "role_descriptions": obj.get("roleDescriptions") or parent.get("roleDescriptions"),
            "raw": obj,
        }

    for g in groups:
        if not isinstance(g, dict):
            continue
        campaigns = g.get("campaigns") or g.get("offers") or g.get("items") or [g]
        for c in campaigns:
            if not isinstance(c, dict):
                continue
            cluster_items = c.get("clusterInteriorOffers") or c.get("clusterItems") or []
            deal = _build_deal_from_obj(c)
            if not deal:
                continue
            articles = []
            for item in cluster_items:
                if isinstance(item, dict):
                    item_content = item.get("content") or {}
                    vol_parts = []
                    if item_content.get("weightVolume") or item.get("netVolume"):
                        vol_parts.append(str(item_content.get("weightVolume") or item.get("netVolume")))
                    if item_content.get("netContentUnit") or item.get("netContentUnit"):
                        vol_parts.append(str(item_content.get("netContentUnit") or item.get("netContentUnit")))
                    articles.append(
                        {
                            "ean": item.get("externalId") or item_content.get("externalId"),
                            "volume": " ".join(vol_parts).strip(),
                            "campaign_id": item.get("campaignId") or item.get("id"),
                            "image_url": item_content.get("imageUrl") or item.get("image"),
                            "title": item_content.get("title") or item.get("title"),
                            "amount_information": item_content.get("amountInformation"),
                            "brand": item_content.get("brand"),
                        }
                    )
            deal["articles"] = articles
            deals.append(deal)

    return deals


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Coop Sverige sensors from a config entry."""
    coordinator: CoopCoordinator = entry.runtime_data

    # Sparat/tjänat senast 12 månaderna (kr) + övriga aktiva
    sensors: list[SensorEntity] = [
        CoopBonusSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            key="total_kr",
            name="Totalt sparat (12 mån)",
            icon="mdi:cash-multiple",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="kr",
        ),
        CoopBonusSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            key="monthly_bonus_kr",
            name="Intjänad bonus (12 mån)",
            icon="mdi:calendar-month",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="kr",
        ),
        CoopBonusSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            key="member_prices_kr",
            name="Medlemsrabatter (12 mån)",
            icon="mdi:tag",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="kr",
        ),
        CoopBonusSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            key="extra_bonus_kr",
            name="Extrabonus (12 mån)",
            icon="mdi:fire",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="kr",
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
        # Poängsensorer (Avstängda som standard)
        CoopBonusSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            key="total_points",
            name="Total Bonus (poäng)",
            icon="mdi:counter",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="p",
            enabled_default=False,
        ),
        CoopBonusSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            key="monthly_bonus_points",
            name="Månadsbonus (poäng)",
            icon="mdi:star",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="p",
            enabled_default=False,
        ),
        CoopBonusSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            key="member_prices_points",
            name="Medlemspriser (poäng)",
            icon="mdi:tag",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="p",
            enabled_default=False,
        ),
        CoopBonusSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            key="extra_bonus_points",
            name="Extrabonus (poäng)",
            icon="mdi:fire",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="p",
            enabled_default=False,
        ),
        # Övriga API-sensorer
        CoopPersonalOffersSensor(coordinator, entry.entry_id),
        CoopFavoriteStoreSensor(coordinator, entry.entry_id),
        CoopStoreDealsSensor(coordinator, entry.entry_id),
        CoopShoppingListsSummarySensor(coordinator, entry.entry_id),
        CoopReceiptsSensor(coordinator, entry.entry_id),
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
        member_id = (
            self.coordinator.data.get("member_id") if self.coordinator.data else None
        )
        name = f"Coop Sverige ({member_id})" if member_id else "Coop Sverige"
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=name,
            manufacturer="Coop Sverige Unofficial",
            model="Unofficial",
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
        enabled_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry_id)
        self._key = key
        self._name = name
        self._icon = icon
        self._device_class = device_class
        self._state_class = state_class
        self._native_unit_of_measurement = native_unit_of_measurement
        self._is_text = is_text
        self._attr_entity_registry_enabled_default = enabled_default
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
            return (
                str(value) if value is not None and str(value).strip() != "" else None
            )
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return round(value, 2)
        try:
            return round(float(value), 2)
        except (ValueError, TypeError):
            return value


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
        """Return the number of active personal offers."""
        offers = self.coordinator.data.get("active_personal_offers", [])
        return len(offers)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return personal offers list as attributes."""
        return {
            "personal_offers": self.coordinator.data.get("personal_offers", []),
            "active_offers": self.coordinator.data.get("active_personal_offers", []),
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
        # Count parent offers, not individual variants
        parents = []
        seen = set()
        for deal in deals:
            pid = deal.get("parent_id") or deal.get("id")
            if pid and pid not in seen:
                seen.add(pid)
                parents.append(deal)
            elif not pid:
                # Fallback - count unique titles if no ids
                key = f"{deal.get('title')}|{deal.get('price')}"
                if key not in seen:
                    seen.add(key)
                    parents.append(deal)
        return len(parents) if parents else len(deals)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose offers in multiple formats for card compatibility."""
        attrs: dict[str, Any] = {}
        if self.coordinator.data:
            attrs["deals"] = parse_store_deals(self.coordinator.data.get("primary_store_offers"))
            personal_offers = self.coordinator.data.get("personal_offers", [])
            active_offers = self.coordinator.data.get("active_personal_offers", [])
            attrs["personal_offers"] = personal_offers
            attrs["active_offers"] = active_offers
            # Wrap for templates expecting offer structure
            wrapped = []
            for po in active_offers:
                if isinstance(po, dict):
                    if "offer" in po and isinstance(po.get("offer"), dict):
                        wrapped.append(po)
                    else:
                        wrapped.append({"offer": po})
                else:
                    wrapped.append(po)
            attrs["offers"] = wrapped or active_offers
        return attrs


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
            shopping_lists = (
                shopping_lists.get("shoppingLists") or shopping_lists.get("lists") or []
            )
        return len(shopping_lists) if isinstance(shopping_lists, list) else 0


class CoopReceiptsSensor(CoordinatorEntity[CoopCoordinator], SensorEntity):
    """Representation of Coop receipts sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CoopCoordinator, entry_id: str) -> None:
        """Initialize the receipts sensor."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._attr_unique_id = f"{entry_id}_receipts"
        self._attr_name = "Kvitton"
        self._attr_icon = "mdi:receipt"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        member_id = (
            self.coordinator.data.get("member_id") if self.coordinator.data else None
        )
        name = f"Coop Sverige ({member_id})" if member_id else "Coop Sverige"
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=name,
            manufacturer="Coop Sverige Unofficial",
            model="Unofficial",
        )

    @property
    def native_value(self) -> int:
        """Return total receipts count."""
        return self.coordinator.data.get("total_receipts", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return receipt history list as attribute."""
        return {
            "receipts": self.coordinator.data.get("receipts", []),
        }
