import logging
import urllib.parse
from datetime import UTC, datetime, timedelta
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
        """Initialize the API client."""
        self.session = session
        self._session_cookie = session_cookie
        # Tvinga alltid fallback till DEFAULT_SUB_KEY om sub_key är None, tom eller bara blanksteg
        self._sub_key = (
            sub_key.strip()
            if (sub_key and isinstance(sub_key, str) and sub_key.strip())
            else DEFAULT_SUB_KEY
        )
        self._access_token: str | None = None
        self._token_expires: datetime = datetime.min

    def _get_headers(self, requires_auth: bool = True) -> dict[str, str]:
        """Build request headers with mandatory subscription key."""
        headers = {
            "Ocp-Apim-Subscription-Key": self._sub_key,
            "Accept": "application/json",
            "User-Agent": "Coop/2.35.0 (SE.coop.coopsverige; build:23500; iOS 17.5.1) Alamofire/5.8.1",
        }
        if requires_auth and self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    async def _async_refresh_token(self) -> None:
        """Get a new access token using the session cookie."""
        if self._access_token and datetime.now(
            tz=UTC
        ) < self._token_expires - timedelta(minutes=5):
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
                        self._token_expires = datetime.now(tz=UTC) + timedelta(
                            seconds=expires_str
                        )
                    else:
                        try:
                            self._token_expires = datetime.fromisoformat(str(expires_str))
                        except (ValueError, TypeError):
                            self._token_expires = datetime.now(tz=UTC) + timedelta(hours=1)
                else:
                    self._token_expires = datetime.now(tz=UTC) + timedelta(
                        hours=1
                    )

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
        headers.update(
            {
                "Authorization": f"Bearer {self._access_token}",
                "Ocp-Apim-Subscription-Key": self._sub_key,
                "Accept": "application/json",
            }
        )
        kwargs["headers"] = headers

        try:
            async with self.session.request(
                method, url, timeout=aiohttp.ClientTimeout(total=15), **kwargs
            ) as resp:
                if resp.status == 401:
                    # Token might have expired between check and use
                    await self._async_refresh_token()
                    headers["Authorization"] = f"Bearer {self._access_token}"
                    async with self.session.request(
                        method, url, timeout=aiohttp.ClientTimeout(total=15), **kwargs
                    ) as retry_resp:
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
        return await self._api_request(
            "GET", f"{API_BASE}/account/points/balance?api-version=v3"
        )

    async def get_loyalty_summary_yearly(self) -> dict[str, Any]:
        """Fetch yearly loyalty points summary."""
        return await self._api_request(
            "GET", f"{API_BASE}/account/points/summary/yearly?api-version=v4"
        )

    # --- Shopping Lists API ---

    async def get_shopping_lists(self) -> list[dict[str, Any]] | dict[str, Any]:
        """Fetch all shopping lists."""
        return await self._api_request("GET", f"{SHOPPING_LIST_BASE}?api-version=v2")

    async def create_shopping_list(self, name: str) -> dict[str, Any]:
        """Create a new empty shopping list."""
        encoded_name = urllib.parse.quote(name)
        return await self._api_request(
            "POST", f"{SHOPPING_LIST_BASE}/{encoded_name}?api-version=v2"
        )

    async def delete_shopping_list(self, shopping_list_id: str | int) -> dict[str, Any]:
        """Delete an entire shopping list."""
        return await self._api_request(
            "DELETE", f"{SHOPPING_LIST_BASE}/{shopping_list_id}?api-version=v2"
        )

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
        quantity: str | float | None = None,
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
        quantity: str | float | None = None,
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
            product["checked"] = bool(
                is_checked
            )  # API:et använder "checked" i POST-requesten
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
        return await self._api_request(
            "GET", f"{STORE_BASE}/favorite-stores/me?api-version=v1"
        )

    async def get_stores_by_coordinates(
        self, latitude: float, longitude: float
    ) -> list[dict[str, Any]] | dict[str, Any]:
        """Find nearby stores based on geographical coordinates."""
        return await self._api_request(
            "GET",
            f"{STORE_BASE}/stores?latitude={latitude}&longitude={longitude}&api-version=v3",
        )

    async def get_store_info(self, ledger_account_number: str | int) -> dict[str, Any]:
        """Fetch comprehensive store info, services and opening hours."""
        return await self._api_request(
            "GET", f"{STORE_BASE}/stores/{ledger_account_number}?api-version=v3"
        )

    async def get_sorting_groups(
        self, store_ledger_account_number: str | int
    ) -> dict[str, Any]:
        """Fetch campaigns, sorting groups and product deals for a store."""
        url = f"{OFFERS_BASE}/sorting-groups/{store_ledger_account_number}?grouped=true&api-version=v3&clustered=true"
        return await self._api_request("GET", url)

    # --- Receipts API ---

    async def get_receipts(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
        page: int = 1,
        per_page: int = 15,
    ) -> dict[str, Any]:
        """Fetch list of purchase receipts."""
        if not from_date:
            from_date = (datetime.now(UTC) - timedelta(days=365)).strftime(
                "%Y-%m-%d"
            )
        if not to_date:
            to_date = datetime.now(UTC).strftime("%Y-%m-%d")

        url = f"https://api.betala.coop.se/kvitto/rest/receipts/v1?from_date={from_date}&to_date={to_date}&page={page}&per_page={per_page}"
        return await self._api_request("GET", url)

    async def get_formal_receipt_pdf(self, receipt_id: str) -> bytes:
        """Fetch the formal receipt PDF for a specific receipt ID."""
        url = f"https://api.betala.coop.se/kvitto/rest/receipts/v1/{receipt_id}/formalReceipt"
        await self._async_refresh_token()
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Ocp-Apim-Subscription-Key": self._sub_key,
            "Accept": "*/*",
        }
        async with self.session.get(
            url, headers=headers, timeout=aiohttp.ClientTimeout(total=20)
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise CoopAPIError(f"Failed to fetch receipt PDF {resp.status}: {text}")
            return await resp.read()

    # --- Recipe Search API ---

    async def search_recipes(
        self, query: str = "", categories: list[str] | None = None
    ) -> dict[str, Any]:
        """Search recipes with optional text query and category filters."""
        url = "https://external.api.coop.se/personalization/search/recipes?api-version=v1&direct=false"
        payload = {
            "session": {},
            "user": {
                "dyid": None,
                "active_consent_accepted": True,
                "dyid_server": None,
            },
            "resultsOptions": {
                "facets": [{"attributeName": "categories", "type": "distinct"}]
            },
        }
        if query:
            payload["query"] = query
        if categories:
            payload["filters"] = [{"attributeName": "categories", "values": categories}]

        await self._async_refresh_token()
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Ocp-Apim-Subscription-Key": self._sub_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        async with self.session.post(url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise CoopAPIError(f"Recipe search failed {resp.status}: {text}")
            return await resp.json()

    # --- Purchase History / Köphistorik API ---

    async def get_purchase_history(
        self, year: int | None = None, month: int | None = None
    ) -> list[dict[str, Any]]:
        """Fetch monthly purchase and points history."""
        now = datetime.now(UTC)
        target_year = year or now.year
        target_month = month or now.month

        url = f"{API_BASE}/account/points/purchasehistory/{target_year}/{target_month:02d}?api-version=v3"
        res = await self._api_request("GET", url)
        return res if isinstance(res, list) else []
