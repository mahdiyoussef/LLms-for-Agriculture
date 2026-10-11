FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    API_REQUIRE_AUTH=true \
    RAG_PROVIDER=bedrock \
    AGENT_MEMORY_DB=/var/lib/agriculture-rag/agent-memory.sqlite3

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY eval ./eval
COPY documents ./documents
COPY .env.example .

RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
RUN mkdir -p /var/lib/agriculture-rag && chown -R appuser:appuser /var/lib/agriculture-rag
USER appuser

VOLUME ["/var/lib/agriculture-rag"]
EXPOSE 8000
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
