"""API client for Elering Estfeed."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
import logging

import aiohttp

from .const import METER_SEARCH_URL, TOKEN_URL

_LOGGER = logging.getLogger(__name__)


class EleringApiError(Exception):
    """Base exception raised for API failures."""


class EleringAuthenticationError(EleringApiError):
    """Raised when credentials are rejected by the API."""


class EleringAuthorizationError(EleringApiError):
    """Raised when token is valid but role/scope permissions are insufficient."""


class EleringTokenAuthenticationError(EleringAuthenticationError):
    """Raised when OAuth client credentials are rejected by token endpoint."""


class EleringTokenAuthorizationError(EleringAuthorizationError):
    """Raised when token endpoint forbids issuing token for this client."""


class EleringResourceAuthenticationError(EleringApiError):
    """Raised when resource endpoint rejects a bearer token."""


class EleringResourceAuthorizationError(EleringAuthorizationError):
    """Raised when resource endpoint denies permissions for requested resource."""


@dataclass
class MeterSnapshot:
    """Latest meter snapshot."""

    cumulative_import_kwh: float | None
    monthly_import_kwh: float | None
    daily_import_kwh: float | None
    last_period_end: str | None


class EleringApiClient:
    """Thin API client around the Elering Estfeed service."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        client_id: str,
        client_secret: str,
        meter_eic: str,
    ) -> None:
        self._session = session
        self._client_id = client_id
        self._client_secret = client_secret
        self._meter_eic = meter_eic
        self._access_token: str | None = None
        self._access_token_expires_at: datetime | None = None
        self._token_lock = asyncio.Lock()

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

        data = await self._post_meter_search(payload)
        _LOGGER.debug("Elering payload: %s", data)
        return self._parse_meter_snapshot(data)

    async def _post_meter_search(self, payload: dict) -> dict:
        """Call meter search with a valid bearer token and one auth retry."""
        for attempt in (1, 2):
            token = await self._get_access_token(force_refresh=attempt == 2)
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            }

            async with self._session.post(
                METER_SEARCH_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                body = await resp.text()
                _LOGGER.debug(
                    "Elering meter search response status=%s attempt=%s meter_eic=%s",
                    resp.status,
                    attempt,
                    self._meter_eic,
                )

                if resp.status == 401:
                    if attempt == 1:
                        _LOGGER.debug("Elering meter search returned 401, forcing token refresh")
                        continue
                    self._log_http_failure("meter_search", resp.status, body)
                    raise EleringResourceAuthenticationError(
                        "Meter search rejected bearer token (HTTP 401) even after refresh."
                    )
                if resp.status == 403:
                    self._log_http_failure("meter_search", resp.status, body)
                    raise EleringResourceAuthorizationError(
                        "Meter search denied by Datahub authorization (HTTP 403). "
                        "Token may be valid, but the technical user lacks required role/access context for this meter."
                    )
                if resp.status >= 400:
                    self._log_http_failure("meter_search", resp.status, body)
                    if self._looks_like_wrong_endpoint_family(body):
                        raise EleringApiError(
                            "Meter endpoint does not appear to be a Datahub JSON API response. "
                            f"Potential endpoint mismatch at {METER_SEARCH_URL}. HTTP {resp.status}"
                        )
                    raise EleringApiError(f"HTTP {resp.status}: {body[:500]}")
                return await resp.json()

        raise EleringAuthenticationError("Authentication failed after token refresh attempt")

    async def _get_access_token(self, force_refresh: bool = False) -> str:
        """Get or renew OAuth2 access token with client credentials."""
        async with self._token_lock:
            now = datetime.now(timezone.utc)
            if not force_refresh and self._access_token and self._access_token_expires_at:
                if now + timedelta(seconds=60) < self._access_token_expires_at:
                    return self._access_token

            form_data = {
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": "openid",
            }
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            }

            async with self._session.post(
                TOKEN_URL,
                data=form_data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                body = await resp.text()
                _LOGGER.debug("Elering token endpoint response status=%s", resp.status)
                if resp.status in (400, 401):
                    self._log_http_failure("token", resp.status, body)
                    raise EleringTokenAuthenticationError(
                        "Token request failed with invalid OAuth client credentials. "
                        f"HTTP {resp.status}: {body[:500]}"
                    )
                if resp.status == 403:
                    self._log_http_failure("token", resp.status, body)
                    raise EleringTokenAuthorizationError(
                        "Token request forbidden by authorization server (HTTP 403). "
                        "Technical user may be blocked or lack token grant permissions."
                    )
                if resp.status >= 400:
                    self._log_http_failure("token", resp.status, body)
                    raise EleringApiError(f"Token request failed HTTP {resp.status}: {body[:500]}")
                token_data = await resp.json()

            access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in")
            if not access_token or not expires_in:
                raise EleringApiError("Token response did not include access_token and expires_in")

            self._access_token = str(access_token)
            self._access_token_expires_at = now + timedelta(seconds=int(expires_in))

            token_context = self._extract_token_context(self._access_token)
            _LOGGER.debug(
                "Elering token acquisition succeeded exp=%s participant=%s roles=%s",
                self._access_token_expires_at.isoformat() if self._access_token_expires_at else None,
                token_context.get("market_participant_identification"),
                token_context.get("roles"),
            )
            return self._access_token

    def _log_http_failure(self, step: str, status: int, body: str) -> None:
        """Log an HTTP failure with safe truncated body and no secrets."""
        snippet = body[:500].replace("\n", " ").replace("\r", " ")
        _LOGGER.debug("Elering %s failed status=%s body_snippet=%s", step, status, snippet)

    def _extract_token_context(self, token: str) -> dict[str, str | list[str] | None]:
        """Extract safe debug context from JWT payload without verifying signature."""
        try:
            parts = token.split(".")
            if len(parts) < 2:
                return {}
            payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
            payload_raw = base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8")
            payload = json.loads(payload_raw)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return {}

        return {
            "market_participant_identification": payload.get("marketParticipantIdentification")
            or payload.get("market_participant_identification")
            or payload.get("sub"),
            "roles": payload.get("roles") or payload.get("realm_access", {}).get("roles"),
        }

    def _looks_like_wrong_endpoint_family(self, body: str) -> bool:
        """Detect obvious non-Datahub API responses to flag endpoint mismatch."""
        snippet = body.lower()
        return "<html" in snippet or "openid-connect" in snippet or "keycloak" in snippet

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
