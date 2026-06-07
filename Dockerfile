FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .
RUN uv pip install --system --no-cache-dir ".[dev]" 2>/dev/null || uv pip install --system --no-cache-dir .

COPY agent/ ./agent/
COPY api/ ./api/
COPY cli/ ./cli/

ENV PYTHONPATH=/app
ENV PORT=8080

EXPOSE 8080

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
