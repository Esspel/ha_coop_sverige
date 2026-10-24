"""Todo platform for Coop Sverige shopping lists with auto-categorization."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VALID_UNITS
from .coordinator import CoopCoordinator

_LOGGER = logging.getLogger(__name__)

# Smart svensk ordlista för autokategorisering till Coops avdelningar
PLACEMENT_KEYWORDS = {
    "Mejeri": [
        "mjölk", "ost", "smör", "grädde", "yoghurt", "fil", "keso", 
        "creme fraiche", "fetaost", "halloumi", "ägg", "kvarg", "chark"
    ],
    "Frukt och grönt": [
        "banan", "äpple", "tomat", "gurka", "sallad", "lök", "vitlök", 
        "potatis", "morot", "paprika", "avokado", "citron", "druvor", 
        "chili", "päron", "spenat", "broccoli", "champinjoner"
    ],
    "Bröd": [
        "bröd", "limpa", "fralla", "knäckebröd", "tortilla", "pitabröd", 
        "skorpor", "rostbröd", "baguette"
    ],
    "Djupfryst": [
        "pizza", "glass", "ärtor", "pommes", "fryst", "kycklingbitar", 
        "fiskpinnar", "flygande jacob"
    ],
    "Konserver · Skafferi": [
        "krossade tomater", "tonfisk", "pasta", "ris", "mjöl", "socker", 
        "kaffe", "te", "havregryn", "olja", "kex", "majs", "bönor", 
        "ketchup", "senap", "soja", "nudlar", "tacosås"
    ],
    "Kryddor · Smaksättare": [
        "salt", "peppar", "basilika", "oregano", "curry", "buljong", 
        "kanel", "paprikapulver", "tackrydda"
    ],
    "Drycker": [
        "läsk", "juice", "vatten", "cola", "fanta", "sprite", 
        "energidryck", "cider", "öl"
    ],
    "Städa · Tvätta · Diska": [
        "diskmedel", "tvättmedel", "sköljmedel", "toalettpapper", 
        "hushållspapper", "schampo", "tvål", "tandkräm", "deo", "vatten"
    ],
}


def _detect_placement(name: str) -> str:
    """Automatically detect Coop placement based on item name keywords."""
    name_lower = name.lower()
    for placement, keywords in PLACEMENT_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                return placement
    return "Övrigt"


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
                raw.get("shoppingLists") or raw.get("lists") or raw.get("items") or []
            )
        if isinstance(raw, list):
            return raw
        return []

    raw_lists = _get_raw_lists()
    initial_entities: list[CoopTodoListEntity] = []

    if not raw_lists:
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
                s_list.get("ID")
                or s_list.get("id")
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

    async_add_entities(initial_entities)

    @callback
    def _sync_new_entities() -> None:
        current_lists = _get_raw_lists()
        new_entities: list[CoopTodoListEntity] = []

        for s_list in current_lists:
            if not isinstance(s_list, dict):
                continue
            lid = str(
                s_list.get("ID")
                or s_list.get("id")
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
        member_id = (
            self.coordinator.data.get("member_id") if self.coordinator.data else None
        )
        name = f"Coop Sverige ({member_id})" if member_id else "Coop Sverige"
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=name,
            manufacturer="Coop Sverige",
            model="Coop Medlem & Butik",
        )

    async def _ensure_real_list_id(self) -> str:
        """Ensure a real shopping list exists on Coop if currently using fallback."""
        if self._list_id != "default_fallback":
            return self._list_id

        try:
            res = await self.coordinator.api_client.create_shopping_list("Inköpslista")
            if isinstance(res, dict):
                new_id = str(
                    res.get("ID")
                    or res.get("id")
                    or res.get("shoppingListID")
                    or res.get("shoppingListId")
                    or res.get("listId")
                    or ""
                )
                if new_id:
                    self._list_id = new_id
                    return new_id

            await self.coordinator.async_request_refresh()
            raw = self.coordinator.data.get("shopping_lists") or []
            if isinstance(raw, list) and raw:
                first = raw[0]
                new_id = str(
                    first.get("ID")
                    or first.get("id")
                    or first.get("shoppingListID")
                    or first.get("shoppingListId")
                    or ""
                )
                if new_id:
                    self._list_id = new_id
                    return new_id
        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Could not create fallback shopping list on Coop: %s", e)

        return ""

    def _get_list_data(self) -> dict[str, Any] | None:
        """Find matching list data."""
        if not self.coordinator.data:
            return {"ID": self._list_id, "Name": "Inköpslista", "Products": []}

        raw = self.coordinator.data.get("shopping_lists") or []
        shopping_lists = []
        if isinstance(raw, dict):
            shopping_lists = (
                raw.get("shoppingLists") or raw.get("lists") or raw.get("items") or []
            )
        elif isinstance(raw, list):
            shopping_lists = raw

        for s_list in shopping_lists:
            if not isinstance(s_list, dict):
                continue
            lid = str(
                s_list.get("ID")
                or s_list.get("id")
                or s_list.get("shoppingListID")
                or s_list.get("shoppingListId")
                or s_list.get("listId")
                or ""
            ).strip()
            if lid == self._list_id:
                return s_list

        if self._list_id == "default_fallback" and shopping_lists:
            return shopping_lists[0]

        return {"ID": self._list_id, "Name": "Inköpslista", "Products": []}

    @property
    def name(self) -> str:
        """Return the list name."""
        list_data = self._get_list_data()
        list_name = list_data.get("Name") or list_data.get("name") if list_data else "Inköpslista"
        return f"Coop {list_name}"

    @property
    def todo_items(self) -> list[TodoItem] | None:
        """Return current items."""
        list_data = self._get_list_data()
        if not list_data:
            return []

        products = list_data.get("products") or list_data.get("Products") or list_data.get("items") or []
        items: list[TodoItem] = []

        for p in products:
            if not isinstance(p, dict):
                continue
            p_id = str(p.get("ID") or p.get("id") or p.get("productId") or "")
            name = p.get("Name") or p.get("name") or p.get("text") or "Vara"
            is_checked = bool(p.get("Checked") or p.get("isChecked") or p.get("checked", False))
            placement = p.get("Placement") or p.get("placement") or "Övrigt"

            desc_parts: list[str] = [f"Avdelning: {placement}"]
            qty = p.get("Quantity") or p.get("quantity")
            unit = p.get("Unit") or p.get("unit")
            if qty:
                desc_parts.insert(0, f"{qty} {unit or ''}".strip())

            description = " | ".join(desc_parts)

            items.append(
                TodoItem(
                    summary=name,
                    uid=p_id,
                    status=TodoItemStatus.COMPLETED
                    if is_checked
                    else TodoItemStatus.NEEDS_ACTION,
                    description=description,
                )
            )

        return items

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create item on Coop list with auto-categorization."""
        target_list_id = await self._ensure_real_list_id()
        if not target_list_id:
            _LOGGER.error("Cannot create item: No valid shopping list ID available")
            return

        raw_text = item.summary.strip()
        quantity = "1"
        unit = ""
        name = raw_text

        # Parsa mängd och enhet om det skrivs in (t.ex. "2 st mjölk")
        sorted_units = sorted(VALID_UNITS, key=len, reverse=True)
        units_pattern = "|".join(re.escape(u) for u in sorted_units)
        match = re.match(
            rf"^(\d+(?:[.,]\d+)?)\s*({units_pattern})\s+(.+)$", raw_text, re.IGNORECASE
        )
        if match:
            quantity = match.group(1).replace(",", ".")
            unit = match.group(2).lower()
            name = match.group(3).strip()
        else:
            num_match = re.match(r"^(\d+(?:[.,]\d+)?)\s+(.+)$", raw_text)
            if num_match:
                quantity = num_match.group(1).replace(",", ".")
                name = num_match.group(2).strip()

        # Om användaren angett avdelning i beskrivningen, använd den, annars autodetektera
        placement = ""
        if item.description and "Avdelning:" in item.description:
            parts = item.description.split("Avdelning:")
            if len(parts) > 1:
                placement = parts[1].strip().split("|")[0].strip()

        if not placement:
            placement = _detect_placement(name)

        await self.coordinator.api_client.add_item_to_shopping_list(
            shopping_list_id=target_list_id,
            name=name,
            quantity=quantity,
            unit=unit,
            placement=placement,
        )
        await self.coordinator.async_request_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update item state, text, or category."""
        if not item.uid:
            return

        target_list_id = await self._ensure_real_list_id()
        if not target_list_id:
            return

        list_data = self._get_list_data()
        existing_product = {}
        if list_data:
            for p in (list_data.get("products") or list_data.get("Products") or []):
                if str(p.get("ID") or p.get("id") or p.get("productId") or "") == str(item.uid):
                    existing_product = p
                    break

        is_checked = (
            (item.status == TodoItemStatus.COMPLETED)
            if item.status is not None
            else None
        )
        product_name = (
            item.summary if item.summary else existing_product.get("Name") or existing_product.get("name", "Vara")
        )

        # Kolla om beskrivningen uppdaterats med ny avdelning
        placement = existing_product.get("Placement") or existing_product.get("placement") or ""
        if item.description and "Avdelning:" in item.description:
            parts = item.description.split("Avdelning:")
            if len(parts) > 1:
                new_placement = parts[1].strip().split("|")[0].strip()
                if new_placement:
                    placement = new_placement

        await self.coordinator.api_client.update_item_in_shopping_list(
            shopping_list_id=target_list_id,
            product_id=item.uid,
            name=product_name,
            unit=existing_product.get("Unit") or existing_product.get("unit"),
            quantity=existing_product.get("Quantity") or existing_product.get("quantity"),
            placement=placement,
            external_ingredient_id=existing_product.get("ExternalIngredientID") or existing_product.get("externalIngredientID"),
            is_checked=is_checked,
        )
        await self.coordinator.async_request_refresh()

    async def async_delete_todo_item(self, uid: str) -> None:
        """Remove a single item from list."""
        await self.async_delete_todo_items([uid])

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Remove multiple items from list."""
        if not uids:
            return

        target_list_id = await self._ensure_real_list_id()
        if not target_list_id:
            return

        await self.coordinator.api_client.delete_item_from_shopping_list(
            shopping_list_id=target_list_id,
            product_id=uids,
        )
        await self.coordinator.async_request_refresh()