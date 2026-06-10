FROM python:3.12-slim

WORKDIR /app

# Node.js required for Phoenix MCP runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Pre-install Phoenix MCP — avoids npx @latest version-mismatch at runtime
RUN mkdir -p /opt/phoenix-mcp \
    && cd /opt/phoenix-mcp \
    && npm init -y \
    && npm install @arizeai/phoenix-mcp --legacy-peer-deps \
    && npm install @modelcontextprotocol/sdk --legacy-peer-deps

RUN pip install uv

COPY pyproject.toml README.md ./
RUN uv pip install --system --no-cache-dir ".[dev]" 2>/dev/null || uv pip install --system --no-cache-dir .

COPY agent/ ./agent/
COPY api/ ./api/
COPY cli/ ./cli/

ENV PYTHONPATH=/app
ENV PORT=8080

EXPOSE 8080

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
