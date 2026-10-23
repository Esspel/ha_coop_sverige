"""Todo platform for Coop Sverige shopping lists."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.components.todo import (
    TodoListEntity,
    TodoListEntityFeature,
    TodoItem,
    TodoItemStatus,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VALID_PLACEMENTS, VALID_UNITS
from .coordinator import CoopCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Coop shopping lists as Todo entities."""
    coordinator: CoopCoordinator = entry.runtime_data
    existing_list_ids: set[str] = set()

    @callback
    def _sync_entities() -> None:
        """Add new todo entities when shopping lists are discovered."""
        data = coordinator.data or {}
        raw_lists = data.get("shopping_lists") or []
        
        _LOGGER.debug("Syncing todo entities. Raw shopping lists data: %s", raw_lists)

        if isinstance(raw_lists, dict):
            raw_lists = (
                raw_lists.get("shoppingLists")
                or raw_lists.get("lists")
                or raw_lists.get("items")
                or raw_lists.get("data")
                or []
            )
        elif not isinstance(raw_lists, list):
            raw_lists = []

        new_entities: list[CoopTodoListEntity] = []
        for s_list in raw_lists:
            if not isinstance(s_list, dict):
                continue
            
            # Leta efter ID med alla tänkbara nyckelvarianter
            list_id = str(
                s_list.get("id")
                or s_list.get("shoppingListID")
                or s_list.get("shoppingListId")
                or s_list.get("listId")
                or s_list.get("key")
                or ""
            ).strip()

            if list_id and list_id not in existing_list_ids:
                existing_list_ids.add(list_id)
                _LOGGER.info("Discovered new Coop shopping list entity: ID=%s, Name=%s", list_id, s_list.get("name"))
                new_entities.append(
                    CoopTodoListEntity(coordinator, entry.entry_id, list_id)
                )

        if new_entities:
            async_add_entities(new_entities)

    # Initial registration
    _sync_entities()
    # Listen for new lists in future updates
    entry.async_on_unload(coordinator.async_add_listener(_sync_entities))


