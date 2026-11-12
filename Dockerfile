FROM node:20-alpine AS web-build

WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 appuser

COPY api.py ./
COPY story/ ./story/
COPY evals/ ./evals/
COPY --from=web-build /web/out/ ./web/out/

USER appuser
CMD ["sh", "-c", "exec uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
