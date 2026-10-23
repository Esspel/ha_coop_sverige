import logging
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp
from .const import (
    API_BASE,
    DEFAULT_SUB_KEY,
    OFFERS_BASE,
    PERSONAL_OFFERS_BASE,
    SHOPPING_LIST_BASE,
    STORE_BASE,
    TOKEN_URL,
)

_LOGGER = logging.getLogger(__name__)


class CoopAuthError(Exception):
    """Error to indicate there is an authentication issue."""


class CoopAPIError(Exception):
    """Error to indicate there is an API issue."""


class CoopAPIClient:
    """API client for interacting with Coop Sverige endpoints."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        session_cookie: str,
        sub_key: str | None = None,
    ) -> None:
        self.session = session
        self._session_cookie = session_cookie
        # Säkerställ att den ALDRIG blir None eller tom sträng
        self._sub_key = sub_key.strip() if (sub_key and sub_key.strip()) else DEFAULT_SUB_KEY
        self._access_token: str | None = None
        self._token_expires: datetime = datetime.min

    async def _async_refresh_token(self) -> None:
        """Get a new access token using the session cookie."""
        if self._access_token and datetime.now(tz=timezone.utc) < self._token_expires - timedelta(minutes=5):
            return

        try:
            headers = {
                "Cookie": f".AspNetCore.Cookies={self._session_cookie}",
                "Accept": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            }
            async with self.session.get(
                TOKEN_URL,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 401:
                    raise CoopAuthError("Invalid session cookie")

                if resp.status != 200:
                    text = await resp.text()
                    raise CoopAPIError(f"Token fetch failed: {resp.status} — {text}")

                result = await resp.json()
                self._access_token = result.get("token") or result.get("access_token")
                if not self._access_token:
                    raise CoopAPIError(f"No token found in response: {result}")

                expires_str = result.get("expires") or result.get("expires_in")
                if expires_str:
                    if isinstance(expires_str, (int, float)):
                        self._token_expires = datetime.now(tz=timezone.utc) + timedelta(seconds=expires_str)
                    else:
                        try:
                            self._token_expires = datetime.fromisoformat(str(expires_str).replace("Z", "+00:00"))
                        except Exception:
                            self._token_expires = datetime.now(tz=timezone.utc) + timedelta(hours=1)
                else:
                    self._token_expires = datetime.now(tz=timezone.utc) + timedelta(hours=1)

                _LOGGER.debug("Token refreshed, expires at %s", self._token_expires)

        except aiohttp.ClientError as e:
            raise CoopAPIError(f"Connection error: {e}") from e
        except Exception as e:
            if isinstance(e, (CoopAuthError, CoopAPIError)):
                raise
            raise CoopAPIError(f"Failed to get token: {e}") from e

    async def _api_request(self, method: str, url: str, **kwargs) -> Any:
        """Make an authorized request to the Coop API."""
        await self._async_refresh_token()

        headers = kwargs.get("headers", {})
        headers.update({
            "Authorization": f"Bearer {self._access_token}",
            "Ocp-Apim-Subscription-Key": self._sub_key,
            "Accept": "application/json",
        })
        kwargs["headers"] = headers

        try:
            async with self.session.request(method, url, timeout=aiohttp.ClientTimeout(total=15), **kwargs) as resp:
                if resp.status == 401:
                    # Token might have expired between check and use
                    await self._async_refresh_token()
                    headers["Authorization"] = f"Bearer {self._access_token}"
                    async with self.session.request(method, url, timeout=aiohttp.ClientTimeout(total=15), **kwargs) as retry_resp:
                        return await self._parse_response(retry_resp)

                return await self._parse_response(resp)

        except aiohttp.ClientError as e:
            raise CoopAPIError(f"Connection error: {e}") from e
        except Exception as e:
            if isinstance(e, CoopAPIError):
                raise
            raise CoopAPIError(f"API request failed: {e}") from e

    async def _parse_response(self, resp: aiohttp.ClientResponse) -> Any:
        """Parse HTTP response and handle potential errors or empty bodies."""
        if resp.status in (200, 201):
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return await resp.json()
            text = await resp.text()
            return text if text else {}
        elif resp.status == 204:
            return {}

        text = await resp.text()
        raise CoopAPIError(f"API error {resp.status}: {text}")

    # --- Loyalty / Bonus API ---

    async def get_loyalty_balance(self) -> dict[str, Any]:
        """Fetch loyalty points balance."""
        return await self._api_request("GET", f"{API_BASE}/account/points/balance?api-version=v3")

    async def get_loyalty_summary_yearly(self) -> dict[str, Any]:
        """Fetch yearly loyalty points summary."""
        return await self._api_request("GET", f"{API_BASE}/account/points/summary/yearly?api-version=v4")

    # --- Shopping Lists API ---

    async def get_shopping_lists(self) -> list[dict[str, Any]] | dict[str, Any]:
        """Fetch all shopping lists."""
        return await self._api_request("GET", f"{SHOPPING_LIST_BASE}?api-version=v2")

    async def create_shopping_list(self, name: str) -> dict[str, Any]:
        """Create a new empty shopping list."""
        encoded_name = urllib.parse.quote(name)
        return await self._api_request("POST", f"{SHOPPING_LIST_BASE}/{encoded_name}?api-version=v2")

    async def delete_shopping_list(self, shopping_list_id: str | int) -> dict[str, Any]:
        """Delete an entire shopping list."""
        return await self._api_request("DELETE", f"{SHOPPING_LIST_BASE}/{shopping_list_id}?api-version=v2")

    async def execute_shopping_list_actions(self, actions: list[dict[str, Any]]) -> Any:
        """Execute action batch on shopping lists.

        actionType 0: Add product
        actionType 1: Update product
        actionType 2: Delete product
        """
        return await self._api_request(
            "POST",
            f"{SHOPPING_LIST_BASE}/execute?api-version=v2",
            json=actions,
        )

    async def add_item_to_shopping_list(
        self,
        shopping_list_id: str | int,
        name: str,
        quantity: str | int | float | None = None,
        unit: str | None = None,
        placement: str | None = None,
    ) -> Any:
        """Add a new item to a shopping list."""
        product: dict[str, Any] = {
            "name": name,
            "shoppingListID": str(shopping_list_id),
        }
        if quantity is not None:
            product["quantity"] = str(quantity)
        if unit is not None:
            product["unit"] = unit
        if placement is not None:
            product["placement"] = placement

        action = {
            "actionType": 0,
            "shoppingListID": str(shopping_list_id),
            "products": [product],
        }
        return await self.execute_shopping_list_actions([action])

    async def update_item_in_shopping_list(
        self,
        shopping_list_id: str | int,
        product_id: str | int,
        name: str | None = None,
        quantity: str | int | float | None = None,
        unit: str | None = None,
        placement: str | None = None,
        is_checked: bool | None = None,
        external_ingredient_id: str | int | None = None,
    ) -> Any:
        """Update an existing item in a shopping list."""
        product: dict[str, Any] = {
            "id": int(product_id) if str(product_id).isdigit() else product_id,
            "shoppingListID": str(shopping_list_id),
        }
        if name is not None:
            product["name"] = name
        if quantity is not None:
            product["quantity"] = str(quantity)
        if unit is not None:
            product["unit"] = unit
        if placement is not None:
            product["placement"] = placement
        if is_checked is not None:
            product["checked"] = bool(is_checked)  # API:et använder "checked" i POST-requesten
        if external_ingredient_id is not None:
            product["externalIngredientID"] = external_ingredient_id

        action = {
            "actionType": 1,
            "shoppingListID": str(shopping_list_id),
            "products": [product],
        }
        return await self.execute_shopping_list_actions([action])

    async def delete_item_from_shopping_list(
        self,
        shopping_list_id: str | int,
        product_id: str | int | list[str | int],
    ) -> Any:
        """Delete one or more items from a shopping list."""
        if isinstance(product_id, (list, tuple, set)):
            pids = [str(p) for p in product_id]
        else:
            pids = [str(product_id)]

        action = {
            "actionType": 2,
            "shoppingListID": str(shopping_list_id),
            "productIDs": pids,
        }
        return await self.execute_shopping_list_actions([action])

    # --- Personal Offers API ---

    async def get_personal_offers(self) -> dict[str, Any] | list[dict[str, Any]]:
        """Fetch targeted personal member offers."""
        url = f"{PERSONAL_OFFERS_BASE}/offers?api-version=v2&channels=MobileApp&status=1&status=3&status=4"
        return await self._api_request("GET", url)

    # --- Store & Deals API ---

    async def get_favorite_stores(self) -> list[dict[str, Any]] | dict[str, Any]:
        """Fetch the member's favorite stores."""
        return await self._api_request("GET", f"{STORE_BASE}/favorite-stores/me?api-version=v1")

    async def get_stores_by_coordinates(self, latitude: float, longitude: float) -> list[dict[str, Any]] | dict[str, Any]:
        """Find nearby stores based on geographical coordinates."""
        return await self._api_request(
            "GET",
            f"{STORE_BASE}/stores?latitude={latitude}&longitude={longitude}&api-version=v3",
        )

    async def get_store_info(self, ledger_account_number: str | int) -> dict[str, Any]:
        """Fetch comprehensive store info, services and opening hours."""
        return await self._api_request("GET", f"{STORE_BASE}/stores/{ledger_account_number}?api-version=v3")

    async def get_sorting_groups(self, store_ledger_account_number: str | int) -> dict[str, Any]:
        """Fetch campaigns, sorting groups and product deals for a store."""
        url = f"{OFFERS_BASE}/sorting-groups/{store_ledger_account_number}?grouped=true&api-version=v3&clustered=true"
        return await self._api_request("GET", url)
