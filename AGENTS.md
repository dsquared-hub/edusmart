# Инструкция для ИИ-помощников (Claude, Codex, Copilot и др.)

EduSmart — образовательная платформа для школьников: ИИ (Gemini) объясняет тему по
шагам с мини-проверками, родители и учителя видят результаты. Подробное описание
возможностей и API — в `README.md`, ответ на ТЗ — в `docs/`.

## Состав

| Папка | Что это |
| --- | --- |
| `backend/` | FastAPI + общее ядро (пакет `app`): модели SQLAlchemy, сервисы, ИИ, миграции Alembic |
| `bot/` | Telegram-бот на aiogram 3, использует ядро из `backend/app` |
| `web/` | Сайт на Next.js 14 (App Router, TypeScript, Tailwind), PWA |
| `prototype/` | Ранний дизайн-прототип на Vite, в продукте не используется |
| `deploy/` | Продакшен: Caddy, docker-compose, бэкапы |

## Запуск

Все настройки — в одном `.env` в корне (образец — `.env.example`). Без ключа Gemini
поставь `GEMINI_FAKE=1`: объяснения будут демонстрационными.

```bash
docker compose up -d --build          # сайт :3000, API :8000/docs
```

Без Docker (Python 3.11+, Node 20+):

```bash
pip install -e "./backend[dev]" -r bot/requirements.txt
cd backend && alembic upgrade head && uvicorn app.main:app --port 8000
cd web && npm ci && npm run dev
```

## Проверки перед коммитом

Те же, что в `.github/workflows/ci.yml`:

```bash
cd backend && pytest -q
cd bot && pytest -q
cd web && npm run typecheck && npm run build
cd backend && alembic check           # модели совпадают с миграциями
```

## Правила

- Схема БД меняется только новой миграцией в `backend/alembic/versions/`.
- Тексты сайта — в `web/messages/{ru,uz,en}.json`, бота — в
  `backend/app/locales/{ru,uz,en}.json`. Новый ключ добавляется во все три языка.
- Вызовы ИИ идут только через `backend/app/services/gemini.py`. Ответ модели всегда
  проверяется: арифметика — кодом в `services/checks.py`, остальное — вторым запросом.
- В запросы к ИИ не передаются имена и идентификаторы детей.
- Доступ к данным ребёнка проверяется в API и покрыт тестами безопасности. Новый
  эндпоинт с данными ученика требует такого же теста.
- Не коммитить `.env`, файлы баз `*.db*` и `backend/media/` (фото работ учеников).
