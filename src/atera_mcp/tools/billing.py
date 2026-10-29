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
"""Billing (read-only): invoices and contracts. PRD-21196."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..api_client import AteraClient
from ._common import (
    READ_ONLY,
    ClientFactory,
    ContractId,
    CustomerId,
    InvoiceNumber,
    ItemsInPage,
    Offset,
    Page,
    list_result,
    locate,
    page_params,
    run_tool,
)


def register(mcp: FastMCP, client_factory: ClientFactory) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def atera_invoices_list(page: Page = None, itemsInPage: ItemsInPage = None, offset: Offset = None) -> str:
        """List billing invoices."""

        async def action(client: AteraClient) -> dict:
            number, size, start = locate(offset, page, itemsInPage)
            return list_result(await client.get("/billing/invoices", page_params(number, size)), None, number, size, start)

        return await run_tool("atera_invoices_list", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def atera_invoice_get(invoiceNumber: InvoiceNumber) -> str:
        """Get one invoice's full record, including its line items."""

        async def action(client: AteraClient) -> Any:
            return await client.get(f"/billing/invoice/{invoiceNumber}")

        return await run_tool("atera_invoice_get", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def atera_contracts_list(page: Page = None, itemsInPage: ItemsInPage = None, offset: Offset = None) -> str:
        """List billing contracts (service agreements)."""

        async def action(client: AteraClient) -> dict:
            number, size, start = locate(offset, page, itemsInPage)
            return list_result(await client.get("/contracts", page_params(number, size)), None, number, size, start)

        return await run_tool("atera_contracts_list", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def atera_contract_get(contractId: ContractId) -> str:
        """Get one contract's full record."""

        async def action(client: AteraClient) -> Any:
            return await client.get(f"/contracts/{int(contractId)}")

        return await run_tool("atera_contract_get", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def atera_contracts_by_customer(
        customerId: CustomerId,
        page: Page = None,
        itemsInPage: ItemsInPage = None,
        offset: Offset = None,
    ) -> str:
        """List the contracts (service agreements) of one customer."""

        async def action(client: AteraClient) -> dict:
            number, size, start = locate(offset, page, itemsInPage)
            document = await client.get(f"/contracts/customer/{int(customerId)}", page_params(number, size))
            return list_result(document, None, number, size, start)

        return await run_tool("atera_contracts_by_customer", client_factory, action)
