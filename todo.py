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

    def _get_raw_lists() -> list[dict[str, Any]]:
        if not coordinator.data:
            return []
        raw = coordinator.data.get("shopping_lists") or []
        if isinstance(raw, dict):
            return (
                raw.get("shoppingLists")
                or raw.get("lists")
                or raw.get("items")
                or []
            )
        if isinstance(raw, list):
            return raw
        return []

    # 1. Tvinga alltid fram minst en entitet direkt så att plattformen registreras i HA
    raw_lists = _get_raw_lists()
    initial_entities: list[CoopTodoListEntity] = []

    if not raw_lists:
        # Fallback-lista om kontot saknar listor vid start
        fallback_id = "default_fallback"
        existing_list_ids.add(fallback_id)
        initial_entities.append(
            CoopTodoListEntity(coordinator, entry.entry_id, fallback_id)
        )
    else:
        for s_list in raw_lists:
            if not isinstance(s_list, dict):
                continue
            lid = str(
                s_list.get("id")
                or s_list.get("shoppingListID")
                or s_list.get("shoppingListId")
                or s_list.get("listId")
                or ""
            ).strip()
            if lid and lid not in existing_list_ids:
                existing_list_ids.add(lid)
                initial_entities.append(
                    CoopTodoListEntity(coordinator, entry.entry_id, lid)
                )

    _LOGGER.info("Registering %d initial Coop todo entities", len(initial_entities))
    async_add_entities(initial_entities)

    # 2. Lyssna på om nya listor dyker upp senare
    @callback
    def _sync_new_entities() -> None:
        current_lists = _get_raw_lists()
        new_entities: list[CoopTodoListEntity] = []

        for s_list in current_lists:
            if not isinstance(s_list, dict):
                continue
            lid = str(
                s_list.get("id")
                or s_list.get("shoppingListID")
                or s_list.get("shoppingListId")
                or s_list.get("listId")
                or ""
            ).strip()
            if lid and lid not in existing_list_ids:
                existing_list_ids.add(lid)
                new_entities.append(
                    CoopTodoListEntity(coordinator, entry.entry_id, lid)
                )

        if new_entities:
            _LOGGER.info("Adding %d dynamic Coop todo entities", len(new_entities))
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_sync_new_entities))


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
        """Find matching list data."""
        if not self.coordinator.data:
            return {"id": self._list_id, "name": "Inköpslista", "products": []}

        raw = self.coordinator.data.get("shopping_lists") or []
        shopping_lists = []
        if isinstance(raw, dict):
            shopping_lists = (
                raw.get("shoppingLists")
                or raw.get("lists")
                or raw.get("items")
                or []
            )
        elif isinstance(raw, list):
            shopping_lists = raw

        for s_list in shopping_lists:
            if not isinstance(s_list, dict):
                continue
            lid = str(
                s_list.get("id")
                or s_list.get("shoppingListID")
                or s_list.get("shoppingListId")
                or s_list.get("listId")
                or ""
            ).strip()
            if lid == self._list_id:
                return s_list

        if self._list_id == "default_fallback" and shopping_lists:
            return shopping_lists[0]

        return {"id": self._list_id, "name": "Inköpslista", "products": []}

    @property
    def name(self) -> str:
        """Return the list name."""
        list_data = self._get_list_data()
        list_name = list_data.get("name") if list_data else "Inköpslista"
        return f"Coop {list_name}"

    @property
    def todo_items(self) -> list[TodoItem] | None:
        """Return current items."""
        list_data = self._get_list_data()
        if not list_data:
            return []

        products = list_data.get("products") or list_data.get("items") or []
        items: list[TodoItem] = []

        for p in products:
            if not isinstance(p, dict):
                continue
            p_id = str(p.get("id") or p.get("productId") or "")
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
        """Create item on Coop list."""
        target_list_id = self._list_id

        if target_list_id == "default_fallback":
            try:
                res = await self.coordinator.api_client.create_shopping_list("Inköpslista")
                if isinstance(res, dict):
                    target_list_id = str(
                        res.get("id")
                        or res.get("shoppingListID")
                        or res.get("shoppingListId")
                        or ""
                    )
            except Exception as e:
                _LOGGER.error("Error creating fallback list on Coop: %s", e)

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

        await self.coordinator.api_client.add_item_to_shopping_list(
            shopping_list_id=target_list_id if target_list_id != "default_fallback" else "",
            name=name,
            quantity=quantity,
            unit=unit,
            placement=placement,
        )
        await self.coordinator.async_request_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update item state or text."""
        if not item.uid:
            return

        list_data = self._get_list_data()
        existing_product = {}
        if list_data:
            for p in list_data.get("products", []):
                if str(p.get("id") or p.get("productId") or "") == str(item.uid):
                    existing_product = p
                    break

        is_checked = (item.status == TodoItemStatus.COMPLETED) if item.status is not None else None
        product_name = item.summary if item.summary else existing_product.get("name", "Vara")

        await self.coordinator.api_client.update_item_in_shopping_list(
            shopping_list_id=self._list_id if self._list_id != "default_fallback" else "",
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
        """Remove items from list."""
        if not uids:
            return

        await self.coordinator.api_client.delete_item_from_shopping_list(
            shopping_list_id=self._list_id if self._list_id != "default_fallback" else "",
            product_id=uids,
        )
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Extra state info."""
        list_data = self._get_list_data()
        if not list_data:
            return {}

        products = list_data.get("products") or []
        checked_count = sum(1 for p in products if isinstance(p, dict) and (p.get("isChecked") or p.get("checked")))
        unchecked_count = len(products) - checked_count

        return {
            "list_id": self._list_id,
            "total_items": len(products),
            "unchecked_items": unchecked_count,
            "checked_items": checked_count,
        }