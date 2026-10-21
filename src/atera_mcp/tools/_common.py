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
"""Shared argument types, result shaping and the error-handling wrapper."""

import logging
import time
from collections.abc import Awaitable, Callable, Iterable
from typing import Annotated, Any, get_args

from mcp.types import ToolAnnotations
from pydantic import Field

from .._json import dump_json_capped, error_envelope
from ..api_client import AteraClient, AteraError

logger = logging.getLogger("atera_mcp.tools")

ClientFactory = Callable[[], AteraClient | None]

MAX_PAGE_SIZE = 50  # Atera's own limit

READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=True)
WRITES = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True)

NOT_CONFIGURED = error_envelope(
    "not_configured", "Atera API key is missing for this request (X-Atera-Api-Key header).", False
)

Page = Annotated[int | None, Field(description="Page number, starting at 1 (default 1).")]
ItemsInPage = Annotated[int | None, Field(description=f"Items per page (default {MAX_PAGE_SIZE}, max {MAX_PAGE_SIZE}).")]
CustomerId = Annotated[int, Field(description="Atera customer id (from atera_customers_list).")]


def page_params(page: int | None, items_in_page: int | None) -> dict[str, Any]:
    size = MAX_PAGE_SIZE if items_in_page is None else max(1, min(int(items_in_page), MAX_PAGE_SIZE))
    return {"Page": max(1, int(page or 1)), "ItemsInPage": size}


def list_result(document: Any, fields: Iterable[str] | None = None) -> dict[str, Any]:
    """Shape an Atera page ``{items, page, totalPages, totalItemCount, nextLink}``.

    When ``fields`` is given, each item is reduced to those keys.
    """
    doc = document if isinstance(document, dict) else {}
    items = doc.get("items") or []
    if fields is not None:
        keep = tuple(fields)
        items = [{k: i[k] for k in keep if i.get(k) is not None} if isinstance(i, dict) else i for i in items]
    page = doc.get("page")
    total_pages = doc.get("totalPages")
    has_more = bool(doc.get("nextLink")) or (
        isinstance(page, int) and isinstance(total_pages, int) and page < total_pages
    )
    return {
        "items": items,
        "count": len(items),
        "page": page,
        "total_pages": total_pages,
        "total_items": doc.get("totalItemCount"),
        "has_more": has_more,
    }


def enum_value(value: Any, choices: Any) -> Any:
    """Canonical spelling of a case-insensitive match in ``choices`` (a Literal type).

    Any other value passes through unchanged, so the API decides (older callers sent free text).
    """
    if not isinstance(value, str):
        return value
    wanted = value.strip().lower()
    return next((c for c in get_args(choices) if isinstance(c, str) and c.lower() == wanted), value)


async def run_tool(
    name: str,
    client_factory: ClientFactory,
    action: Callable[[AteraClient], Awaitable[Any]],
) -> str:
    """Resolve the caller's client, run ``action``, and always return a string.

    Errors never escape as exceptions: they become the standard error envelope.
    """
    client = client_factory()
    if client is None:
        return NOT_CONFIGURED
    started = time.monotonic()
    try:
        result = await action(client)
    except AteraError as e:
        logger.info("tool=%s outcome=error status=%s ms=%d", name, e.status_code, _ms(started))
        return e.to_envelope()
    except ValueError as e:
        logger.info("tool=%s outcome=invalid_argument ms=%d", name, _ms(started))
        return error_envelope("invalid_argument", str(e), False)
    except Exception as e:  # noqa: BLE001 - tools must never raise
        logger.warning("tool=%s outcome=unexpected error=%s ms=%d", name, type(e).__name__, _ms(started))
        return error_envelope("upstream_error", f"Unexpected error: {type(e).__name__}", True)
    logger.info("tool=%s outcome=ok ms=%d", name, _ms(started))
    return result if isinstance(result, str) else dump_json_capped(result)


def _ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
