import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import selector

from .const import (
    CONF_BETALA_REFRESH_TOKEN,
    CONF_EMAIL,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SESSION_COOKIE,
    CONF_STORE_LEDGER_ACCOUNT,
    CONF_SUB_KEY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SUB_KEY,
    DOMAIN,
    TOKEN_URL,
)

_LOGGER = logging.getLogger(__name__)


def _get_user_schema(
    default_cookie: str = "",
    default_betala_refresh_token: str = "",
    default_store: str = "",
    default_interval: int = DEFAULT_SCAN_INTERVAL,
) -> vol.Schema:
    """Schema for initial setup."""
    return vol.Schema(
        {
            vol.Required(CONF_SESSION_COOKIE, default=default_cookie): selector(
                {"text": {"type": "password"}}
            ),
            vol.Optional(CONF_BETALA_REFRESH_TOKEN, default=default_betala_refresh_token): selector(
                {"text": {"type": "password"}}
            ),
            vol.Optional(CONF_STORE_LEDGER_ACCOUNT, default=default_store): selector(
                {"text": {"type": "text"}}
            ),
            vol.Optional(CONF_SCAN_INTERVAL, default=default_interval): selector(
                {
                    "number": {
                        "min": 10,
                        "max": 120,
                        "step": 5,
                        "unit_of_measurement": "minuter",
                    }
                }
            ),
        }
    )


def _get_options_schema(
    default_cookie: str = "",
    default_betala_refresh_token: str = "",
    default_store: str = "",
    default_interval: int = DEFAULT_SCAN_INTERVAL,
) -> vol.Schema:
    """Schema for options flow."""
    return vol.Schema(
        {
            vol.Required(CONF_SESSION_COOKIE, default=default_cookie): selector(
                {"text": {"type": "password"}}
            ),
            vol.Optional(CONF_BETALA_REFRESH_TOKEN, default=default_betala_refresh_token): selector(
                {"text": {"type": "password"}}
            ),
            vol.Optional(CONF_STORE_LEDGER_ACCOUNT, default=default_store): selector(
                {"text": {"type": "text"}}
            ),
            vol.Optional(CONF_SCAN_INTERVAL, default=default_interval): selector(
                {
                    "number": {
                        "min": 10,
                        "max": 120,
                        "step": 5,
                        "unit_of_measurement": "minuter",
                    }
                }
            ),
        }
    )


async def _validate_cookie(hass, session_cookie: str) -> dict[str, Any]:
    """Validate session cookie against Coop token endpoint."""
    session = async_get_clientsession(hass)
    headers = {
        "Cookie": f".AspNetCore.Cookies={session_cookie}",
        "Accept": "application/json",
    }
    async with session.get(TOKEN_URL, headers=headers, timeout=15) as resp:
        if resp.status != 200:
            raise ValueError("invalid_cookie")
        return await resp.json()


class CoopConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Coop Sverige."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            session_cookie = user_input[CONF_SESSION_COOKIE].strip()
            betala_refresh_token = user_input.get(CONF_BETALA_REFRESH_TOKEN, "").strip()
            store_ledger = user_input.get(CONF_STORE_LEDGER_ACCOUNT, "").strip()
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

            try:
                result = await _validate_cookie(self.hass, session_cookie)
                email = result.get("email", "Okänd")
                name = f"Coop Sverige ({email})"
            except ValueError:
                errors["base"] = "invalid_cookie"
            except Exception as e:  # noqa: BLE001
                _LOGGER.error("Validation failed: %s", e)
                errors["base"] = "cannot_connect"

            if not errors:
                await self.async_set_unique_id(email)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_SESSION_COOKIE: session_cookie,
                        CONF_BETALA_REFRESH_TOKEN: betala_refresh_token,
                        CONF_SUB_KEY: DEFAULT_SUB_KEY,
                        CONF_STORE_LEDGER_ACCOUNT: store_ledger if store_ledger else None,
                        CONF_SCAN_INTERVAL: scan_interval,
                        CONF_EMAIL: email,
                        CONF_NAME: name,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=_get_user_schema(), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return CoopOptionsFlowHandler()


class CoopOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Coop Sverige."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            session_cookie = user_input[CONF_SESSION_COOKIE].strip()

            try:
                await _validate_cookie(self.hass, session_cookie)
                sub_key = (
                    self.config_entry.options.get(CONF_SUB_KEY)
                    or self.config_entry.data.get(CONF_SUB_KEY)
                    or DEFAULT_SUB_KEY
                )
                options_data = {
                    **user_input,
                    CONF_SUB_KEY: sub_key,
                }
                return self.async_create_entry(title="", data=options_data)
            except ValueError:
                errors["base"] = "invalid_cookie"
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"

        cookie = self.config_entry.options.get(
            CONF_SESSION_COOKIE
        ) or self.config_entry.data.get(CONF_SESSION_COOKIE, "")
        betala_refresh_token = self.config_entry.options.get(
            CONF_BETALA_REFRESH_TOKEN
        ) or self.config_entry.data.get(CONF_BETALA_REFRESH_TOKEN, "")
        store_ledger = self.config_entry.options.get(
            CONF_STORE_LEDGER_ACCOUNT
        ) or self.config_entry.data.get(CONF_STORE_LEDGER_ACCOUNT, "")
        scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL
        ) or self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        return self.async_show_form(
            step_id="init",
            data_schema=_get_options_schema(
                default_cookie=cookie,
                default_betala_refresh_token=betala_refresh_token,
                default_store=store_ledger,
                default_interval=int(scan_interval),
            ),
            errors=errors,
        )


CoopBonusConfigFlow = CoopConfigFlow
CoopBonusOptionsFlowHandler = CoopOptionsFlowHandler