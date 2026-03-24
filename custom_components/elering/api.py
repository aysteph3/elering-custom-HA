"""API client for Elering Estfeed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import logging

import aiohttp

from .const import METER_SEARCH_URL

_LOGGER = logging.getLogger(__name__)


class EleringApiError(Exception):
    """Base exception raised for API failures."""


class EleringAuthenticationError(EleringApiError):
    """Raised when credentials are rejected by the API."""


@dataclass
class MeterSnapshot:
    """Latest meter snapshot."""

    cumulative_import_kwh: float | None
    monthly_import_kwh: float | None
    daily_import_kwh: float | None
    last_period_end: str | None


class EleringApiClient:
    """Thin API client around the Elering Estfeed service."""

    def __init__(self, session: aiohttp.ClientSession, api_token: str, meter_eic: str) -> None:
        self._session = session
        self._api_token = api_token
        self._meter_eic = meter_eic

    async def async_fetch_meter_data(self) -> MeterSnapshot:
        """Fetch recent meter data and convert it into HA-friendly sensor values."""
        now = datetime.now(timezone.utc)

        # Seven days gives you enough data to recover if HA was down for a while.
        start = (now - timedelta(days=7)).replace(second=0, microsecond=0)

        payload = {
            "searchCriteria": {
                "meterEic": self._meter_eic,
                "periodStart": start.isoformat().replace("+00:00", "Z"),
                "periodEnd": now.isoformat().replace("+00:00", "Z"),
            },
            "pagination": {
                "page": 0,
                "pageSize": 1000,
            },
        }

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_token}",
        }

        async with self._session.post(
            METER_SEARCH_URL,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            body = await resp.text()
            if resp.status in (401, 403):
                raise EleringAuthenticationError(
                    "Authentication failed: Elering API token is invalid, expired, or missing required access. "
                    f"HTTP {resp.status}: {body[:500]}"
                )
            if resp.status >= 400:
                raise EleringApiError(f"HTTP {resp.status}: {body[:500]}")
            data = await resp.json()

        _LOGGER.debug("Elering payload: %s", data)
        return self._parse_meter_snapshot(data)

    def _parse_meter_snapshot(self, data: dict) -> MeterSnapshot:
        """Parse the returned JSON.

        You will probably need to tweak the row field names after inspecting your real payload.
        This version tries several likely keys defensively.
        """
        rows = (
            data.get("meterData")
            or data.get("data")
            or data.get("content")
            or data.get("items")
            or []
        )

        if isinstance(rows, dict):
            rows = rows.get("items") or rows.get("content") or []

        parsed_rows: list[tuple[dict, float, str | None, date | None]] = []
        latest_end = None
        latest_day = None

        for row in rows:
            direction = str(
                row.get("direction")
                or row.get("flowDirection")
                or row.get("type")
                or "IMPORT"
            ).upper()

            if direction not in ("IMPORT", "IN", "CONSUMPTION", "A01"):
                continue

            quantity = (
                row.get("consumption")
                or row.get("quantity")
                or row.get("value")
                or row.get("amount")
                or 0
            )

            unit = str(row.get("unit") or "kWh")
            period_end = row.get("periodEnd") or row.get("to") or row.get("end")

            try:
                value = float(quantity)
            except (TypeError, ValueError):
                continue

            if unit.lower() == "wh":
                value_kwh = value / 1000
            elif unit.lower() == "mwh":
                value_kwh = value * 1000
            else:
                value_kwh = value

            row_day = self._parse_period_end_date(period_end)
            parsed_rows.append((row, value_kwh, period_end, row_day))

            if latest_end is None or (period_end and str(period_end) > str(latest_end)):
                latest_end = period_end
                latest_day = row_day

        daily_import_kwh = 0.0
        monthly_import_kwh = 0.0
        cumulative_import_kwh = self._extract_cumulative_reading(data)

        for row, value_kwh, period_end, row_day in parsed_rows:
            if row_day is None or latest_day is None:
                cumulative_import_kwh = self._pick_latest_cumulative_reading(
                    current_value=cumulative_import_kwh,
                    row=row,
                    period_end=period_end,
                    latest_end=latest_end,
                )
                continue

            if row_day.year == latest_day.year and row_day.month == latest_day.month:
                monthly_import_kwh += value_kwh

            if row_day == latest_day:
                daily_import_kwh += value_kwh

            cumulative_import_kwh = self._pick_latest_cumulative_reading(
                current_value=cumulative_import_kwh,
                row=row,
                period_end=period_end,
                latest_end=latest_end,
            )

        return MeterSnapshot(
            cumulative_import_kwh=round(cumulative_import_kwh, 3)
            if cumulative_import_kwh is not None
            else None,
            monthly_import_kwh=round(monthly_import_kwh, 3) if latest_day is not None else None,
            daily_import_kwh=round(daily_import_kwh, 3) if latest_day is not None else None,
            last_period_end=latest_end,
        )

    def _extract_cumulative_reading(self, data: dict) -> float | None:
        """Extract a true cumulative reading from the payload when available."""
        return self._coerce_float_from_keys(
            data,
            (
                "cumulativeImportKwh",
                "totalImportKwh",
                "meterReadingKwh",
                "meterRegisterKwh",
                "readingKwh",
            ),
        )

    def _pick_latest_cumulative_reading(
        self,
        current_value: float | None,
        row: dict,
        period_end: str | None,
        latest_end: str | None,
    ) -> float | None:
        """Prefer a cumulative reading on the latest row when present."""
        if latest_end is not None and period_end is not None and str(period_end) != str(latest_end):
            return current_value

        row_value = self._coerce_float_from_keys(
            row,
            (
                "cumulativeImportKwh",
                "cumulativeQuantity",
                "cumulativeValue",
                "meterReading",
                "meterRegister",
                "registerValue",
                "reading",
                "readingValue",
                "totalImportKwh",
                "totalConsumptionKwh",
            ),
        )
        if row_value is None:
            return current_value
        return row_value

    def _coerce_float_from_keys(self, data: dict, keys: tuple[str, ...]) -> float | None:
        """Return the first key that can be parsed as a float."""
        for key in keys:
            if key not in data:
                continue
            try:
                return float(data[key])
            except (TypeError, ValueError):
                continue
        return None

    def _parse_period_end_date(self, value: str | None) -> date | None:
        """Parse the row period end into a date."""
        if not value:
            return None

        try:
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized).date()
        except ValueError:
            return None
