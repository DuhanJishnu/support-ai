FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first for Docker layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies (without installing the project itself)
RUN uv sync --frozen --no-install-project

# Copy application source code
COPY . .

# Sync again to install the project
RUN uv sync --frozen

EXPOSE 8000

# Run with hot-reload for development
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
