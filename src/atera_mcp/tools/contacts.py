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
"""Contacts (end users at customers)."""

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..api_client import AteraClient
from ._common import READ_ONLY, ClientFactory, CustomerId, ItemsInPage, Page, list_result, page_params, run_tool


def register(mcp: FastMCP, client_factory: ClientFactory) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def atera_contacts_list(page: Page = None, itemsInPage: ItemsInPage = None) -> str:
        """List contacts (end users at all customers): name, e-mail, phone, job title, customer."""

        async def action(client: AteraClient) -> dict:
            return list_result(await client.get("/contacts", page_params(page, itemsInPage)))

        return await run_tool("atera_contacts_list", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def atera_contacts_get(
        contactId: Annotated[int, Field(description="Contact id (EndUserID).")],
    ) -> str:
        """Get one contact's full record."""

        async def action(client: AteraClient) -> Any:
            return await client.get(f"/contacts/{int(contactId)}")

        return await run_tool("atera_contacts_get", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def atera_contacts_by_customer(
        customerId: CustomerId,
        page: Page = None,
        itemsInPage: ItemsInPage = None,
    ) -> str:
        """List the contacts of one customer."""

        async def action(client: AteraClient) -> dict:
            return list_result(
                await client.get(f"/contacts/customer/{int(customerId)}", page_params(page, itemsInPage))
            )

        return await run_tool("atera_contacts_by_customer", client_factory, action)
