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
"""Customers (the MSP's clients)."""

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..api_client import AteraClient
from ._common import READ_ONLY, WRITES, ClientFactory, CustomerId, ItemsInPage, Page, list_result, page_params, run_tool

Text = Annotated[str | None, Field(description="Optional.")]


def register(mcp: FastMCP, client_factory: ClientFactory) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def atera_customers_list(page: Page = None, itemsInPage: ItemsInPage = None) -> str:
        """List customers (the MSP's clients) with id, name, domain and contact details."""

        async def action(client: AteraClient) -> dict:
            return list_result(await client.get("/customers", page_params(page, itemsInPage)))

        return await run_tool("atera_customers_list", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def atera_customers_get(customerId: CustomerId) -> str:
        """Get one customer's full record."""

        async def action(client: AteraClient) -> Any:
            return await client.get(f"/customers/{int(customerId)}")

        return await run_tool("atera_customers_get", client_factory, action)

    @mcp.tool(annotations=WRITES)
    async def atera_customers_create(
        CustomerName: Annotated[str, Field(description="Customer (company) name.")],
        BusinessNumber: Text = None,
        Domain: Annotated[str | None, Field(description="E-mail domain, e.g. example.com.")] = None,
        Address: Text = None,
        City: Text = None,
        State: Text = None,
        Country: Text = None,
        ZipCode: Text = None,
        Phone: Text = None,
        Fax: Text = None,
        Notes: Text = None,
        Website: Text = None,
    ) -> str:
        """Create a customer in Atera. Changes data: only when the user explicitly asks."""

        async def action(client: AteraClient) -> Any:
            body = {
                k: v
                for k, v in {
                    "CustomerName": CustomerName,
                    "BusinessNumber": BusinessNumber,
                    "Domain": Domain,
                    "Address": Address,
                    "City": City,
                    "State": State,
                    "Country": Country,
                    "ZipCode": ZipCode,
                    "Phone": Phone,
                    "Fax": Fax,
                    "Notes": Notes,
                    "Website": Website,
                }.items()
                if v is not None
            }
            return await client.post("/customers", body=body)

        return await run_tool("atera_customers_create", client_factory, action)
