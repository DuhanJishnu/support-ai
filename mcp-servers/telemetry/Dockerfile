FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml ./

# Install dependencies
RUN uv sync --no-install-project

# Copy application code
COPY . .

RUN uv sync

EXPOSE 8001

# Run using SSE transport in Docker environment
ENV MCP_TRANSPORT=sse
ENV PORT=8001

CMD ["uv", "run", "python", "server.py"]
