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
"""Per-area tool guide. All tools are always listed; these only describe them."""

from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..api_client import AteraClient
from ._common import READ_ONLY, ClientFactory, run_tool

DOMAIN_TOOLS: dict[str, dict[str, str]] = {
    "customers": {
        "atera_customers_list": "List customers.",
        "atera_customers_get": "One customer.",
        "atera_customers_create": "Create a customer (write).",
    },
    "agents": {
        "atera_agents_list": "List agents, optionally for one customer.",
        "atera_agents_get": "One agent's full record.",
        "atera_agents_get_by_machine": "Agent(s) on a machine name.",
    },
    "tickets": {
        "atera_tickets_list": "List tickets by status, customer, technician or date.",
        "atera_tickets_get": "One ticket.",
        "atera_tickets_create": "Create a ticket (write).",
        "atera_tickets_update": "Update a ticket (write).",
        "atera_tickets_add_comment": "Add a comment (write).",
    },
    "alerts": {
        "atera_alerts_list": "List alerts by severity, customer, archived.",
        "atera_alerts_get": "One alert.",
        "atera_alerts_by_agent": "Alerts of one agent.",
        "atera_alerts_by_device": "Alerts of one monitored device.",
    },
    "contacts": {
        "atera_contacts_list": "List contacts.",
        "atera_contacts_get": "One contact.",
        "atera_contacts_by_customer": "Contacts of one customer.",
    },
}


def register(mcp: FastMCP, client_factory: ClientFactory) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def atera_navigate(
        domain: Annotated[
            Literal["customers", "agents", "tickets", "alerts", "contacts"],
            Field(description="Area to show tools for."),
        ],
    ) -> str:
        """Show which tools cover one area: customers, agents, tickets, alerts or contacts.

        All tools are always available; this is only a guide. Makes no API call.
        """

        async def action(_client: AteraClient) -> dict:
            return {"domain": domain, "tools": DOMAIN_TOOLS[domain]}

        return await run_tool("atera_navigate", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def atera_back() -> str:
        """List the available areas. Kept for older clients; every tool is always available."""

        async def action(_client: AteraClient) -> dict:
            return {"domains": {name: sorted(tools) for name, tools in DOMAIN_TOOLS.items()}}

        return await run_tool("atera_back", client_factory, action)
