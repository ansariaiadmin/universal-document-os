FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim AS runner
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system --gid 1001 appgroup \
    && adduser --system --uid 1001 --gid 1001 --home /app appuser \
    && mkdir -p /app/data/uploads /app/data/outputs /app/data/workrooms \
    && chown -R appuser:appgroup /app
COPY --from=builder /install /usr/local
COPY --chown=appuser:appgroup . .
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 CMD curl -f http://localhost:8000/api/health || exit 1
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
