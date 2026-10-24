"""Services for the Coop Sverige integration."""
import logging
import os

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.helpers import config_validation as cv

try:
    from homeassistant.core import SupportsResponse

    OPTIONAL_RESPONSE = SupportsResponse.OPTIONAL
except ImportError:
    OPTIONAL_RESPONSE = None

from .const import (
    DOMAIN,
    SERVICE_ADD_ITEM,
    SERVICE_CLEAR_COMPLETED,
    SERVICE_CREATE_SHOPPING_LIST,
    SERVICE_DELETE_ITEM,
    SERVICE_DELETE_SHOPPING_LIST,
    SERVICE_GET_PERSONAL_OFFERS,
    SERVICE_GET_STORE_INFO,
    SERVICE_GET_STORE_OFFERS,
    SERVICE_UPDATE_ITEM,
    VALID_PLACEMENTS,
    VALID_UNITS,
)
from .coordinator import CoopCoordinator
from .sensor import parse_store_deals

_LOGGER = logging.getLogger(__name__)


def normalize_unit(unit: str | None) -> str:
    """Normalize unit string against valid Coop API values."""
    if not unit:
        return ""
    cleaned = unit.strip().lower()
    for valid in VALID_UNITS:
        if cleaned == valid.lower():
            return valid
    return unit.strip()


def normalize_placement(placement: str | None) -> str:
    """Normalize placement string against valid Coop API values."""
    if not placement:
        return ""
    cleaned = placement.strip().lower().replace("&", "och")
    for valid in VALID_PLACEMENTS:
        valid_norm = valid.lower().replace("&", "och")
        if cleaned == valid_norm or cleaned in valid_norm:
            return valid
    return placement.strip()


ATTR_ENTRY_ID = "entry_id"
ATTR_LIST_ID = "list_id"
ATTR_PRODUCT_ID = "product_id"
ATTR_NAME = "name"
ATTR_QUANTITY = "quantity"
ATTR_UNIT = "unit"
ATTR_PLACEMENT = "placement"
ATTR_IS_CHECKED = "is_checked"
ATTR_STORE_ID = "store_id"

SCHEMA_ADD_ITEM = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Optional(ATTR_LIST_ID): cv.string,
        vol.Optional(ATTR_QUANTITY, default="1"): cv.string,
        vol.Optional(ATTR_UNIT, default=""): cv.string,
        vol.Optional(ATTR_PLACEMENT, default=""): cv.string,
        vol.Optional(ATTR_ENTRY_ID): cv.string,
    }
)

SCHEMA_UPDATE_ITEM = vol.Schema(
    {
        vol.Required(ATTR_PRODUCT_ID): cv.string,
        vol.Optional(ATTR_LIST_ID): cv.string,
        vol.Optional(ATTR_NAME): cv.string,
        vol.Optional(ATTR_QUANTITY): cv.string,
        vol.Optional(ATTR_UNIT): cv.string,
        vol.Optional(ATTR_PLACEMENT): cv.string,
        vol.Optional(ATTR_IS_CHECKED): cv.boolean,
        vol.Optional(ATTR_ENTRY_ID): cv.string,
    }
)

SCHEMA_DELETE_ITEM = vol.Schema(
    {
        vol.Required(ATTR_PRODUCT_ID): cv.string,
        vol.Optional(ATTR_LIST_ID): cv.string,
        vol.Optional(ATTR_ENTRY_ID): cv.string,
    }
)

SCHEMA_CLEAR_COMPLETED = vol.Schema(
    {
        vol.Optional(ATTR_LIST_ID): cv.string,
        vol.Optional(ATTR_ENTRY_ID): cv.string,
    }
)

SCHEMA_CREATE_LIST = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Optional(ATTR_ENTRY_ID): cv.string,
    }
)

SCHEMA_DELETE_LIST = vol.Schema(
    {
        vol.Required(ATTR_LIST_ID): cv.string,
        vol.Optional(ATTR_ENTRY_ID): cv.string,
    }
)

