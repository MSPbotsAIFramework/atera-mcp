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
"""FastMCP factory and the per-request credential middleware."""

import contextvars
import uuid
from collections.abc import Callable

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from ._arguments import EnvelopeFastMCP
from .api_client import AteraClient, AteraCredentials
from .config import Settings

HEADER_API_KEY = "X-Atera-Api-Key"
REQUIRED_HEADERS = [HEADER_API_KEY]
OPTIONAL_HEADERS: list[str] = []

# Per-request isolation: the middleware sets these for the duration of one
# HTTP request and resets them in `finally`. Nothing credential-related is
# ever stored at module level.
_credentials_var: contextvars.ContextVar[AteraCredentials | None] = contextvars.ContextVar(
    "atera_credentials", default=None
)
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("atera_request_id", default="-")

INSTRUCTIONS = (
    "Atera is an all-in-one RMM and PSA platform for MSPs: remote monitoring of "
    "client devices (agents), alerting, and help-desk ticketing. Customers are "
    "the MSP's clients; contacts are people at those customers; agents are "
    "monitored Windows/Mac/Linux machines; alerts come from agents and "
    "network/SNMP/HTTP devices.\n"
    "Typical flows:\n"
    "- Find a client: atera_customers_list -> atera_customers_get.\n"
    "- Device questions: atera_agents_list(customerId) or "
    "atera_agents_get_by_machine(machineName) -> atera_alerts_by_agent.\n"
    "- Alert triage: atera_alerts_list(alertSeverity='Critical', archived=false).\n"
    "- Help desk: atera_tickets_list(ticketStatus='Open') -> atera_tickets_get; "
    "atera_tickets_add_comment adds an internal note by default.\n"
    "- People: atera_contacts_by_customer(customerId).\n"
    "All tools are always available (atera_navigate only lists one area). "
    "Lists use page / itemsInPage (max 50) and return {items, page, "
    "total_pages, total_items, has_more}. atera_customers_create, "
    "atera_tickets_create, atera_tickets_update and atera_tickets_add_comment "
    "change data: use them only when the user asks."
)


def get_client_from_context() -> AteraClient | None:
    """The Atera client for the current request, or None outside a request."""
    credentials = _credentials_var.get()
    if credentials is None:
        return None
    return AteraClient(credentials)


def _key_from_header(value: str | None) -> str:
    """Accept the key with or without a leading 'Bearer ' prefix."""
    parts = (value or "").split()
    if parts and parts[0].lower() == "bearer":
        parts = parts[1:]
    return " ".join(parts)


class GatewayCredentialsMiddleware:
    """Reads X-Atera-Api-Key on /mcp requests into the request context; 401 when missing."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        api_key = _key_from_header(request.headers.get(HEADER_API_KEY))
        if not api_key:
            await JSONResponse(
                {
                    "error": "Missing credentials",
                    "message": f"Required header missing: {HEADER_API_KEY}",
                    "required_headers": REQUIRED_HEADERS,
                    "optional_headers": OPTIONAL_HEADERS,
                },
                status_code=401,
            )(scope, receive, send)
            return

        request_id = (request.headers.get("x-request-id") or "").strip()[:64] or uuid.uuid4().hex[:12]
        creds_token = _credentials_var.set(AteraCredentials(api_key))
        rid_token = request_id_var.set(request_id)
        try:
            await self.app(scope, receive, send)
        finally:
            _credentials_var.reset(creds_token)
            request_id_var.reset(rid_token)


def create_mcp_server(settings: Settings | None = None) -> FastMCP:
    """Build the FastMCP server and register every Atera tool."""
    mcp = EnvelopeFastMCP(
        name="atera-mcp",
        instructions=INSTRUCTIONS,
        # The service sits behind the gateway, so Host is never localhost;
        # DNS-rebinding protection would reject those requests with 421.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        stateless_http=True,
    )

    client_factory: Callable[[], AteraClient | None] = get_client_from_context

    from .tools import agents, alerts, contacts, customers, navigation, tickets

    for module in (navigation, customers, agents, tickets, alerts, contacts):
        module.register(mcp, client_factory)

    return mcp
