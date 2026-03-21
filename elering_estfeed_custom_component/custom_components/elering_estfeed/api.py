"""API client for Elering Estfeed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging

import aiohttp

from .const import METER_SEARCH_URL

_LOGGER = logging.getLogger(__name__)


@dataclass
class MeterSnapshot:
    """Latest meter snapshot."""

    total_import_kwh: float | None
    current_import_w: float | None
    last_period_end: str | None


class EleringApiClient:
    """Thin API client around the Elering Estfeed service."""

    def __init__(self, session: aiohttp.ClientSession, access_token: str, meter_eic: str) -> None:
        self._session = session
        self._access_token = access_token
        self._meter_eic = meter_eic

    async def async_fetch_meter_data(self) -> MeterSnapshot:
        """Fetch recent meter data and convert it into HA-friendly sensor values."""
        now = datetime.now(UTC)

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
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        async with self._session.post(
            METER_SEARCH_URL,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            body = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"HTTP {resp.status}: {body[:500]}")
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

        total_import_kwh = 0.0
        latest_end = None
        latest_power_w = None

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
            period = str(row.get("resolution") or row.get("period") or "PT15M").upper()
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

            total_import_kwh += value_kwh

            if latest_end is None or (period_end and str(period_end) > str(latest_end)):
                latest_end = period_end

                # Convert interval energy to interval-average power.
                if period == "PT15M":
                    latest_power_w = value_kwh * 4000
                elif period == "PT1H":
                    latest_power_w = value_kwh * 1000
                else:
                    latest_power_w = None

        return MeterSnapshot(
            total_import_kwh=round(total_import_kwh, 3) if rows else None,
            current_import_w=round(latest_power_w, 1) if latest_power_w is not None else None,
            last_period_end=latest_end,
        )