SCHEMA_STORE = vol.Schema(
    {
        vol.Optional(ATTR_STORE_ID): cv.string,
        vol.Optional(ATTR_ENTRY_ID): cv.string,
    }
)

SCHEMA_PERSONAL_OFFERS = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
    }
)


def _get_coordinator(hass: HomeAssistant, entry_id: str | None) -> CoopCoordinator:
    """Helper to get coordinator instance."""
    entries: dict[str, CoopCoordinator] = hass.data.get(DOMAIN, {})
    if not entries:
        raise ValueError("No Coop integration entries found")
    if entry_id and entry_id in entries:
        return entries[entry_id]
    return next(iter(entries.values()))


def _resolve_list_id(
    coordinator: CoopCoordinator, list_id: str | None, product_id: str | None = None
) -> str:
    """Resolve shopping list ID, defaulting to first available or one containing the product."""
    shopping_lists = coordinator.data.get("shopping_lists") or []
    if isinstance(shopping_lists, dict):
        shopping_lists = (
            shopping_lists.get("shoppingLists") or shopping_lists.get("lists") or []
        )

    if list_id:
        return str(list_id)

    # If product_id given, search which list contains it
    if product_id:
        for s_list in shopping_lists:
            lid = str(s_list.get("id") or s_list.get("shoppingListID") or "")
            Products = s_list.get("Products") or []
            for p in Products:
                if str(p.get("id") or p.get("productId") or "") == str(product_id):
                    return lid

    # Default to first available list
    if shopping_lists:
        first = shopping_lists[0]
        return str(first.get("id") or first.get("shoppingListID") or "")

    raise ValueError("No shopping lists found in account")


