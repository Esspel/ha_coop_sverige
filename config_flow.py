import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import selector

from .const import (
    CONF_EMAIL,
    CONF_NAME,
    CONF_SESSION_COOKIE,
    CONF_SUB_KEY,
    DEFAULT_SUB_KEY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class CoopBonusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Coop Bonus."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            session_cookie = user_input[CONF_SESSION_COOKIE]
            sub_key = user_input.get(CONF_SUB_KEY, DEFAULT_SUB_KEY)

            # Validate by trying to fetch token
            try:
                session = async_get_clientsession(self.hass)
                headers = {
                    "Cookie": f".AspNetCore.Cookies={session_cookie}",
                    "Accept": "application/json",
                }
                async with session.get(
                    "https://www.coop.se/api/spa/token",
                    headers=headers,
                    timeout=15,
                ) as resp:
                    if resp.status != 200:
                        errors["base"] = "invalid_cookie"
                        return self.async_show_form(step_id="user", data_schema=_get_schema(), errors=errors)
                    
                    result = await resp.json()
                    email = result.get("email", "Okänd")
                    name = f"Coop Bonus ({email})"

            except Exception as e:
                _LOGGER.error("Validation failed: %s", e)
                errors["base"] = "cannot_connect"
                return self.async_show_form(step_id="user", data_schema=_get_schema(), errors=errors)

            await self.async_set_unique_id(email)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=name,
                data={
                    CONF_SESSION_COOKIE: session_cookie,
                    CONF_SUB_KEY: sub_key if sub_key != DEFAULT_SUB_KEY else None,
                    CONF_EMAIL: email,
                    CONF_NAME: name,
                },
            )

        return self.async_show_form(step_id="user", data_schema=_get_schema(), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return CoopBonusOptionsFlowHandler(config_entry)


class CoopBonusOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(step_id="init", data_schema=_get_schema())


def _get_schema():
    return vol.Schema(
        {
            vol.Required(CONF_SESSION_COOKIE): selector(
                {"type": "password", "label": "Session Cookie (.AspNetCore.Cookies)", "placeholder": "Paste your .AspNetCore.Cookies value here"}
            ),
            vol.Optional(CONF_SUB_KEY, default=DEFAULT_SUB_KEY): selector(
                {"type": "text", "label": "Subscription Key (optional)", "placeholder": "3becf0ce306f41a1ae94077c16798187"}
            ),
        }
    )