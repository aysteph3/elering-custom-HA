"""Unit tests for the Elering API payload parser."""

from __future__ import annotations

from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = REPO_ROOT / "elering_estfeed_custom_component" / "custom_components" / "elering_estfeed"


def _load_api_module():
    package_name = "_test_elering_estfeed"
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


class ParseMeterSnapshotTests(unittest.TestCase):
    """Verify meter snapshot parsing."""

    def setUp(self):
        self.client = EleringApiClient(session=None, access_token="token", meter_eic="meter")

    def test_month_start_uses_first_day_of_current_month(self):
        month_start = self.client._month_start(datetime(2026, 3, 21, 14, 35, 12, tzinfo=timezone.utc))

        self.assertEqual(month_start, datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc))

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

    def test_async_fetch_meter_data_combines_multiple_pages(self):
        responses = [
            {
                "meterData": [
                    {
                        "direction": "IMPORT",
                        "consumption": 1.5,
                        "unit": "kWh",
                        "periodEnd": "2026-03-21T00:00:00Z",
                        "meterReading": 10.5,
                    }
                ]
                * 1000,
                "pagination": {"totalPages": 2},
            },
            {
                "meterData": [
                    {
                        "direction": "IMPORT",
                        "consumption": 2.0,
                        "unit": "kWh",
                        "periodEnd": "2026-03-21T00:15:00Z",
                        "meterReading": 12.5,
                    }
                ],
                "pagination": {"totalPages": 2},
            },
        ]
        payloads = []

        async def _fake_post(payload):
            payloads.append(payload)
            return responses[len(payloads) - 1]

        with patch.object(self.client, "_async_post_meter_data_page", side_effect=_fake_post):
            snapshot = self._run_async(self.client.async_fetch_meter_data())

        self.assertEqual([payload["pagination"]["page"] for payload in payloads], [0, 1])
        self.assertEqual(snapshot.monthly_import_kwh, 1502.0)
        self.assertEqual(snapshot.daily_import_kwh, 1502.0)
        self.assertEqual(snapshot.cumulative_import_kwh, 12.5)

    def test_async_fetch_meter_data_preserves_latest_page_top_level_metadata(self):
        responses = [
            {
                "items": [
                    {
                        "direction": "IMPORT",
                        "quantity": 1000,
                        "unit": "Wh",
                        "periodEnd": "2026-03-21T00:00:00Z",
                    }
                ]
                * 1000,
                "cumulativeImportKwh": 500.0,
                "pagination": {"totalPages": 2},
            },
            {
                "items": [
                    {
                        "direction": "IMPORT",
                        "quantity": 2.0,
                        "unit": "kWh",
                        "periodEnd": "2026-03-21T00:15:00Z",
                    }
                ],
                "cumulativeImportKwh": 777.25,
                "pagination": {"totalPages": 2},
            },
        ]

        async def _fake_post(payload):
            return responses[payload["pagination"]["page"]]

        with patch.object(self.client, "_async_post_meter_data_page", side_effect=_fake_post):
            snapshot = self._run_async(self.client.async_fetch_meter_data())

        self.assertEqual(snapshot.monthly_import_kwh, 1002.0)
        self.assertEqual(snapshot.daily_import_kwh, 1002.0)
        self.assertEqual(snapshot.cumulative_import_kwh, 777.25)
        self.assertEqual(snapshot.last_period_end, "2026-03-21T00:15:00Z")

    def _run_async(self, coro):
        import asyncio

        return asyncio.run(coro)


if __name__ == "__main__":
    unittest.main()
