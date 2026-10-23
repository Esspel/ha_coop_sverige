"""Constants for the Coop Sverige integration."""

DOMAIN = "ha_coop_sverige"

CONF_SESSION_COOKIE = "session_cookie"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_EMAIL = "email"
CONF_NAME = "name"
CONF_SUB_KEY = "ocp_apim_subscription_key"

API_BASE = "https://external.api.coop.se/loyalty"
TOKEN_URL = "https://www.coop.se/api/spa/token"
CLIENT_ID = "coopse_prod"

# Default subscription key discovered from network traffic
DEFAULT_SUB_KEY = "3becf0ce306f41a1ae94077c16798187"

# Supported Home Assistant platforms
PLATFORMS = ["sensor", "todo"]

# Base URLs
SHOPPING_LIST_BASE = "https://proxy.api.coop.se/digital/shoppinglist"
PERSONAL_OFFERS_BASE = "https://external.api.coop.se/digital/personaloffers"
STORE_BASE = "https://proxy.api.coop.se/external/store"
OFFERS_BASE = "https://external.api.coop.se/dke/offers"

# API Versions
API_V1 = "v1"
API_V2 = "v2"
API_V3 = "v3"
API_V4 = "v4"

# Services
SERVICE_ADD_ITEM = "add_item"
SERVICE_UPDATE_ITEM = "update_item"
SERVICE_DELETE_ITEM = "delete_item"
SERVICE_CLEAR_COMPLETED = "clear_completed"
SERVICE_CREATE_SHOPPING_LIST = "create_shopping_list"
SERVICE_DELETE_SHOPPING_LIST = "delete_shopping_list"
SERVICE_GET_STORE_INFO = "get_store_info"
SERVICE_GET_STORE_OFFERS = "get_store_offers"
SERVICE_GET_PERSONAL_OFFERS = "get_personal_offers"
