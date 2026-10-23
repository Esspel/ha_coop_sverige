import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import CoopAPIClient, CoopAPIError, CoopAuthError

_LOGGER = logging.getLogger(__name__)


class CoopCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """DataUpdateCoordinator for Coop Sverige."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: CoopAPIClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Coop Sverige",
            update_interval=timedelta(minutes=30),
        )
        self.api_client = api_client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Coop APIs."""
        # 1. Fetch core loyalty data
        try:
            balance = await self.api_client.get_loyalty_balance()
            yearly = await self.api_client.get_loyalty_summary_yearly()
        except CoopAuthError as e:
            _LOGGER.error("Authentication failed: %s", e)
            raise UpdateFailed(f"Auth failed: {e}") from e
        except CoopAPIError as e:
            raise UpdateFailed(f"Failed to fetch loyalty data: {e}") from e
        except Exception as e:
            raise UpdateFailed(f"Unexpected error fetching loyalty: {e}") from e

        # 2. Fetch shopping lists
        shopping_lists: list[dict[str, Any]] = []
        try:
            raw_lists = await self.api_client.get_shopping_lists()
            if isinstance(raw_lists, list):
                shopping_lists = raw_lists
            elif isinstance(raw_lists, dict):
                shopping_lists = raw_lists.get("shoppingLists") or raw_lists.get("lists") or []
        except Exception as e:
            _LOGGER.warning("Failed to fetch shopping lists: %s", e)

        # 3. Fetch personal member offers
        personal_offers: list[dict[str, Any]] = []
        try:
            raw_offers = await self.api_client.get_personal_offers()
            if isinstance(raw_offers, list):
                personal_offers = raw_offers
            elif isinstance(raw_offers, dict):
                personal_offers = (
                    raw_offers.get("offers")
                    or raw_offers.get("personalOffers")
                    or raw_offers.get("items")
                    or []
                )
        except Exception as e:
            _LOGGER.warning("Failed to fetch personal offers: %s", e)

        # 4. Fetch favorite stores or nearby stores via coordinates
        favorite_stores: list[dict[str, Any]] = []
        primary_store_info: dict[str, Any] = {}
        primary_store_offers: dict[str, Any] = {}
        try:
            raw_stores = await self.api_client.get_favorite_stores()
            if isinstance(raw_stores, list):
                favorite_stores = raw_stores
            elif isinstance(raw_stores, dict):
                favorite_stores = raw_stores.get("stores") or raw_stores.get("favoriteStores") or []

            # If no favorite store set in app, find closest store via Home Assistant coordinates
            if not favorite_stores and hasattr(self.hass.config, "latitude") and self.hass.config.latitude:
                try:
                    nearby = await self.api_client.get_stores_by_coordinates(
                        self.hass.config.latitude, self.hass.config.longitude
                    )
                    if isinstance(nearby, list) and nearby:
                        favorite_stores = nearby
                    elif isinstance(nearby, dict):
                        favorite_stores = nearby.get("stores") or nearby.get("items") or []
                except Exception as err:
                    _LOGGER.debug("Could not fetch nearby stores: %s", err)

            # If store found, fetch full store details, opening hours, holiday calendar and campaigns
            if favorite_stores:
                first_store = favorite_stores[0]
                ledger = (
                    first_store.get("ledgerAccountNumber")
                    or first_store.get("storeId")
                    or first_store.get("id")
                    or first_store.get("reskontranummer")
                )
                if ledger:
                    try:
                        primary_store_info = await self.api_client.get_store_info(ledger)
                    except Exception as err:
                        _LOGGER.warning("Failed to fetch store info for %s: %s", ledger, err)

                    try:
                        primary_store_offers = await self.api_client.get_sorting_groups(ledger)
                    except Exception as err:
                        _LOGGER.warning("Failed to fetch sorting groups for store %s: %s", ledger, err)
        except Exception as e:
            _LOGGER.warning("Failed to fetch favorite stores: %s", e)

        # Parse yearly loyalty response
        point_groups: dict[Any, dict[str, Any]] = {}
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
        bonus_info: dict[str, Any] = {
            "next_level_kr": 0.0,
            "days_until_next_level": 0,
        }

        if "kr till nästa nivå" in progress_info:
            try:
                next_level_kr = progress_info.split("kr till nästa nivå")[0].split(": ")[-1].strip()
                bonus_info["next_level_kr"] = float(next_level_kr.replace(".", "").replace(",", "."))
            except (ValueError, IndexError):
                bonus_info["next_level_kr"] = 0.0

        if "dagar kvar att samla" in progress_info:
            try:
                days_left = progress_info.split("dagar kvar att samla")[0].split(": ")[-1].strip()
                bonus_info["days_until_next_level"] = int(days_left)
            except (ValueError, IndexError):
                bonus_info["days_until_next_level"] = 0

        # Parse active personal offers
        active_offers = []
        for offer in personal_offers:
            status = offer.get("status")
            # status: 1 = active / ready at cash register, 4 = used
            if status in (1, "1", "Active", "active") or status is None:
                active_offers.append(offer)

        # Count total and pending shopping items
        total_items_count = 0
        unchecked_items_count = 0
        for s_list in shopping_lists:
            products = s_list.get("products") or []
            total_items_count += len(products)
            unchecked_items_count += sum(
                1 for p in products if not (p.get("isChecked") or p.get("checked"))
            )

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
            # Extended API Data
            "shopping_lists": shopping_lists,
            "total_shopping_items": total_items_count,
            "unchecked_shopping_items": unchecked_items_count,
            "personal_offers": personal_offers,
            "active_personal_offers": active_offers,
            "favorite_stores": favorite_stores,
            "primary_store_info": primary_store_info,
            "primary_store_offers": primary_store_offers,
            **bonus_info,
        }

        _LOGGER.debug("Coop Sverige data updated successfully")
        return data


# Backwards compatibility alias
CoopBonusCoordinator = CoopCoordinator
