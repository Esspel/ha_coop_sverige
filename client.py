"""API-client for Coop Sverige."""
import asyncio
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
    RECEIPT_SUB_KEY,
    SHOPPING_LIST_BASE,
    STORE_BASE,
    STORE_SUB_KEY,
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
        betala_refresh_token: str | None = None,
        token_update_callback: Any | None = None,
    ) -> None:
        """Initialize the API client."""
        self.session = session
        self._session_cookie = session_cookie
        self._betala_refresh_token = betala_refresh_token
        self._token_update_callback = token_update_callback
        self._betala_access_token: str | None = None
        self._betala_token_expires: datetime = datetime.now(tz=UTC)
        self._betala_refresh_lock = asyncio.Lock()
        self._sub_key = (
            sub_key.strip()
            if (sub_key and isinstance(sub_key, str) and sub_key.strip())
            else DEFAULT_SUB_KEY
        )
        self._access_token: str | None = None
        self._token_expires: datetime = datetime.now(tz=UTC)

    async def _async_refresh_betala_token(self) -> str | None:
        """Refresh Betala access token using the offline refresh token."""
        if not self._betala_refresh_token:
            return None

        async with self._betala_refresh_lock:
            now = datetime.now(tz=UTC)

            # Cache old token in case callback fails
            old_access_token = self._betala_access_token
            old_refresh_token = self._betala_refresh_token

            # Återanvänd access-token så länge den är giltig.
            if (
                self._betala_access_token
                and now < self._betala_token_expires - timedelta(minutes=5)
            ):
                return self._betala_access_token

            token_url = "https://sso.betala.coop.se/auth/realms/coop/protocol/openid-connect/token?origin=scanpay"
            headers = {
                "User-Agent": "Coop/7.34 (5882; ; 27.0; ; Apple; iPhone18,3)",
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                "Accept": "*/*",
            }
            payload = {
                "client_id": "scanpay",
                "grant_type": "refresh_token",
                "refresh_token": self._betala_refresh_token,
            }

            try:
                async with self.session.post(
                    token_url, headers=headers, data=payload, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status != 200:
                        _LOGGER.warning("Failed to refresh Betala token (status %s)", resp.status)
                        # Restore old tokens and return None
                        self._betala_access_token = old_access_token
                        self._betala_refresh_token = old_refresh_token
                        return None

                    data = await resp.json()
                    self._betala_access_token = data.get("access_token")
                    expires_in = data.get("expires_in", 3600)
                    self._betala_token_expires = datetime.now(tz=UTC) + timedelta(seconds=expires_in)

                    if (new_rt := data.get("refresh_token")) and new_rt != self._betala_refresh_token:
                        # Spara roterad refresh-token innan funktionen avslutas.
                        if self._token_update_callback:
                            callback = self._token_update_callback
                            if asyncio.iscoroutinefunction(callback):
                                try:
                                    await callback(new_rt)
                                except Exception: # noqa: BLE001
                                    # Callback failed - restore old refresh token
                                    _LOGGER.warning(
                                        "Betala refresh token callback failed; "
                                        "restoring old token"
                                    )
                                    self._betala_refresh_token = old_refresh_token
                                    self._betala_access_token = old_access_token
                                    return None
                            else:
                                try:
                                    callback(new_rt)
                                except Exception: # noqa: BLE001
                                    # Callback failed - restore old refresh token
                                    _LOGGER.warning(
                                        "Betala refresh token callback failed; "
                                        "restoring old token"
                                    )
                                    self._betala_refresh_token = old_refresh_token
                                    self._betala_access_token = old_access_token
                                    return None

                        self._betala_refresh_token = new_rt

                    return self._betala_access_token
            except (TimeoutError, aiohttp.ClientError):
                _LOGGER.exception("Network error refreshing Betala token")
                # Restore old tokens
                self._betala_access_token = old_access_token
                self._betala_refresh_token = old_refresh_token
                return None
            except Exception:
                _LOGGER.exception("Unexpected error refreshing Betala token")
                # Restore old tokens
                self._betala_access_token = old_access_token
                self._betala_refresh_token = old_refresh_token
                return None

    def _get_sub_key_for_url(self, url: str) -> str:
        """Return the correct subscription key based on target API domain and path."""
        if "api.betala.coop.se" in url or "/digital/shoppinglist" in url:
            return RECEIPT_SUB_KEY
        if "/external/store" in url:
            return STORE_SUB_KEY
        return self._sub_key

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

        sub_key = self._get_sub_key_for_url(url)
        headers = kwargs.get("headers", {})
        
        # Använd Coop-appens User-Agent för proxy-, butiks- och betala-anrop
        user_agent = (
            "coopapp-ios-7.34"
            if "proxy.api.coop.se" in url or "api.betala.coop.se" in url
            else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        headers.update(
            {
                "Authorization": f"Bearer {self._access_token}",
                "Ocp-Apim-Subscription-Key": sub_key,
                "Accept": "application/json",
                "User-Agent": user_agent,
            }
        )
        kwargs["headers"] = headers

        try:
            async with self.session.request(
                method, url, timeout=aiohttp.ClientTimeout(total=15), **kwargs
            ) as resp:
                if resp.status == 401:
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
    
    async def get_loyalty_timeline(self) -> dict[str, Any]:
        """Fetch monthly bonus timeline and loyalty ladder progress."""
        return await self._api_request(
            "GET", f"{API_BASE}/account/points/timeline?api-version=v4"
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
        """Execute action batch on shopping lists."""
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
            "Products": [product],
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
            product["checked"] = bool(is_checked)
        if external_ingredient_id is not None:
            product["externalIngredientID"] = external_ingredient_id

        action = {
            "actionType": 1,
            "shoppingListID": str(shopping_list_id),
            "Products": [product],
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
        """Fetch receipts using the Betala refresh token."""
        betala_token = await self._async_refresh_betala_token()

        if not betala_token:
            _LOGGER.warning(
                "Receipts unavailable: Betala token refresh failed or refresh token is missing"
            )
            return {"data": [], "total": 0}

        if not from_date:
            from_date = (
                datetime.now(UTC) - timedelta(days=365)
            ).strftime("%Y-%m-%d")
        if not to_date:
            to_date = datetime.now(UTC).strftime("%Y-%m-%d")

        url = (
            "https://api.betala.coop.se/kvitto/rest/receipts/v1"
            f"?from_date={from_date}&to_date={to_date}"
            f"&page={page}&per_page={per_page}"
        )

        headers = {
            "Authorization": f"Bearer {betala_token}",
            "Ocp-Apim-Subscription-Key": RECEIPT_SUB_KEY,
            "Accept": "application/json",
        }

        try:
            async with self.session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    _LOGGER.warning(
                        "Receipt API returned HTTP %s: %s",
                        resp.status,
                        text[:500],
                    )
                    return {"data": [], "total": 0}

                result = await resp.json()

                if not isinstance(result, dict):
                    _LOGGER.warning(
                        "Unexpected receipt API response type: %s",
                        type(result).__name__,
                    )
                    return {"data": [], "total": 0}

                _LOGGER.debug(
                    "Receipt API response keys: %s; total=%s",
                    list(result.keys()),
                    result.get("total"),
                )
                return result

        except Exception:
            _LOGGER.exception("Failed to fetch receipts from Coop")
            return {"data": [], "total": 0}

    async def get_formal_receipt_pdf(self, receipt_id: str) -> bytes:
        """Fetch the formal receipt PDF for a specific receipt ID."""
        betala_token = await self._async_refresh_betala_token()
        if not betala_token:
            raise CoopAPIError("No valid betala_refresh_token configured for receipt PDF download")

        url = f"https://api.betala.coop.se/kvitto/rest/receipts/v1/{receipt_id}/formalReceipt"
        headers = {
            "Authorization": f"Bearer {betala_token}",
            "Ocp-Apim-Subscription-Key": RECEIPT_SUB_KEY,
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

        return await self._api_request("POST", url, json=payload)

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