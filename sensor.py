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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import CoopCoordinator

_LOGGER = logging.getLogger(__name__)


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
            device_class=SensorDeviceClass.MONEY,
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
            device_class=SensorDeviceClass.MONEY,
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
            device_class=SensorDeviceClass.MONEY,
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
            device_class=SensorDeviceClass.MONEY,
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
            device_class=SensorDeviceClass.MONEY,
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
            device_class=None,
            state_class=None,
            native_unit_of_measurement="",
            is_text=True,
        ),
        CoopBonusSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            key="member_id",
            name="Medlems-ID",
            icon="mdi:card-account-details",
            device_class=None,
            state_class=None,
            native_unit_of_measurement="",
            is_text=True,
        ),
        # New sensors for expanded API features
        CoopPersonalOffersSensor(coordinator, entry.entry_id),
        CoopFavoriteStoreSensor(coordinator, entry.entry_id),
        CoopShoppingListsSummarySensor(coordinator, entry.entry_id),
    ]

    async_add_entities(sensors, update_before_add=True)


class CoopBonusSensor(CoordinatorEntity[CoopCoordinator], SensorEntity):
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
        native_unit_of_measurement: str = "",
        is_text: bool = False,
    ) -> None:
        super().__init__(coordinator)
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
        self._attr_device_class = device_class
        self._attr_state_class = state_class
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
        if isinstance(value, float):
            return round(value, 2)
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


class CoopPersonalOffersSensor(CoordinatorEntity[CoopCoordinator], SensorEntity):
    """Sensor showing active personal offers and discounts."""

    _attr_icon = "mdi:ticket-percent"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "st"

    def __init__(self, coordinator: CoopCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
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
            formatted_offers.append({
                "title": o.get("title") or o.get("heading") or o.get("name") or "Erbjudande",
                "description": o.get("description") or o.get("body") or "",
                "rebate": o.get("rebate") or o.get("discountText") or "",
                "remaining_use": o.get("remainingUse"),
                "status": o.get("status"),
                "valid_to": o.get("validTo") or o.get("endDate"),
                "channels": o.get("channels", []),
                "eans": o.get("eans", []),
            })

        return {
            "total_personal_offers": len(raw_offers),
            "active_offers": formatted_offers,
        }


class CoopFavoriteStoreSensor(CoordinatorEntity[CoopCoordinator], SensorEntity):
    """Sensor showing details and opening hours for the member's favorite store."""

    _attr_icon = "mdi:store"

    def __init__(self, coordinator: CoopCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_favorite_store"
        self._attr_name = "Coop Favoritbutik"

    def _get_store_info(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        return self.coordinator.data.get("primary_store_info") or {}

    def _get_fav_store_summary(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        favs = self.coordinator.data.get("favorite_stores") or []
        return favs[0] if favs else {}

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

        # Services offered (e.g. Scan & Pay, Snabbkassa, Salladsbar, Postombud)
        services = info.get("services") or []

        # Irregular Opening Hours (holidays calendar)
        irregular_hours = info.get("futureIrregularOpeningHours") or info.get("irregularOpeningHours") or []
        user_warnings = [
            h for h in irregular_hours
            if isinstance(h, dict) and h.get("visibleForEndUsers")
        ]

        # Regular Opening Hours
        regular_hours = info.get("openingHours") or info.get("regularOpeningHours") or []

        # Current campaigns count if available
        offers_data = self.coordinator.data.get("primary_store_offers") or {}
        campaign_count = 0
        if isinstance(offers_data, list):
            campaign_count = len(offers_data)
        elif isinstance(offers_data, dict):
            campaign_count = len(offers_data.get("sortingGroups") or offers_data.get("items") or [])

        attrs: dict[str, Any] = {
            "ledger_account_number": ledger,
            "address": street,
            "zip_code": zip_code,
            "city": city,
            "phone": phone,
            "web_url": web_url,
            "services": services,
            "regular_opening_hours": regular_hours,
            "irregular_opening_hours": irregular_hours,
            "upcoming_holiday_warnings": user_warnings,
            "active_campaigns_count": campaign_count,
        }

        return {k: v for k, v in attrs.items() if v is not None}


class CoopShoppingListsSummarySensor(CoordinatorEntity[CoopCoordinator], SensorEntity):
    """Sensor providing a summary of all shopping lists."""

    _attr_icon = "mdi:format-list-checks"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "listor"

    def __init__(self, coordinator: CoopCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
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
        return len(shopping_lists)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return summary attributes for shopping lists."""
        if not self.coordinator.data:
            return {}

        shopping_lists = self.coordinator.data.get("shopping_lists") or []
        if isinstance(shopping_lists, dict):
            shopping_lists = shopping_lists.get("shoppingLists") or shopping_lists.get("lists") or []

        lists_summary = []
        for s_list in shopping_lists:
            lid = str(s_list.get("id") or s_list.get("shoppingListID") or "")
            name = s_list.get("name") or "Inköpslista"
            products = s_list.get("products") or []
            checked_count = sum(1 for p in products if p.get("isChecked") or p.get("checked"))
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
