"""Constants for the Elering integration."""

DOMAIN = "elering"

CONF_API_TOKEN = "api_token"
CONF_COOKIE_HEADER = "cookie_header"  # Legacy key kept for migration only.
CONF_METER_EIC = "meter_eic"

METER_SEARCH_URL = "https://datahub.elering.ee/api/v1/meter-data/search"

DEFAULT_SCAN_INTERVAL_MINUTES = 15
