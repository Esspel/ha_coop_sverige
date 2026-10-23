import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import CoopBonusCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up Coop Bonus sensors from a config entry."""
    coordinator: CoopBonusCoordinator = entry.runtime_data

    sensors = [
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
    ]

    async_add_entities(sensors, update_before_add=True)


class CoopBonusSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Coop Bonus sensor."""

    def __init__(
        self,
        coordinator: CoopBonusCoordinator,
        entry_id: str,
        key: str,
        name: str,
        icon: str,
        device_class,
        state_class,
        native_unit_of_measurement: str,
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
        if self._key == "total_kr" or self._key == "total_points":
            return {
                "månadsbonus_kr": data.get("monthly_bonus_kr"),
                "månadsbonus_poäng": data.get("monthly_bonus_points"),
                "medlemspriser_kr": data.get("member_prices_kr"),
                "medlemspriser_poäng": data.get("member_prices_points"),
                "extrabonus_kr": data.get("extra_bonus_kr"),
                "extrabonus_poäng": data.get("extra_bonus_points"),
            }
        return {}