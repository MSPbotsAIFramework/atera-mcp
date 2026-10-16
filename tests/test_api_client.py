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
"""Auth header selection, paging and tool behaviour against a mocked Atera API."""

import json

import httpx
import pytest

from atera_mcp import api_client
from atera_mcp.api_client import AteraClient, AteraCredentials, is_jwt
from atera_mcp.server import _credentials_var, create_mcp_server

JWT_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJleGFtcGxlIn0.c2lnbmF0dXJl"

TICKET_PAGE = {
    "items": [
        {
            "TicketID": 101,
            "TicketNumber": "101",
            "TicketTitle": "Printer offline",
            "TicketStatus": "Open",
            "CustomerName": "Example Co",
            "FirstComment": "long text that the list view drops",
        }
    ],
    "totalItemCount": 120,
    "page": 1,
    "itemsInPage": 50,
    "totalPages": 3,
    "prevLink": None,
    "nextLink": "https://app.atera.com/api/v3/tickets?page=2&itemsInPage=50",
}


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def instant(_seconds):
        return None

    monkeypatch.setattr(api_client.asyncio, "sleep", instant)


class Recorder:
    def __init__(self, reply=None):
        self.requests: list[httpx.Request] = []
        self.reply = reply or (lambda r: httpx.Response(200, json={"items": [], "page": 1, "totalPages": 1}))

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.reply(request)


async def _call(monkeypatch, recorder: Recorder, tool: str, args: dict, key: str = "legacy-key"):
    http = httpx.AsyncClient(transport=httpx.MockTransport(recorder))
    monkeypatch.setattr(api_client, "_get_shared_http_client", lambda: http)
    mcp = create_mcp_server()
    ctx = _credentials_var.set(AteraCredentials(key))
    try:
        content, _ = await mcp.call_tool(tool, args)
    finally:
        _credentials_var.reset(ctx)
    return json.loads(content[0].text)


@pytest.mark.parametrize(
    "key,expected",
    [(JWT_KEY, True), ("legacy-static-key", False), ("a.b.c", False), ("eyJ.only-two", False)],
)
def test_jwt_detection(key, expected):
    assert is_jwt(key) is expected


async def test_legacy_key_goes_in_x_api_key(monkeypatch):
    rec = Recorder()
    await _call(monkeypatch, rec, "atera_customers_list", {"itemsInPage": 1}, key="legacy-key")
    req = rec.requests[0]
    assert req.headers["x-api-key"] == "legacy-key"
    assert "authorization" not in req.headers
    assert str(req.url) == "https://app.atera.com/api/v3/customers?Page=1&ItemsInPage=1"


async def test_jwt_key_goes_in_bearer_only(monkeypatch):
    rec = Recorder()
    await _call(monkeypatch, rec, "atera_customers_list", {}, key=JWT_KEY)
    req = rec.requests[0]
    assert req.headers["authorization"] == f"Bearer {JWT_KEY}"
    assert "x-api-key" not in req.headers


async def test_ticket_list_filters_paging_and_trim(monkeypatch):
    rec = Recorder(lambda r: httpx.Response(200, json=TICKET_PAGE))
    result = await _call(
        monkeypatch,
        rec,
        "atera_tickets_list",
        {"ticketStatus": "Open", "customerId": 7, "itemsInPage": 500, "dateFrom": "2026-01-01"},
    )
    params = rec.requests[0].url.params
    assert params["TicketStatus"] == "Open" and params["CustomerID"] == "7"
    assert params["ItemsInPage"] == "50" and params["DateFrom"] == "2026-01-01"
    assert result["has_more"] is True and result["total_items"] == 120 and result["total_pages"] == 3
    assert "FirstComment" not in result["items"][0]
    assert result["items"][0]["TicketTitle"] == "Printer offline"


async def test_agents_list_by_customer(monkeypatch):
    rec = Recorder()
    await _call(monkeypatch, rec, "atera_agents_list", {"customerId": 42})
    assert rec.requests[0].url.path == "/api/v3/agents"
    assert rec.requests[0].url.params["CustomerID"] == "42"


async def test_alerts_list_bool_and_severity(monkeypatch):
    rec = Recorder()
    await _call(monkeypatch, rec, "atera_alerts_list", {"alertSeverity": "Critical", "archived": False})
    params = rec.requests[0].url.params
    assert params["AlertSeverity"] == "Critical" and params["Archived"] == "false"


