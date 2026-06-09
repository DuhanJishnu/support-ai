# Support AI — Multi-Agent Customer Support Platform

A production-grade, multi-agent customer support platform built with **FastAPI**, **Next.js**, **LangGraph**, and the **Model Context Protocol (MCP)**.

## Architecture

```
support-ai/
├── backend/       → FastAPI + LangGraph + MCP Clients (Python 3.12)
├── frontend/      → Next.js 16 + TypeScript + Tailwind v4
├── mcp-servers/   → Independent MCP services (coming soon)
└── docker-compose.yml
```

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & Docker Compose
- [uv](https://docs.astral.sh/uv/) (for local backend development)
- [Node.js 20+](https://nodejs.org/) (for local frontend development)

### Run with Docker

```bash
docker-compose up --build
```

| Service  | URL                     |
|----------|-------------------------|
| Backend  | http://localhost:8000   |
| Frontend | http://localhost:3000   |

### Local Development (without Docker)

**Backend:**
```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Tech Stack

- **Backend:** FastAPI, Pydantic v2, uvicorn, uv
- **Frontend:** Next.js 16 (App Router), TypeScript, Tailwind CSS v4
- **AI/Agents:** LangGraph, LangChain, MCP SDK (coming soon)
- **Infrastructure:** Docker, Docker Compose, GitHub Actions

## License

MIT
