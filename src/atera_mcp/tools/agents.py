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
"""Agents (monitored machines)."""

from typing import Annotated, Any
from urllib.parse import quote

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..api_client import AteraClient
from ._common import READ_ONLY, ClientFactory, ItemsInPage, Offset, Page, list_result, locate, page_params, run_tool

# Fields kept in the list view; atera_agents_get returns the full record.
SUMMARY_FIELDS = (
    "AgentID",
    "AgentName",
    "MachineName",
    "CustomerID",
    "CustomerName",
    "FolderName",
    "AgentType",
    "Online",
    "LastSeenDate",
    "OSType",
    "OS",
    "CurrentUser",
    "IPAddresses",
    "Vendor",
    "Model",
    "HardwareSerialNumber",
)


def register(mcp: FastMCP, client_factory: ClientFactory) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def atera_agents_list(
        page: Page = None,
        itemsInPage: ItemsInPage = None,
        customerId: Annotated[int | None, Field(description="Only this customer's agents.")] = None,
        offset: Offset = None,
    ) -> str:
        """List agents (monitored machines): name, customer, online state, OS, last seen, user.

        Use atera_agents_get for one agent's full hardware and software detail.
        """

        async def action(client: AteraClient) -> dict:
            number, size, start = locate(offset, page, itemsInPage)
            params = page_params(number, size)
            if customerId is not None:
                params["CustomerID"] = int(customerId)
            return list_result(await client.get("/agents", params), SUMMARY_FIELDS, number, size, start)

        return await run_tool("atera_agents_list", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def atera_agents_get(
        agentId: Annotated[int, Field(description="Agent id (from atera_agents_list).")],
    ) -> str:
        """Get one agent's full record: hardware, OS, IPs, antivirus, Office, last reboot."""

        async def action(client: AteraClient) -> Any:
            return await client.get(f"/agents/{int(agentId)}")

        return await run_tool("atera_agents_get", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def atera_agents_get_by_machine(
        machineName: Annotated[str, Field(description="Computer name, e.g. WS-001.")],
    ) -> str:
        """Find the agent(s) installed on a machine by its computer name."""

        async def action(client: AteraClient) -> Any:
            name = machineName.strip()
            if not name:
                raise ValueError("machineName is required")
            return await client.get(f"/agents/machine/{quote(name, safe='')}")

        return await run_tool("atera_agents_get_by_machine", client_factory, action)
