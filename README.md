# AssistFlow - Multi-Agent Customer Support Platform

AssistFlow is a production-oriented support automation platform for a ride-hailing
business. It combines **FastAPI**, **Next.js**, **LangGraph**, PostgreSQL, and the
**Model Context Protocol (MCP)** so specialized agents can route tickets and fetch
external operational data before proposing a resolution.

## Current Status

Implemented through **Day 13** of the project roadmap.

- Monorepo setup with Docker Compose for frontend, backend, PostgreSQL, and MCP servers.
- Backend quality foundation with Ruff, Pytest, structured logging, correlation IDs,
  and standard JSON error responses.
- Async SQLAlchemy models and Alembic migration for users, rides, transactions, and
  support tickets.
- Mock data seeding script for local ride-hailing support scenarios.
- Standalone MCP services:
  - Telemetry: `get_ride_route_deviation`
  - Billing: `verify_transaction_status`
- FastAPI MCP client manager for tool discovery and invocation.
- LangGraph support workflow with:
  - Router node for structured intent classification.
  - Billing node that invokes transaction verification through MCP.
  - Telemetry node that invokes route deviation lookup through MCP.
  - Generic support node for non-specialized requests.
  - Guardrail node that validates deterministic resolution decisions.
- Next.js support console with a split chat workspace and live context/tool-call
  panel.
- Server-Sent Events endpoint for agent tokens, node status changes, tool
  invocations, and final graph state.
- `useAgentStream` React hook that posts support messages and parses streaming
  events for the dashboard.
- Agent activity indicators for thinking, MCP/database lookup, and policy
  validation states.
- Structured tool evidence panels for transaction checks and ride telemetry
  output in the support chat.

## Architecture

```text
support-ai/
├── backend/              FastAPI API, LangGraph agents, MCP client, DB models
├── frontend/             Next.js App Router UI with TypeScript and Tailwind
├── mcp-servers/
│   ├── billing/          MCP tool: verify_transaction_status
│   └── telemetry/        MCP tool: get_ride_route_deviation
├── docker-compose.yml    Local orchestration for all services
└── README.md
```

```text
Customer message
    |
    v
FastAPI /api/agents/chat
    |
    v
LangGraph router
    |
    |-- BILLING --> BillingAgent --> Billing MCP tool ----|
    |-- SAFETY  --> TelemetryAgent --> Telemetry MCP tool -|--> GuardrailNode
    `-- GENERAL --> GenericLLM ---------------------------|
                                                           |
                                                           v
                                                  Resolution decision
```

## Services

| Service | URL | Purpose |
| --- | --- | --- |
| Frontend | http://localhost:3000 | Next.js support console |
| Backend | http://localhost:8000 | FastAPI API and agent graph |
| API Docs | http://localhost:8000/docs | OpenAPI documentation |
| Postgres | localhost:5432 | Local application database |
| Telemetry MCP | http://localhost:8001/sse | Ride route deviation tool |
| Billing MCP | http://localhost:8002/sse | Transaction verification tool |

## Quick Start

### Prerequisites

- Docker and Docker Compose
- uv for local backend development
- Node.js 20+ for local frontend development
- Google API key for live router classification

### Run With Docker

```bash
cd support-ai
docker-compose up --build
```

### Local Backend

```bash
cd support-ai/backend
uv sync
uv run uvicorn app.main:app --reload
```

### Local Frontend

```bash
cd support-ai/frontend
npm install
npm run dev
```

## API Examples

Run the agent graph:

```bash
curl -X POST http://localhost:8000/api/agents/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"I was charged twice for transaction_id txn_123\"}"
```

Stream the agent graph:

```bash
curl -N -X POST http://localhost:8000/api/agents/chat/stream ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"My driver took a strange route for ride_id ride_456\"}"
```

List discovered MCP tools:

```bash
curl http://localhost:8000/api/mcp/tools
```

Invoke a tool directly:

```bash
curl -X POST http://localhost:8000/api/mcp/invoke ^
  -H "Content-Type: application/json" ^
  -d "{\"tool_name\":\"verify_transaction_status\",\"input\":{\"transaction_id\":\"txn_123\"}}"
```

## Environment

The backend reads settings from environment variables or `backend/.env`.

| Variable | Default | Description |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://support_ai:support_ai@localhost:5432/support_ai` | Async SQLAlchemy database URL |
| `GOOGLE_API_KEY` | empty | Required for live Gemini router classification |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Router model |
| `MCP_TELEMETRY_SERVER_URL` | `http://telemetry:8001/sse` | Telemetry MCP endpoint |
| `MCP_BILLING_SERVER_URL` | `http://billing:8002/sse` | Billing MCP endpoint |
| `MCP_REQUEST_TIMEOUT` | `30.0` | MCP request timeout in seconds |

## Testing

Backend tests use mocks for LLM and MCP interactions, so they can run without a live
Google API key or running MCP containers.

```bash
cd support-ai/backend
uv run pytest
uv run ruff check .
```

Frontend checks:

```bash
cd support-ai/frontend
npm run lint
npm run test:run
```

## License

MIT
