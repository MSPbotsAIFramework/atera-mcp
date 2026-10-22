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
"""Monitoring alerts."""

from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..api_client import AteraClient
from ._common import READ_ONLY, ClientFactory, ItemsInPage, Offset, Page, list_result, locate, page_params, run_tool


def register(mcp: FastMCP, client_factory: ClientFactory) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def atera_alerts_list(
        page: Page = None,
        itemsInPage: ItemsInPage = None,
        alertSeverity: Annotated[
            Literal["Information", "Warning", "Critical"] | None, Field(description="Severity.")
        ] = None,
        customerId: Annotated[int | None, Field(description="Only this customer's alerts.")] = None,
        archived: Annotated[bool | None, Field(description="true = archived alerts, false = active ones.")] = None,
        offset: Offset = None,
    ) -> str:
        """List monitoring alerts: title, severity, source device/agent, customer, created date."""

        async def action(client: AteraClient) -> dict:
            number, size, start = locate(offset, page, itemsInPage)
            params = page_params(number, size)
            for key, value in (("AlertSeverity", alertSeverity), ("CustomerID", customerId), ("Archived", archived)):
                if value is not None:
                    params[key] = value
            return list_result(await client.get("/alerts", params), None, number, size, start)

        return await run_tool("atera_alerts_list", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def atera_alerts_get(
        alertId: Annotated[int, Field(description="Alert id (from atera_alerts_list).")],
    ) -> str:
        """Get one alert's full record."""

        async def action(client: AteraClient) -> Any:
            return await client.get(f"/alerts/{int(alertId)}")

        return await run_tool("atera_alerts_get", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def atera_alerts_by_agent(
        agentId: Annotated[int, Field(description="Agent id.")],
        page: Page = None,
        itemsInPage: ItemsInPage = None,
        offset: Offset = None,
    ) -> str:
        """List the alerts raised by one agent (monitored machine)."""

        async def action(client: AteraClient) -> dict:
            number, size, start = locate(offset, page, itemsInPage)
            document = await client.get(f"/alerts/agent/{int(agentId)}", page_params(number, size))
            return list_result(document, None, number, size, start)

        return await run_tool("atera_alerts_by_agent", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def atera_alerts_by_device(
        deviceId: Annotated[int, Field(description="Monitored device id (SNMP/TCP/HTTP/generic device).")],
        page: Page = None,
        itemsInPage: ItemsInPage = None,
        offset: Offset = None,
    ) -> str:
        """List the alerts raised by one network-monitored device (SNMP, TCP, HTTP or generic)."""

        async def action(client: AteraClient) -> dict:
            number, size, start = locate(offset, page, itemsInPage)
            document = await client.get(f"/alerts/device/{int(deviceId)}", page_params(number, size))
            return list_result(document, None, number, size, start)

        return await run_tool("atera_alerts_by_device", client_factory, action)
