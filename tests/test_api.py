"""Unit tests for Elering API auth and payload parsing."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = REPO_ROOT / "custom_components" / "elering"


def _load_api_module():
    package_name = "_test_elering"
    package = types.ModuleType(package_name)
    package.__path__ = [str(PACKAGE_DIR)]
    sys.modules[package_name] = package

    aiohttp_stub = types.ModuleType("aiohttp")

    class _ClientTimeout:
        def __init__(self, total):
            self.total = total

    aiohttp_stub.ClientSession = object
    aiohttp_stub.ClientTimeout = _ClientTimeout
    sys.modules["aiohttp"] = aiohttp_stub

    const_spec = spec_from_file_location(f"{package_name}.const", PACKAGE_DIR / "const.py")
    const_module = module_from_spec(const_spec)
    assert const_spec and const_spec.loader
    sys.modules[f"{package_name}.const"] = const_module
    const_spec.loader.exec_module(const_module)

    api_spec = spec_from_file_location(f"{package_name}.api", PACKAGE_DIR / "api.py")
    api_module = module_from_spec(api_spec)
    assert api_spec and api_spec.loader
    sys.modules[f"{package_name}.api"] = api_module
    api_spec.loader.exec_module(api_module)
    return api_module


API_MODULE = _load_api_module()
EleringApiClient = API_MODULE.EleringApiClient
EleringApiError = API_MODULE.EleringApiError
EleringAuthenticationError = API_MODULE.EleringAuthenticationError
TOKEN_URL = API_MODULE.TOKEN_URL
METER_SEARCH_URL = API_MODULE.METER_SEARCH_URL


class FetchMeterDataOAuthTests(unittest.IsolatedAsyncioTestCase):
    """Verify OAuth2 and request behavior."""

    async def test_acquires_token_and_calls_meter_endpoint_with_bearer(self):
        session = _MockSession(
            [
                _MockResponse(status=200, json_data={"access_token": "abc", "expires_in": 300}),
                _MockResponse(status=200, json_data={"meterData": []}),
            ]
        )
        client = EleringApiClient(session=session, client_id="id", client_secret="secret", meter_eic="meter")

        await client.async_fetch_meter_data()

        self.assertEqual(session.calls[0]["url"], TOKEN_URL)
        self.assertEqual(session.calls[0]["kwargs"]["data"]["grant_type"], "client_credentials")
        self.assertEqual(session.calls[1]["url"], METER_SEARCH_URL)
        self.assertEqual(session.calls[1]["kwargs"]["headers"]["Authorization"], "Bearer abc")

    async def test_reacquires_token_after_meter_401(self):
        session = _MockSession(
            [
                _MockResponse(status=200, json_data={"access_token": "abc", "expires_in": 300}),
                _MockResponse(status=401, text_data='{"error":"bad token"}'),
                _MockResponse(status=200, json_data={"access_token": "def", "expires_in": 300}),
                _MockResponse(status=200, json_data={"meterData": []}),
            ]
        )
        client = EleringApiClient(session=session, client_id="id", client_secret="secret", meter_eic="meter")

        await client.async_fetch_meter_data()

        self.assertEqual(session.calls[1]["kwargs"]["headers"]["Authorization"], "Bearer abc")
        self.assertEqual(session.calls[3]["kwargs"]["headers"]["Authorization"], "Bearer def")

    async def test_invalid_credentials_raise_auth_error(self):
        session = _MockSession([_MockResponse(status=401, text_data='{"error":"invalid_client"}')])
        client = EleringApiClient(session=session, client_id="bad", client_secret="bad", meter_eic="meter")

        with self.assertRaises(EleringAuthenticationError):
            await client.async_fetch_meter_data()


class ParseMeterSnapshotTests(unittest.TestCase):
    """Verify meter snapshot parsing remains intact."""

    def setUp(self):
        self.client = EleringApiClient(session=None, client_id="id", client_secret="secret", meter_eic="meter")

    def test_uses_latest_row_cumulative_reading_and_computes_daily_monthly(self):
        snapshot = self.client._parse_meter_snapshot(
            {
                "meterData": [
                    {
                        "direction": "IMPORT",
                        "consumption": 2.5,
                        "unit": "kWh",
                        "periodEnd": "2026-03-20T23:45:00Z",
                        "meterReading": 102.5,
                    },
                    {
                        "direction": "IMPORT",
                        "consumption": 3.0,
                        "unit": "kWh",
                        "periodEnd": "2026-03-21T00:00:00Z",
                        "meterReading": 105.5,
                    },
                    {
                        "direction": "IMPORT",
                        "consumption": 4.0,
                        "unit": "kWh",
                        "periodEnd": "2026-03-21T00:15:00Z",
                        "meterReading": 109.5,
                    },
                ]
            }
        )

        self.assertEqual(snapshot.cumulative_import_kwh, 109.5)
        self.assertEqual(snapshot.monthly_import_kwh, 9.5)
        self.assertEqual(snapshot.daily_import_kwh, 7.0)


class _MockResponse:
    def __init__(self, status, text_data="", json_data=None):
        self.status = status
        self._text_data = text_data
        self._json_data = json_data or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return self._text_data

    async def json(self):
        return self._json_data


class _MockSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.method_calls = []

    def post(self, url, **kwargs):
        self.calls.append({"url": url, "kwargs": kwargs})
        return self._responses.pop(0)


if __name__ == "__main__":
    unittest.main()
