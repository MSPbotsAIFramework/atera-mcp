# Copyright 2026 MSPbots.ai
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Async client for the Atera REST API (v3)."""

import asyncio
import re
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from ._json import error_envelope
from .config import API_BASE_URL

logger = logging.getLogger("atera_mcp.api")

_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 2
_MAX_BACKOFF_SECONDS = 20.0
# Whole-call budget including retries; the gateway times a tool call out at 120s.
_CALL_BUDGET_SECONDS = 100.0

# One connection pool for the process. It never holds credentials: the
# Authorization header is built per request from the caller's own
# token, so sharing the pool across tenants is safe.
_shared_http_client: httpx.AsyncClient | None = None


def _get_shared_http_client() -> httpx.AsyncClient:
    global _shared_http_client
    if _shared_http_client is None:
        _shared_http_client = httpx.AsyncClient(timeout=_TIMEOUT)
    return _shared_http_client


# status_code -> (error code, retryable). 0 means no HTTP response at all
# (connection error or timeout).
_STATUS_TO_CODE: dict[int, tuple[str, bool]] = {
    0: ("upstream_error", True),
    400: ("invalid_argument", False),
    401: ("unauthorized", False),
    403: ("unauthorized", False),
    404: ("not_found", False),
    422: ("invalid_argument", False),
    429: ("rate_limited", True),
}


def classify_status(status_code: int) -> tuple[str, bool]:
    if status_code in _STATUS_TO_CODE:
        return _STATUS_TO_CODE[status_code]
    if status_code >= 500:
        return "upstream_error", True
    if status_code >= 400:
        return "invalid_argument", False
    return "upstream_error", True


class AteraError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Atera API error {status_code}: {message}")

    def to_envelope(self) -> str:
        code, retryable = classify_status(self.status_code)
        return error_envelope(code, self.message, retryable)


_JWT_SEGMENT = re.compile(r"^[A-Za-z0-9_-]+={0,2}$")


def is_jwt(token: str) -> bool:
    """True for JWT-shaped keys (three base64url segments, header starting "eyJ")."""
    parts = token.split(".")
    return len(parts) == 3 and parts[0].startswith("eyJ") and all(p and _JWT_SEGMENT.match(p) for p in parts)


@dataclass(frozen=True)
class AteraCredentials:
    api_key: str

    def __repr__(self) -> str:  # never leak the key into logs or tracebacks
        return "AteraCredentials(api_key=<redacted>)"


class AteraClient:
    """Thin wrapper over the Atera API for one caller's key."""

    def __init__(self, credentials: AteraCredentials, http_client: httpx.AsyncClient | None = None):
        self._credentials = credentials
        self._http = http_client
        self.base_url = API_BASE_URL

    def _headers(self) -> dict[str, str]:
        key = self._credentials.api_key
        # Current Atera API tokens are JWTs and are accepted only as a Bearer
        # token; older static keys are sent in X-API-KEY. Never send both.
        auth = {"Authorization": f"Bearer {key}"} if is_jwt(key) else {"X-API-KEY": key}
        return auth | {"Accept": "application/json"}

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self.request("GET", path, params=params)

    async def post(self, path: str, params: dict[str, Any] | None = None, body: Any = None) -> Any:
        return await self.request("POST", path, params=params, body=body)

    async def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: Any = None,
    ) -> Any:
        http = self._http or _get_shared_http_client()
        url = f"{self.base_url}{path}"
        query = {k: _param_value(v) for k, v in (params or {}).items() if v is not None}
        headers = self._headers()
        if body is not None:
            headers["Content-Type"] = "application/json"

        started = time.monotonic()
        attempt = 0
        while True:
            t0 = time.monotonic()
            try:
                resp = await http.request(method, url, params=query, json=body, headers=headers)
            except httpx.TimeoutException as e:
                status, error = 0, AteraError(0, f"Timed out calling Atera ({method} {path})")
                resp, exc = None, e
            except httpx.RequestError as e:
                status = 0
                error = AteraError(0, f"Network error calling Atera ({method} {path}): {type(e).__name__}")
                resp, exc = None, e
            else:
                status, error, exc = resp.status_code, None, None

            logger.info(
                "atera_api method=%s path=%s status=%s ms=%d attempt=%d",
                method,
                path,
                status,
                (time.monotonic() - t0) * 1000,
                attempt,
            )

            retryable = status == 0 or status in _RETRYABLE_STATUS
            if retryable and attempt < _MAX_RETRIES:
                delay = _retry_delay(resp, attempt)
                if time.monotonic() - started + delay < _CALL_BUDGET_SECONDS:
                    attempt += 1
                    await asyncio.sleep(delay)
                    continue

            if error is not None:
                raise error from exc
            assert resp is not None
            if resp.status_code >= 400:
                raise AteraError(resp.status_code, _error_message(resp))
            return _parse_body(resp)


def _param_value(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _retry_delay(resp: httpx.Response | None, attempt: int) -> float:
    if resp is not None:
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                return max(0.0, min(float(retry_after), _MAX_BACKOFF_SECONDS))
            except ValueError:
                pass
    return min(float(2**attempt), _MAX_BACKOFF_SECONDS)


def _parse_body(resp: httpx.Response) -> Any:
    if not resp.content:
        return None
    try:
        return resp.json()
    except ValueError:
        return {"raw_response": resp.text[:2000]}


def _error_message(resp: httpx.Response) -> str:
    """Short, credential-free description of an Atera error response."""
    fallback = f"Atera returned HTTP {resp.status_code}"
    try:
        payload = resp.json()
    except ValueError:
        return fallback
    if isinstance(payload, dict):
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            parts = []
            for err in errors[:3]:
                if isinstance(err, dict):
                    text = err.get("detail") or err.get("title") or err.get("code")
                    if text:
                        parts.append(str(text))
            if parts:
                return f"{fallback}: " + "; ".join(parts)[:500]
        for key in ("message", "error", "detail"):
            if isinstance(payload.get(key), str):
                return f"{fallback}: {payload[key][:500]}"
    return fallback
