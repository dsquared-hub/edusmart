#!/bin/sh
# Резервная копия PostgreSQL и фото работ раз в BACKUP_INTERVAL_SECONDS (по умолчанию сутки).
# Хранятся BACKUP_KEEP_DAYS дней (по умолчанию 14) в deploy/backups/.
# Восстановление — deploy/restore.sh.
set -eu

KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
INTERVAL="${BACKUP_INTERVAL_SECONDS:-86400}"
mkdir -p /backups

while true; do
  STAMP="$(date +%Y%m%d-%H%M%S)"
  FILE="/backups/edu-${STAMP}.dump"
  if pg_dump --format=custom --no-owner --file="${FILE}.tmp"; then
    mv "${FILE}.tmp" "${FILE}"
    echo "[backup] ${FILE} ($(du -h "${FILE}" | cut -f1))"
  else
    rm -f "${FILE}.tmp"
    echo "[backup] ОШИБКА резервного копирования" >&2
  fi
  # Фото рукописных работ (Academic Copilot) — архивом рядом с дампом БД
  if [ -d /media/checks ]; then
    if tar -czf "/backups/media-${STAMP}.tar.gz.tmp" -C /media checks; then
      mv "/backups/media-${STAMP}.tar.gz.tmp" "/backups/media-${STAMP}.tar.gz"
      echo "[backup] media-${STAMP}.tar.gz"
    else
      rm -f "/backups/media-${STAMP}.tar.gz.tmp"
      echo "[backup] ОШИБКА архивации фото работ" >&2
    fi
  fi
  find /backups \( -name 'edu-*.dump' -o -name 'media-*.tar.gz' \) -mtime +"${KEEP_DAYS}" -delete
  sleep "${INTERVAL}"
done
