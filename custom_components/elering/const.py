"""Constants for the Elering integration."""

DOMAIN = "elering"

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_API_TOKEN = "api_token"  # Legacy key kept for migration only.
CONF_COOKIE_HEADER = "cookie_header"  # Legacy key kept for migration only.
CONF_METER_EIC = "meter_eic"

METER_SEARCH_URL = "https://estfeed.elering.ee/api/public/v1/meter-data/search" 
TOKEN_URL = "https://kc.elering.ee/realms/estfeed/protocol/openid-connect/token"

DEFAULT_SCAN_INTERVAL_MINUTES = 15
