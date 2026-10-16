# Atera MCP Server

An [MCP](https://modelcontextprotocol.io) server for the [Atera](https://www.atera.com) RMM and
PSA API (v3). It lets an AI agent read an MSP's Atera data (customers, monitored agents,
alerts, tickets and contacts) and, on explicit request, create customers and tickets, update
tickets and add ticket comments.

- Transport: MCP Streamable HTTP at `POST /mcp`, health probe at `GET /health`
- Stateless and multi-tenant: the API key arrives on every request as an HTTP header and is
  never stored; every tool is listed from the first `tools/list`
- Python 3.12, [uv](https://docs.astral.sh/uv/), FastMCP, httpx
- License: Apache-2.0, Copyright 2026 MSPbots.ai

## Authentication headers

| Header | Required | Type | Default | Allowed values | Description | Example |
|---|---|---|---|---|---|---|
| `X-Atera-Api-Key` | Yes | string | none | - | Atera API token (a leading `Bearer ` is accepted and ignored) | `your-atera-api-key` |

Where to get it:

- In Atera open **Admin -> Data management -> API -> New token**. A token has an expiration
  date (at most one year), an optional IP allowlist, and either full access or per-domain
  Read / Write / Delete permissions.
- Grant **Read** on Customers, Agents, Tickets, Alerts and Contacts for the read tools; add
  **Write** on Customers and Tickets only if the agent should create or update them.
- If the token restricts IP addresses, allow the public egress IP of the environment that runs
  this server.

How the key is sent to Atera: JWT-format tokens (the current token format) are sent as
`Authorization: Bearer <token>`; older static keys are sent as `X-API-KEY: <key>`. Only one of
the two headers is ever sent.

A request to `/mcp` without the header gets HTTP 401 listing the required header.

## Tools

All tools return a JSON string. List tools take `page` (from 1) and `itemsInPage` (default and
maximum 50) and return `{items, count, page, total_pages, total_items, has_more}`.

| Tool | Purpose | Parameters (required in **bold**) |
|---|---|---|
| `atera_navigate` | Show the tools of one area | **domain** (`customers`, `agents`, `tickets`, `alerts`, `contacts`) |
| `atera_back` | List all areas and their tools | - |
| `atera_customers_list` | List customers | page, itemsInPage |
| `atera_customers_get` | One customer | **customerId** |
| `atera_customers_create` | Create a customer (**write**) | **CustomerName**, BusinessNumber, Domain, Address, City, State, Country, ZipCode, Phone, Fax, Notes, Website |
| `atera_agents_list` | List monitored machines (summary) | page, itemsInPage, customerId |
| `atera_agents_get` | One agent's full record | **agentId** |
| `atera_agents_get_by_machine` | Agent(s) by computer name | **machineName** |
| `atera_tickets_list` | List tickets (summary) | page, itemsInPage, ticketStatus (`Open`, `Pending`, `Resolved`, `Closed`), customerId, technicianId, dateFrom, dateTo |
| `atera_tickets_get` | One ticket's full record | **ticketId** |
| `atera_tickets_create` | Create a ticket (**write**) | **TicketTitle**, CustomerID, CustomerEmail, ContactID, TicketPriority, TicketImpact, TicketStatus, TicketType, TechnicianContactID, Description |
| `atera_tickets_update` | Change ticket fields (**write**) | **ticketId**, TicketTitle, TicketPriority, TicketImpact, TicketStatus, TicketType, TechnicianContactID |
| `atera_tickets_add_comment` | Add a comment, internal by default (**write**) | **ticketId**, **comment**, isInternal |
| `atera_alerts_list` | List alerts | page, itemsInPage, alertSeverity (`Information`, `Warning`, `Critical`), customerId, archived |
| `atera_alerts_get` | One alert | **alertId** |
| `atera_alerts_by_agent` | Alerts of one agent | **agentId**, page, itemsInPage |
| `atera_alerts_by_device` | Alerts of one monitored device | **deviceId**, page, itemsInPage |
| `atera_contacts_list` | List contacts | page, itemsInPage |
| `atera_contacts_get` | One contact | **contactId** |
| `atera_contacts_by_customer` | Contacts of one customer | **customerId**, page, itemsInPage |

Errors come back as a JSON envelope instead of an exception:

```json
{"error": {"code": "unauthorized", "message": "Atera returned HTTP 401: ...", "retryable": false}}
```

`code` is one of `not_configured`, `unauthorized`, `not_found`, `invalid_argument`,
`rate_limited`, `upstream_error`. Atera allows about 700 requests per minute per account; 429
responses are retried with backoff.

## Run locally

```bash
uv sync
uv run python -m atera_mcp          # listens on 0.0.0.0:8080
```

or with Docker:

```bash
docker build --platform linux/amd64 -t atera-mcp:dev .
docker run --rm -p 8080:8080 atera-mcp:dev
```

Configuration (environment variables, all optional): `MCP_HTTP_HOST` (default `0.0.0.0`),
`MCP_HTTP_PORT` (default `8080`), `LOG_LEVEL` (default `INFO`). The key is never read from the
environment.

## Testing example

```bash
# list tools
curl -s http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-Atera-Api-Key: your-atera-api-key" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# open tickets
curl -s http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-Atera-Api-Key: your-atera-api-key" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"atera_tickets_list","arguments":{"ticketStatus":"Open","itemsInPage":10}}}'
```

Unit tests (no network access needed):

```bash
uv run pytest
```

## Delivery notes

- **All tools always listed.** Older versions only listed a navigation tool until one was
  called. Behind a stateless gateway that hid every other tool, so this version lists all 20
  tools up front. `atera_navigate` and `atera_back` remain for compatibility and only describe
  the tools.
- **Tool count (20).** Kept as is because the tool names are an existing contract.
- **Write tools.** `atera_customers_create`, `atera_tickets_create`, `atera_tickets_update` and
  `atera_tickets_add_comment` change data; descriptions tell the agent to use them only on
  explicit request, and ticket comments default to internal. There are no delete tools.
- **List trimming.** `atera_agents_list` and `atera_tickets_list` return summary fields; use the
  matching `_get` tool for the full record.

## License

Apache License 2.0 - see [LICENSE](LICENSE) and [NOTICE](NOTICE).
