import logging
from typing import Any

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
    TOKEN_URL,
)

_LOGGER = logging.getLogger(__name__)


def _get_schema(default_cookie: str = "", default_sub_key: str = DEFAULT_SUB_KEY) -> vol.Schema:
    """Build config flow data schema using valid Home Assistant selectors."""
    schema_fields: dict[Any, Any] = {}

    if default_cookie:
        schema_fields[vol.Required(CONF_SESSION_COOKIE, default=default_cookie)] = selector(
            {"text": {"type": "password"}}
        )
    else:
        schema_fields[vol.Required(CONF_SESSION_COOKIE)] = selector(
            {"text": {"type": "password"}}
        )

    schema_fields[vol.Optional(CONF_SUB_KEY, default=default_sub_key)] = selector(
        {"text": {"type": "text"}}
    )

    return vol.Schema(schema_fields)


class CoopConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Coop Sverige."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            session_cookie = user_input[CONF_SESSION_COOKIE].strip()
            sub_key = user_input.get(CONF_SUB_KEY, DEFAULT_SUB_KEY).strip()

            # Validate by trying to fetch token
            try:
                session = async_get_clientsession(self.hass)
                headers = {
                    "Cookie": f".AspNetCore.Cookies={session_cookie}",
                    "Accept": "application/json",
                }
                async with session.get(
                    TOKEN_URL,
                    headers=headers,
                    timeout=15,
                ) as resp:
                    if resp.status != 200:
                        errors["base"] = "invalid_cookie"
                        return self.async_show_form(
                            step_id="user",
                            data_schema=_get_schema(default_sub_key=sub_key),
                            errors=errors,
                        )

                    result = await resp.json()
                    email = result.get("email", "Okänd")
                    name = f"Coop Sverige ({email})"

            except Exception as e:
                _LOGGER.error("Validation failed: %s", e)
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="user",
                    data_schema=_get_schema(default_sub_key=sub_key),
                    errors=errors,
                )

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

        return self.async_show_form(step_id="user", data_schema=_get_schema())

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return CoopOptionsFlowHandler(config_entry)


class CoopOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Coop Sverige."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        cookie = self.config_entry.data.get(CONF_SESSION_COOKIE, "")
        sub_key = self.config_entry.data.get(CONF_SUB_KEY, DEFAULT_SUB_KEY)
        return self.async_show_form(
            step_id="init",
            data_schema=_get_schema(default_cookie=cookie, default_sub_key=sub_key),
        )


CoopBonusConfigFlow = CoopConfigFlow
CoopBonusOptionsFlowHandler = CoopOptionsFlowHandler
