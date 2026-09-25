FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir .

COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/scripts ./scripts

EXPOSE 8000
# Миграции при каждом старте — идемпотентно.
# --forwarded-allow-ips="*": API доступен только из сети compose (снаружи — через
# Caddy), поэтому доверяем X-Forwarded-For — лимит запросов видит настоящий IP.
RUN useradd --create-home app \
    && mkdir -p /app/media && chown app /app/media
# Фото рукописных работ (Academic Copilot) — в томе media, не в образе
ENV MEDIA_DIR=/app/media
USER app
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
