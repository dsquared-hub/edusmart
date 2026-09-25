FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

# Общее ядро из /backend — тот же код, что у API
COPY backend/pyproject.toml ./backend/
COPY backend/app ./backend/app
RUN pip install --no-cache-dir ./backend

COPY bot/requirements.txt ./bot/
RUN pip install --no-cache-dir -r bot/requirements.txt

COPY bot ./bot
RUN useradd --create-home app
USER app
WORKDIR /srv/bot
CMD ["python", "main.py"]
