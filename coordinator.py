import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_BASE, DEFAULT_SUB_KEY, TOKEN_URL

_LOGGER = logging.getLogger(__name__)


class CoopBonusCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch Coop Bonus data using session cookie authentication."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        session_cookie: str,
        sub_key: str | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Coop Bonus",
            update_interval=timedelta(hours=6),
        )
        self.session = session
        self._session_cookie = session_cookie
        self._sub_key = sub_key or DEFAULT_SUB_KEY
        self._access_token: str | None = None
        self._token_expires: datetime = datetime.min
        self.entry_id = None

    async def _async_refresh_token(self) -> None:
        """Get a new access token using the session cookie."""
        # Check if current token is still valid (with 5 min buffer)
        if self._access_token and datetime.now(tz=timezone.utc) < self._token_expires - timedelta(minutes=5):
            return

        try:
            headers = {
                "Cookie": f".AspNetCore.Cookies={self._session_cookie}",
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            }
            async with self.session.get(
                TOKEN_URL,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise UpdateFailed(f"Token fetch failed: {resp.status} — {text}")

                result = await resp.json()
                self._access_token = result["token"]

                # Parse expiry from response
                expires_str = result.get("expires")
                if expires_str:
                    # Parse ISO format: "2026-10-22T17:52:14.7016244+00:00"
                    self._token_expires = datetime.fromisoformat(expires_str)
                else:
                    # Fallback: assume 1 hour
                    self._token_expires = datetime.now(tz=timezone.utc) + timedelta(hours=1)

                _LOGGER.debug("Token refreshed, expires at %s", self._token_expires)

        except Exception as e:
            raise UpdateFailed(f"Failed to get token: {e}") from e

    async def _api_get(self, path: str) -> dict:
        """Make a GET request to the Coop loyalty API."""
        await self._async_refresh_token()
        
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Ocp-Apim-Subscription-Key": self._sub_key,
            "Accept": "application/json",
        }
        url = f"{API_BASE}{path}"
        
        try:
            async with self.session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 401:
                    # Token might have expired between check and use
                    await self._async_refresh_token()
                    headers["Authorization"] = f"Bearer {self._access_token}"
                    async with self.session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as retry_resp:
                        if retry_resp.status != 200:
                            text = await retry_resp.text()
                            raise UpdateFailed(f"API error after retry {retry_resp.status}: {text}")
                        return await retry_resp.json()
                
                if resp.status != 200:
                    text = await resp.text()
                    raise UpdateFailed(f"API error {resp.status}: {text}")
                
                return await resp.json()
        
        except Exception as e:
            raise UpdateFailed(f"API request failed: {e}") from e

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Coop Bonus API."""
        try:
            balance = await self._api_get("/account/points/balance?api-version=v3")
            yearly = await self._api_get("/account/points/summary/yearly?api-version=v4")
        except Exception as e:
            raise UpdateFailed(f"Failed to fetch Coop data: {e}") from e

        # Parse yearly response
        point_groups = {}
        for group in yearly.get("pointGroupings", []):
            gid = group.get("id")
            point_groups[gid] = {
                "label": group.get("label", ""),
                "points": group.get("points", 0),
                "monetary": group.get("monetary", 0),
                "type": group.get("type", ""),
            }

        # Extract bonus progress info
        progress_info = yearly.get("bonusProgressInfo", "")
        bonus_info = {}
        
        if "kr till nästa nivå" in progress_info:
            try:
                next_level_kr = progress_info.split("kr till nästa nivå")[0].split(": ")[-1].strip()
                bonus_info["next_level_kr"] = float(next_level_kr.replace(".", "").replace(",", "."))
            except (ValueError, IndexError):
                bonus_info["next_level_kr"] = 0
        
        if "dagar kvar att samla" in progress_info:
            try:
                days_left = progress_info.split("dagar kvar att samla")[0].split(": ")[-1].strip()
                bonus_info["days_until_next_level"] = int(days_left)
            except (ValueError, IndexError):
                bonus_info["days_until_next_level"] = 0

        # Build final data structure
        data = {
            "total_kr": yearly.get("monetaryEarnings", 0),
            "total_points": sum(g.get("points", 0) for g in yearly.get("pointGroupings", [])),
            "monthly_bonus_kr": point_groups.get(1, {}).get("monetary", 0),
            "monthly_bonus_points": point_groups.get(1, {}).get("points", 0),
            "member_prices_kr": point_groups.get(3, {}).get("monetary", 0),
            "member_prices_points": point_groups.get(3, {}).get("points", 0),
            "extra_bonus_kr": point_groups.get(2, {}).get("monetary", 0),
            "extra_bonus_points": point_groups.get(2, {}).get("points", 0),
            "last_login": balance.get("lastLoginDate", ""),
            "member_id": balance.get("memberId", ""),
            **bonus_info,
        }

        _LOGGER.debug("Coop Bonus data updated: %s", data)
        return data