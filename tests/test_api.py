"""Unit tests for the Elering API payload parser."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = REPO_ROOT / "custom_components" / "elektrilevi_meter"


def _load_api_module():
    package_name = "_test_elektrilevi_meter"
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


class ParseMeterSnapshotTests(unittest.TestCase):
    """Verify meter snapshot parsing."""

    def setUp(self):
        self.client = EleringApiClient(session=None, access_token="token", meter_eic="meter")

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
        self.assertEqual(snapshot.last_period_end, "2026-03-21T00:15:00Z")

    def test_uses_top_level_cumulative_reading_when_row_level_is_missing(self):
        snapshot = self.client._parse_meter_snapshot(
            {
                "cumulativeImportKwh": 550.25,
                "items": [
                    {
                        "direction": "IMPORT",
                        "quantity": 1200,
                        "unit": "Wh",
                        "periodEnd": "2026-03-21T08:00:00Z",
                    },
                    {
                        "direction": "IMPORT",
                        "quantity": 1.8,
                        "unit": "kWh",
                        "periodEnd": "2026-03-21T09:00:00Z",
                    },
                ],
            }
        )

        self.assertEqual(snapshot.cumulative_import_kwh, 550.25)
        self.assertEqual(snapshot.monthly_import_kwh, 3.0)
        self.assertEqual(snapshot.daily_import_kwh, 3.0)

    def test_ignores_non_import_rows_and_handles_missing_cumulative_reading(self):
        snapshot = self.client._parse_meter_snapshot(
            {
                "content": [
                    {
                        "direction": "EXPORT",
                        "value": 10,
                        "unit": "kWh",
                        "periodEnd": "2026-03-21T08:00:00Z",
                    },
                    {
                        "direction": "IMPORT",
                        "value": 2,
                        "unit": "kWh",
                        "periodEnd": "2026-03-21T09:00:00Z",
                    },
                    {
                        "direction": "IMPORT",
                        "value": 5,
                        "unit": "kWh",
                        "periodEnd": "2026-02-28T23:45:00Z",
                    },
                ]
            }
        )

        self.assertIsNone(snapshot.cumulative_import_kwh)
        self.assertEqual(snapshot.monthly_import_kwh, 2.0)
        self.assertEqual(snapshot.daily_import_kwh, 2.0)


class FetchMeterDataErrorTests(unittest.IsolatedAsyncioTestCase):
    """Verify API error handling."""

    async def test_raises_authentication_error_for_401(self):
        response = _MockResponse(status=401, text_data='{"error":"unauthorized"}')
        session = _MockSession(response)
        client = EleringApiClient(session=session, access_token="token", meter_eic="meter")

        with self.assertRaises(EleringAuthenticationError):
            await client.async_fetch_meter_data()

    async def test_raises_api_error_for_other_4xx_5xx(self):
        response = _MockResponse(status=500, text_data='{"error":"boom"}')
        session = _MockSession(response)
        client = EleringApiClient(session=session, access_token="token", meter_eic="meter")

        with self.assertRaises(EleringApiError):
            await client.async_fetch_meter_data()


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
    def __init__(self, response):
        self._response = response

    def post(self, *args, **kwargs):
        return self._response


if __name__ == "__main__":
    unittest.main()
