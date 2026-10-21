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
"""Help-desk tickets."""

from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..api_client import AteraClient
from ._common import READ_ONLY, WRITES, ClientFactory, ItemsInPage, Page, enum_value, list_result, page_params, run_tool

TicketId = Annotated[int, Field(description="Ticket id (from atera_tickets_list).")]
PriorityValue = Literal["Low", "Medium", "High", "Critical"]
ImpactValue = Literal["NoImpact", "Minor", "Major", "Site Down", "Crisis"]
StatusValue = Literal["Open", "Pending", "Resolved", "Closed"]
Priority = Annotated[PriorityValue | str | None, Field(description="Priority.")]
Impact = Annotated[ImpactValue | str | None, Field(description="Business impact.")]
Status = Annotated[StatusValue | str | None, Field(description="Ticket status.")]
TicketType = Annotated[str | None, Field(description="Ticket type, e.g. Problem, Request, Incident, Change.")]
Technician = Annotated[int | None, Field(description="Technician contact id to assign.")]

# Fields kept in the list view; atera_tickets_get returns the full record.
SUMMARY_FIELDS = (
    "TicketID",
    "TicketNumber",
    "TicketTitle",
    "TicketStatus",
    "TicketPriority",
    "TicketImpact",
    "TicketType",
    "CustomerID",
    "CustomerName",
    "ContactFullName",
    "TechnicianFullName",
    "SLAStatus",
    "DueDate",
    "CreatedDate",
    "LastUpdatedDate",
)


def _compact(values: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in values.items() if v is not None}


def register(mcp: FastMCP, client_factory: ClientFactory) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def atera_tickets_list(
        page: Page = None,
        itemsInPage: ItemsInPage = None,
        ticketStatus: Status = None,
        customerId: Annotated[int | None, Field(description="Only this customer's tickets.")] = None,
        technicianId: Annotated[int | None, Field(description="Only tickets assigned to this technician.")] = None,
        dateFrom: Annotated[str | None, Field(description="Created on or after, YYYY-MM-DD.")] = None,
        dateTo: Annotated[str | None, Field(description="Created on or before, YYYY-MM-DD.")] = None,
    ) -> str:
        """List tickets: number, title, status, priority, customer, contact, technician, SLA, dates."""

        async def action(client: AteraClient) -> dict:
            params = page_params(page, itemsInPage) | _compact(
                {
                    "TicketStatus": enum_value(ticketStatus, StatusValue),
                    "CustomerID": customerId,
                    "TechnicianID": technicianId,
                    "DateFrom": dateFrom,
                    "DateTo": dateTo,
                }
            )
            return list_result(await client.get("/tickets", params), SUMMARY_FIELDS)

        return await run_tool("atera_tickets_list", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def atera_tickets_get(ticketId: TicketId) -> str:
        """Get one ticket's full record, including first and last end-user comment and SLA dates."""

        async def action(client: AteraClient) -> Any:
            return await client.get(f"/tickets/{int(ticketId)}")

        return await run_tool("atera_tickets_get", client_factory, action)

    @mcp.tool(annotations=WRITES)
    async def atera_tickets_create(
        TicketTitle: Annotated[str, Field(description="Short summary of the issue.")],
        CustomerID: Annotated[int | None, Field(description="Customer the ticket is for.")] = None,
        CustomerEmail: Annotated[str | None, Field(description="End-user e-mail (alternative to ContactID).")] = None,
        ContactID: Annotated[int | None, Field(description="End-user contact id.")] = None,
        TicketPriority: Priority = None,
        TicketImpact: Impact = None,
        TicketStatus: Status = None,
        TicketType: TicketType = None,
        TechnicianContactID: Technician = None,
        Description: Annotated[str | None, Field(description="Full description of the issue.")] = None,
    ) -> str:
        """Create a ticket. Changes data: only when the user explicitly asks."""

        async def action(client: AteraClient) -> Any:
            body = _compact(
                {
                    "TicketTitle": TicketTitle,
                    "CustomerID": CustomerID,
                    "CustomerEmail": CustomerEmail,
                    "ContactID": ContactID,
                    "TicketPriority": enum_value(TicketPriority, PriorityValue),
                    "TicketImpact": enum_value(TicketImpact, ImpactValue),
                    "TicketStatus": enum_value(TicketStatus, StatusValue),
                    "TicketType": TicketType,
                    "TechnicianContactID": TechnicianContactID,
                    "Description": Description,
                }
            )
            return await client.post("/tickets", body=body)

        return await run_tool("atera_tickets_create", client_factory, action)

    @mcp.tool(annotations=WRITES)
    async def atera_tickets_update(
        ticketId: TicketId,
        TicketTitle: Annotated[str | None, Field(description="New title.")] = None,
        TicketPriority: Priority = None,
        TicketImpact: Impact = None,
        TicketStatus: Status = None,
        TicketType: TicketType = None,
        TechnicianContactID: Technician = None,
    ) -> str:
        """Update a ticket's title, priority, impact, status, type or technician; omitted fields stay.

        Changes data: only when the user explicitly asks.
        """

        async def action(client: AteraClient) -> Any:
            body = _compact(
                {
                    "TicketTitle": TicketTitle,
                    "TicketPriority": enum_value(TicketPriority, PriorityValue),
                    "TicketImpact": enum_value(TicketImpact, ImpactValue),
                    "TicketStatus": enum_value(TicketStatus, StatusValue),
                    "TicketType": TicketType,
                    "TechnicianContactID": TechnicianContactID,
                }
            )
            if not body:
                raise ValueError("Give at least one field to change")
            result = await client.post(f"/tickets/{int(ticketId)}", body=body)
            return result if result is not None else {"updated": True, "ticketId": ticketId, **body}

        return await run_tool("atera_tickets_update", client_factory, action)

    @mcp.tool(annotations=WRITES)
    async def atera_tickets_add_comment(
        ticketId: TicketId,
        comment: Annotated[str, Field(description="Comment text.")],
        isInternal: Annotated[
            bool | None, Field(description="Internal note (default true). false makes it visible to the end user.")
        ] = None,
    ) -> str:
        """Add a comment to a ticket; internal by default. Only when the user explicitly asks."""

        async def action(client: AteraClient) -> Any:
            if not comment.strip():
                raise ValueError("comment must not be empty")
            body = {"Comment": comment, "IsInternal": True if isInternal is None else bool(isInternal)}
            result = await client.post(f"/tickets/{int(ticketId)}/comments", body=body)
            return result if result is not None else {"added": True, "ticketId": ticketId}

        return await run_tool("atera_tickets_add_comment", client_factory, action)