@pytest.mark.parametrize(
    "tool,args,method,path",
    [
        ("atera_customers_get", {"customerId": 5}, "GET", "/api/v3/customers/5"),
        ("atera_agents_get", {"agentId": 9}, "GET", "/api/v3/agents/9"),
        ("atera_agents_get_by_machine", {"machineName": "WS 001"}, "GET", "/api/v3/agents/machine/WS%20001"),
        ("atera_alerts_get", {"alertId": 3}, "GET", "/api/v3/alerts/3"),
        ("atera_alerts_by_agent", {"agentId": 9}, "GET", "/api/v3/alerts/agent/9"),
        ("atera_alerts_by_device", {"deviceId": 4}, "GET", "/api/v3/alerts/device/4"),
        ("atera_contacts_get", {"contactId": 8}, "GET", "/api/v3/contacts/8"),
        ("atera_contacts_by_customer", {"customerId": 5}, "GET", "/api/v3/contacts/customer/5"),
        ("atera_tickets_get", {"ticketId": 101}, "GET", "/api/v3/tickets/101"),
    ],
)
async def test_read_routing(monkeypatch, tool, args, method, path):
    rec = Recorder(lambda r: httpx.Response(200, json={}))
    await _call(monkeypatch, rec, tool, args)
    req = rec.requests[0]
    assert (req.method, req.url.raw_path.decode().split("?")[0]) == (method, path)


async def test_create_ticket_body(monkeypatch):
    rec = Recorder(lambda r: httpx.Response(200, json={"ActionID": 1, "ID": 555}))
    await _call(
        monkeypatch, rec, "atera_tickets_create",
        {"TicketTitle": "VPN down", "CustomerID": 7, "TicketPriority": "High", "Description": "Users cannot connect"},
    )
    req = rec.requests[0]
    assert (req.method, req.url.path) == ("POST", "/api/v3/tickets")
    assert json.loads(req.content) == {
        "TicketTitle": "VPN down", "CustomerID": 7, "TicketPriority": "High", "Description": "Users cannot connect"
    }


async def test_update_ticket_sends_only_given_fields(monkeypatch):
    rec = Recorder(lambda r: httpx.Response(200, content=b""))
    result = await _call(monkeypatch, rec, "atera_tickets_update", {"ticketId": 101, "TicketStatus": "Resolved"})
    req = rec.requests[0]
    assert (req.method, req.url.path) == ("POST", "/api/v3/tickets/101")
    assert json.loads(req.content) == {"TicketStatus": "Resolved"}
    assert result["updated"] is True


async def test_update_ticket_without_fields_is_rejected(monkeypatch):
    rec = Recorder()
    result = await _call(monkeypatch, rec, "atera_tickets_update", {"ticketId": 101})
    assert result["error"]["code"] == "invalid_argument"
    assert rec.requests == []


@pytest.mark.parametrize("given,expected", [({}, True), ({"isInternal": False}, False)])
async def test_comment_is_internal_by_default(monkeypatch, given, expected):
    rec = Recorder(lambda r: httpx.Response(200, json={"CommentID": 1}))
    await _call(monkeypatch, rec, "atera_tickets_add_comment", {"ticketId": 101, "comment": "Rebooted router"} | given)
    req = rec.requests[0]
    assert (req.method, req.url.path) == ("POST", "/api/v3/tickets/101/comments")
    assert json.loads(req.content) == {"Comment": "Rebooted router", "IsInternal": expected}


async def test_unauthorized_maps_to_envelope(monkeypatch):
    rec = Recorder(lambda r: httpx.Response(401, json={"Message": "Authorization has been denied for this request."}))
    result = await _call(monkeypatch, rec, "atera_customers_list", {}, key="secret-key")
    assert result["error"]["code"] == "unauthorized"
    assert "secret-key" not in json.dumps(result)


async def test_navigate_and_back_need_no_api_call(monkeypatch):
    rec = Recorder()
    nav = await _call(monkeypatch, rec, "atera_navigate", {"domain": "tickets"})
    back = await _call(monkeypatch, rec, "atera_back", {})
    assert "atera_tickets_update" in nav["tools"]
    assert "agents" in back["domains"]
    assert rec.requests == []


def test_client_never_sends_both_auth_headers():
    for key in (JWT_KEY, "legacy-key"):
        headers = AteraClient(AteraCredentials(key))._headers()
        assert ("Authorization" in headers) != ("X-API-KEY" in headers)
