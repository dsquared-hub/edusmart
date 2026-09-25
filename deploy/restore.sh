#!/bin/sh
# Восстановление базы из резервной копии.
#   cd deploy
#   sh restore.sh backups/edu-20260925-030000.dump
# ВНИМАНИЕ: текущие данные в базе будут заменены данными из копии.
set -eu

DUMP="${1:?Укажи файл: sh restore.sh backups/edu-....dump}"
[ -f "$DUMP" ] || { echo "Файл не найден: $DUMP" >&2; exit 1; }

COMPOSE="docker compose -f docker-compose.prod.yml --env-file ../.env"

echo "Останавливаю бота и API, чтобы никто не писал в базу…"
$COMPOSE stop bot backend

echo "Восстанавливаю из $DUMP…"
$COMPOSE exec -T postgres sh -c 'pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$DUMP"

echo "Запускаю обратно…"
$COMPOSE start backend bot
echo "Готово."