class CoopTodoListEntity(CoordinatorEntity[CoopCoordinator], TodoListEntity):
    """Representation of a Coop Shopping List as a Home Assistant Todo List."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(
        self,
        coordinator: CoopCoordinator,
        entry_id: str,
        list_id: str,
    ) -> None:
        """Initialize the Todo list entity."""
        super().__init__(coordinator)
        self._list_id = str(list_id)
        self._entry_id = entry_id
        self._attr_unique_id = f"{entry_id}_todo_{list_id}"
        self._attr_icon = "mdi:cart-outline"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information linking this list to the Coop Sverige device."""
        member_id = self.coordinator.data.get("member_id") if self.coordinator.data else None
        name = f"Coop Sverige ({member_id})" if member_id else "Coop Sverige"
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=name,
            manufacturer="Coop Sverige",
            model="Coop Medlem & Butik",
        )

    def _get_list_data(self) -> dict[str, Any] | None:
        """Find the matching shopping list data from coordinator."""
        if not self.coordinator.data:
            return None
        shopping_lists = self.coordinator.data.get("shopping_lists") or []
        if isinstance(shopping_lists, dict):
            shopping_lists = (
                shopping_lists.get("shoppingLists")
                or shopping_lists.get("lists")
                or shopping_lists.get("items")
                or []
            )

        for s_list in shopping_lists:
            if not isinstance(s_list, dict):
                continue
            lid = str(
                s_list.get("id")
                or s_list.get("shoppingListID")
                or s_list.get("shoppingListId")
                or s_list.get("listId")
                or s_list.get("key")
                or ""
            ).strip()
            if lid == self._list_id:
                return s_list
        return None

    @property
    def name(self) -> str:
        """Return the list name."""
        list_data = self._get_list_data()
        if list_data and list_data.get("name"):
            return f"Coop {list_data['name']}"
        return f"Coop Inköpslista {self._list_id}"

    @property
    def todo_items(self) -> list[TodoItem] | None:
        """Return the items in this to-do list."""
        list_data = self._get_list_data()
        if not list_data:
            return []

        products = list_data.get("products") or list_data.get("items") or []
        items: list[TodoItem] = []

        for p in products:
            if not isinstance(p, dict):
                continue
            p_id = str(p.get("id") or p.get("productId") or p.get("itemId") or "")
            name = p.get("name") or p.get("text") or "Vara"
            is_checked = bool(p.get("isChecked") or p.get("checked", False))

            desc_parts: list[str] = []
            qty = p.get("quantity")
            unit = p.get("unit")
            if qty:
                desc_parts.append(f"{qty} {unit or ''}".strip())
            placement = p.get("placement")
            if placement:
                desc_parts.append(f"Avdelning: {placement}")

            description = " | ".join(desc_parts) if desc_parts else None

            items.append(
                TodoItem(
                    summary=name,
                    uid=p_id,
                    status=TodoItemStatus.COMPLETED if is_checked else TodoItemStatus.NEEDS_ACTION,
                    description=description,
                )
            )

        return items

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a new shopping item with automatic quantity/unit/placement parsing."""
        raw_text = item.summary.strip()
        quantity = "1"
        unit = ""
        placement = ""
        name = raw_text

        sorted_units = sorted(VALID_UNITS, key=len, reverse=True)
        units_pattern = "|".join(re.escape(u) for u in sorted_units)
        match = re.match(rf"^(\d+(?:[.,]\d+)?)\s*({units_pattern})\s+(.+)$", raw_text, re.IGNORECASE)
        if match:
            quantity = match.group(1).replace(",", ".")
            unit = match.group(2).lower()
            name = match.group(3).strip()
        else:
            num_match = re.match(r"^(\d+(?:[.,]\d+)?)\s+(.+)$", raw_text)
            if num_match:
                quantity = num_match.group(1).replace(",", ".")
                name = num_match.group(2).strip()

        placement_source = item.description or ""
        delim_match = re.search(r"[\(\|]\s*([^\|\)]+)\s*[\)]?$", name)
        if delim_match:
            candidate = delim_match.group(1).strip()
            for p in VALID_PLACEMENTS:
                if candidate.lower() == p.lower():
                    placement = p
                    name = name[:delim_match.start()].strip()
                    break

        if not placement and placement_source:
            for p in VALID_PLACEMENTS:
                if p.lower() in placement_source.lower():
                    placement = p
                    break

        await self.coordinator.api_client.add_item_to_shopping_list(
            shopping_list_id=self._list_id,
            name=name,
            quantity=quantity,
            unit=unit,
            placement=placement,
        )
        await self.coordinator.async_request_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an existing shopping item."""
        if not item.uid:
            _LOGGER.error("Cannot update item without uid")
            return

        list_data = self._get_list_data()
        existing_product = {}
        if list_data:
            for p in list_data.get("products", list_data.get("items", [])):
                if str(p.get("id") or p.get("productId") or "") == str(item.uid):
                    existing_product = p
                    break

        is_checked = (item.status == TodoItemStatus.COMPLETED) if item.status is not None else None
        product_name = item.summary if item.summary else existing_product.get("name", "Vara")

        await self.coordinator.api_client.update_item_in_shopping_list(
            shopping_list_id=self._list_id,
            product_id=item.uid,
            name=product_name,
            unit=existing_product.get("unit"),
            quantity=existing_product.get("quantity"),
            placement=existing_product.get("placement"),
            external_ingredient_id=existing_product.get("externalIngredientID"),
            is_checked=is_checked,
        )
        await self.coordinator.async_request_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete items from the shopping list."""
        if not uids:
            return

        await self.coordinator.api_client.delete_item_from_shopping_list(
            shopping_list_id=self._list_id,
            product_id=uids,
        )
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(f_self) -> dict[str, Any]:
        """Return extra attributes for the shopping list."""
        list_data = f_self._get_list_data()
        if not list_data:
            return {}

        products = list_data.get("products") or list_data.get("items") or []
        checked_count = sum(1 for p in products if isinstance(p, dict) and (p.get("isChecked") or p.get("checked")))
        unchecked_count = len(products) - checked_count

        return {
            "list_id": f_self._list_id,
            "created": list_data.get("created"),
            "updated": list_data.get("updated"),
            "total_items": len(products),
            "unchecked_items": unchecked_count,
            "checked_items": checked_count,
        }