def _resolve_store_id(coordinator: CoopCoordinator, store_id: str | None) -> str:
    """Resolve store ID / ledger number, defaulting to favorite store."""
    if store_id:
        return str(store_id)

    favs = coordinator.data.get("favorite_stores") or []
    if favs:
        first = favs[0]
        ledger = (
            first.get("ledgerAccountNumber")
            or first.get("storeId")
            or first.get("id")
            or first.get("reskontranummer")
        )
        if ledger:
            return str(ledger)

    raise ValueError("No store ID provided and no favorite store found")


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up all Coop Sverige actions/services."""

    async def handle_add_item(call: ServiceCall) -> ServiceResponse:
        """Add item to a shopping list and return status."""
        coordinator = _get_coordinator(hass, call.data.get(ATTR_ENTRY_ID))
        list_id = _resolve_list_id(coordinator, call.data.get(ATTR_LIST_ID))
        name = call.data[ATTR_NAME]
        quantity = call.data.get(ATTR_QUANTITY, "1")
        unit = normalize_unit(call.data.get(ATTR_UNIT))
        placement = normalize_placement(call.data.get(ATTR_PLACEMENT))

        await coordinator.api_client.add_item_to_shopping_list(
            shopping_list_id=list_id,
            name=name,
            quantity=quantity,
            unit=unit,
            placement=placement,
        )
        await coordinator.async_request_refresh()
        return {"success": True, "list_id": list_id, "name": name}

    async def handle_update_item(call: ServiceCall) -> ServiceResponse:
        """Update an item in a shopping list and return status."""
        coordinator = _get_coordinator(hass, call.data.get(ATTR_ENTRY_ID))
        product_id = call.data[ATTR_PRODUCT_ID]
        list_id = _resolve_list_id(
            coordinator, call.data.get(ATTR_LIST_ID), product_id=product_id
        )

        unit_raw = call.data.get(ATTR_UNIT)
        unit = normalize_unit(unit_raw) if unit_raw is not None else None
        placement_raw = call.data.get(ATTR_PLACEMENT)
        placement = (
            normalize_placement(placement_raw) if placement_raw is not None else None
        )

        await coordinator.api_client.update_item_in_shopping_list(
            shopping_list_id=list_id,
            product_id=product_id,
            name=call.data.get(ATTR_NAME),
            quantity=call.data.get(ATTR_QUANTITY),
            unit=unit,
            placement=placement,
            is_checked=call.data.get(ATTR_IS_CHECKED),
        )
        await coordinator.async_request_refresh()
        return {"success": True, "list_id": list_id, "product_id": product_id}

    async def handle_delete_item(call: ServiceCall) -> ServiceResponse:
        """Delete an item from a shopping list and return status."""
        coordinator = _get_coordinator(hass, call.data.get(ATTR_ENTRY_ID))
        product_id = call.data[ATTR_PRODUCT_ID]
        list_id = _resolve_list_id(
            coordinator, call.data.get(ATTR_LIST_ID), product_id=product_id
        )

        await coordinator.api_client.delete_item_from_shopping_list(
            shopping_list_id=list_id,
            product_id=product_id,
        )
        await coordinator.async_request_refresh()
        return {"success": True, "list_id": list_id, "product_id": product_id}

    async def handle_clear_completed(call: ServiceCall) -> ServiceResponse:
        """Clear all checked items from a shopping list and return count."""
        coordinator = _get_coordinator(hass, call.data.get(ATTR_ENTRY_ID))
        list_id = _resolve_list_id(coordinator, call.data.get(ATTR_LIST_ID))

        shopping_lists = coordinator.data.get("shopping_lists") or []
        if isinstance(shopping_lists, dict):
            shopping_lists = (
                shopping_lists.get("shoppingLists") or shopping_lists.get("lists") or []
            )

        checked_ids = []
        for s_list in shopping_lists:
            if str(s_list.get("id") or s_list.get("shoppingListID") or "") == list_id:
                for p in s_list.get("Products") or []:
                    if p.get("isChecked") or p.get("checked"):
                        pid = p.get("id") or p.get("productId")
                        if pid:
                            checked_ids.append(str(pid))
                break

        if checked_ids:
            await coordinator.api_client.delete_item_from_shopping_list(
                shopping_list_id=list_id,
                product_id=checked_ids,
            )
            await coordinator.async_request_refresh()

        return {"success": True, "list_id": list_id, "cleared_count": len(checked_ids)}

    async def handle_create_list(call: ServiceCall) -> ServiceResponse:
        """Create a new shopping list and return its ID."""
        coordinator = _get_coordinator(hass, call.data.get(ATTR_ENTRY_ID))
        name = call.data[ATTR_NAME]

        new_list_id = None

        # 1. Skapa listan via API:et och fånga svarsdata direkt
        try:
            api_response = await coordinator.api_client.create_shopping_list(name)
            _LOGGER.debug("Create shopping list API response: %s", api_response)
            if isinstance(api_response, dict):
                new_list_id = (
                    api_response.get("id")
                    or api_response.get("shoppingListID")
                    or api_response.get("shoppingListId")
                    or api_response.get("listId")
                )
            elif isinstance(api_response, (str, int)):
                new_list_id = str(api_response)
        except Exception as err:  # noqa: BLE001  # noqa: BLE001
            _LOGGER.warning("Failed to create shopping list on Coop: %s", err)

        # 2. Om ID inte returnerades direkt i POST-svaret, gör en sökning bland listorna
        if not new_list_id:
            try:
                raw_lists = await coordinator.api_client.get_shopping_lists()
                if isinstance(raw_lists, dict):
                    shopping_lists = (
                        raw_lists.get("shoppingLists")
                        or raw_lists.get("lists")
                        or raw_lists.get("items")
                        or []
                    )
                elif isinstance(raw_lists, list):
                    shopping_lists = raw_lists
                else:
                    shopping_lists = []

                # Leta efter exakt namnmatchning
                for s in shopping_lists:
                    if (
                        isinstance(s, dict)
                        and str(s.get("name")).strip().lower() == name.strip().lower()
                    ):
                        new_list_id = (
                            s.get("id")
                            or s.get("shoppingListID")
                            or s.get("shoppingListId")
                            or s.get("listId")
                        )
                        break

                # Om fortfarande None, ta den senast tillagda listan (sista i listan)
                if not new_list_id and shopping_lists:
                    last_item = shopping_lists[-1]
                    if isinstance(last_item, dict):
                        new_list_id = (
                            last_item.get("id")
                            or last_item.get("shoppingListID")
                            or last_item.get("shoppingListId")
                            or last_item.get("listId")
                        )
            except Exception as err:  # noqa: BLE001  # noqa: BLE001
                _LOGGER.warning("Could not fetch fresh lists after creation: %s", err)

        await coordinator.async_request_refresh()
        return {"success": True, "list_id": new_list_id, "name": name}

    async def handle_delete_list(call: ServiceCall) -> ServiceResponse:
        """Delete a shopping list and return status."""
        coordinator = _get_coordinator(hass, call.data.get(ATTR_ENTRY_ID))
        list_id = call.data[ATTR_LIST_ID]

        await coordinator.api_client.delete_shopping_list(list_id)
        await coordinator.async_request_refresh()
        return {"success": True, "list_id": list_id}

    async def handle_get_store_info(call: ServiceCall) -> ServiceResponse:
        """Get store details, opening hours, services and holiday calendar."""
        coordinator = _get_coordinator(hass, call.data.get(ATTR_ENTRY_ID))
        store_id = _resolve_store_id(coordinator, call.data.get(ATTR_STORE_ID))

        info = await coordinator.api_client.get_store_info(store_id)
        return {"store": info}

    async def handle_get_store_offers(call: ServiceCall) -> ServiceResponse:
        """Get campaigns and deals for a specific store."""
        coordinator = _get_coordinator(hass, call.data.get(ATTR_ENTRY_ID))
        store_id = _resolve_store_id(coordinator, call.data.get(ATTR_STORE_ID))

        offers = await coordinator.api_client.get_sorting_groups(store_id)
        deals = parse_store_deals(offers)
        return {"offers": offers, "deals": deals}

    async def handle_get_personal_offers(call: ServiceCall) -> ServiceResponse:
        """Get active personal member offers."""
        coordinator = _get_coordinator(hass, call.data.get(ATTR_ENTRY_ID))
        offers = await coordinator.api_client.get_personal_offers()
        return {"offers": offers}

    async def handle_get_receipts(call: ServiceCall) -> ServiceResponse:
        """Fetch recent receipts."""
        coordinator = _get_coordinator(hass, call.data.get(ATTR_ENTRY_ID))
        from_date = call.data.get("from_date")
        to_date = call.data.get("to_date")
        per_page = call.data.get("per_page", 15)

        try:
            res = await coordinator.api_client.get_receipts(
                from_date=from_date, to_date=to_date, per_page=per_page
            )
            return {
                "success": True,
                "receipts": res.get("data", []),
                "total": res.get("total", 0),
            }
        except Exception as err:  # noqa: BLE001  # noqa: BLE001
            _LOGGER.error("Failed to fetch receipts: %s", err)
            return {"success": False, "error": str(err)}

    async def handle_download_receipt_pdf(call: ServiceCall) -> ServiceResponse:
        """Download formal receipt PDF and save locally or return metadata."""
        coordinator = _get_coordinator(hass, call.data.get(ATTR_ENTRY_ID))
        receipt_id = call.data["receipt_id"]

        try:
            pdf_bytes = await coordinator.api_client.get_formal_receipt_pdf(receipt_id)

            dest_dir = hass.config.path("www", "coop_receipts")
            await hass.async_add_executor_job(os.makedirs, dest_dir, True)
            file_path = os.path.join(dest_dir, f"kvitto_{receipt_id}.pdf")

            def _save_file() -> None:
                with open(file_path, "wb") as f:
                    f.write(pdf_bytes)

            await hass.async_add_executor_job(_save_file)

            url_path = f"/local/coop_receipts/kvitto_{receipt_id}.pdf"
            return {"success": True, "file_path": file_path, "url": url_path}
        except Exception as err:  # noqa: BLE001  # noqa: BLE001
            _LOGGER.error("Failed to download receipt PDF: %s", err)
            return {"success": False, "error": str(err)}

    async def handle_search_recipes(call: ServiceCall) -> ServiceResponse:
        """Search Coop recipes."""
        coordinator = _get_coordinator(hass, call.data.get(ATTR_ENTRY_ID))
        query = call.data.get("query", "")
        categories = call.data.get("categories")

        try:
            result = await coordinator.api_client.search_recipes(
                query=query, categories=categories
            )
            return {"success": True, "results": result}
        except Exception as err:  # noqa: BLE001  # noqa: BLE001
            _LOGGER.error("Failed to search recipes: %s", err)
            return {"success": False, "error": str(err)}

    async def handle_get_purchase_history(call: ServiceCall) -> ServiceResponse:
        """Fetch monthly purchase history."""
        coordinator = _get_coordinator(hass, call.data.get(ATTR_ENTRY_ID))
        year = call.data.get("year")
        month = call.data.get("month")

        try:
            history = await coordinator.api_client.get_purchase_history(
                year=year, month=month
            )
            return {"success": True, "history": history}
        except Exception as err:  # noqa: BLE001  # noqa: BLE001
            _LOGGER.error("Failed to fetch purchase history: %s", err)
            return {"success": False, "error": str(err)}

    # Register all actions with response support enabled
    resp_kwargs = (
        {"supports_response": OPTIONAL_RESPONSE}
        if OPTIONAL_RESPONSE is not None
        else {}
    )

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_ITEM, handle_add_item, schema=SCHEMA_ADD_ITEM, **resp_kwargs
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_ITEM,
        handle_update_item,
        schema=SCHEMA_UPDATE_ITEM,
        **resp_kwargs,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_ITEM,
        handle_delete_item,
        schema=SCHEMA_DELETE_ITEM,
        **resp_kwargs,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_COMPLETED,
        handle_clear_completed,
        schema=SCHEMA_CLEAR_COMPLETED,
        **resp_kwargs,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_SHOPPING_LIST,
        handle_create_list,
        schema=SCHEMA_CREATE_LIST,
        **resp_kwargs,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_SHOPPING_LIST,
        handle_delete_list,
        schema=SCHEMA_DELETE_LIST,
        **resp_kwargs,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_STORE_INFO,
        handle_get_store_info,
        schema=SCHEMA_STORE,
        **resp_kwargs,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_STORE_OFFERS,
        handle_get_store_offers,
        schema=SCHEMA_STORE,
        **resp_kwargs,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PERSONAL_OFFERS,
        handle_get_personal_offers,
        schema=SCHEMA_PERSONAL_OFFERS,
        **resp_kwargs,
    )
    hass.services.async_register(
        DOMAIN, "get_receipts", handle_get_receipts, schema=vol.Schema({...})
    )
    hass.services.async_register(
        DOMAIN,
        "download_receipt_pdf",
        handle_download_receipt_pdf,
        schema=vol.Schema(
            {
                vol.Required("receipt_id"): cv.string,
                vol.Optional(ATTR_ENTRY_ID): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "search_recipes",
        handle_search_recipes,
        schema=vol.Schema(
            {
                vol.Optional("query", default=""): cv.string,
                vol.Optional("categories"): [cv.string],
                vol.Optional(ATTR_ENTRY_ID): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        "get_purchase_history",
        handle_get_purchase_history,
        schema=vol.Schema(
            {
                vol.Optional("year"): cv.positive_int,
                vol.Optional("month"): cv.positive_int,
                vol.Optional(ATTR_ENTRY_ID): cv.string,
            }
        ),
    )
