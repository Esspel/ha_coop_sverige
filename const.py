DOMAIN = "ha_coop_sverige"

CONF_REFRESH_TOKEN = "refresh_token"
CONF_EMAIL = "email"
CONF_NAME = "name"
CONF_SUB_KEY = "ocp_apim_subscription_key"

API_BASE = "https://external.api.coop.se/loyalty"
TOKEN_URL = "https://login.coop.se/connect/token"
CLIENT_ID = "coopse_prod"

# Default subscription key discovered from network traffic
DEFAULT_SUB_KEY = "3becf0ce306f41a1ae94077c16798187"

PLATFORMS = ["sensor"]

# Sensor entity IDs
ENTITIES = [
    "total_kr",
    "total_points",
    "monthly_bonus_kr",
    "monthly_bonus_points",
    "member_prices_kr",
    "member_prices_points",
    "extra_bonus_kr",
    "extra_bonus_points",
    "next_level_kr",
    "days_until_next_level",
    "last_login",
    "member_id",
]