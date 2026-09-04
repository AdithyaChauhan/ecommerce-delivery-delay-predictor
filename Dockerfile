FROM node:24.20.0-bookworm-slim AS frontend-build

WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13.15-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DELIVERY_DELAY_MODEL_PATH=/app/models/delay_model_v2_pipeline.joblib \
    DELIVERY_DELAY_METRICS_PATH=/app/models/delay_model_v2_metrics.json \
    DELIVERY_DELAY_STATIC_DIR=/app/frontend-dist

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY delivery_delay ./delivery_delay
COPY models/delay_model_v2_pipeline.joblib models/delay_model_v2_metrics.json ./models/
COPY --from=frontend-build /src/frontend/dist ./frontend-dist

RUN addgroup --system --gid 10001 appgroup \
    && adduser --system --uid 10001 --gid 10001 appuser \
    && chown -R appuser:appgroup /app

USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).read()"

CMD ["uvicorn", "delivery_delay.api:app", "--host", "0.0.0.0", "--port", "8000"]
