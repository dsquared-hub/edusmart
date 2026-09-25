"""RAG по учебнику (Модуль 5.2): PDF → страницы → фрагменты → эмбеддинги → поиск.

Генерация уроков опирается на текст учебника, а не на общие знания модели:
в промпт идут только найденные фрагменты с номерами страниц.

Эмбеддинги: Gemini (gemini-embedding-001) или локальный хэш-эмбеддинг без сети —
он ищет по совпадению слов и годится для демо, тестов и работы без ключа.
Поиск — косинусная близость в Python: учебник на 200 страниц это ~600 фрагментов,
~50 мс. Следующий шаг для PostgreSQL — pgvector + HNSW (меняется только retrieve()).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import re
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import Textbook, TextbookChunk
from app.db.session import SessionLocal

log = logging.getLogger(__name__)

CHUNK_CHARS = 900
CHUNK_OVERLAP = 150
MIN_TEXT_CHARS = 200  # меньше — PDF без текстового слоя (скан): нужен OCR
MIN_SCORE = 0.1  # косинусная близость фрагмента к теме, ниже — «не по теме»


class RagError(Exception):
    def __init__(self, code: str, status: int = 409):
        super().__init__(code)
        self.code = code
        self.status = status


class Embedder(Protocol):
    name: str

    async def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]: ...


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm, 6) for v in vec]


_WORD = re.compile(r"\w+", re.UNICODE)


class HashEmbedder:
    """Эмбеддинг без сети: слова и пары слов, хэшированные в 512 измерений со знаком."""

    name = "hash-512"
    dims = 512

    async def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dims
        words = [w for w in _WORD.findall(text.lower()) if len(w) > 1]
        # Грубый «стемминг»: первые 6 букв — «трапеции» и «трапецию» совпадут
        stems = [w[:6] for w in words]
        for token in stems + [f"{a} {b}" for a, b in zip(stems, stems[1:])]:
            h = int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest(), "big")
            vec[h % self.dims] += 1.0 if (h >> 32) & 1 else -1.0
        return _normalize(vec)


class GeminiEmbedder:
    def __init__(self, settings: Settings):
        from google import genai
        from google.genai import types

        self._types = types
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = settings.embed_model
        self.dims = settings.embed_dims
        self.name = f"{self.model}:{self.dims}"

    async def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 64):  # пачками: меньше запросов, быстрее индексация
            response = await self.client.aio.models.embed_content(
                model=self.model,
                contents=texts[i : i + 64],
                config=self._types.EmbedContentConfig(
                    task_type="RETRIEVAL_QUERY" if query else "RETRIEVAL_DOCUMENT",
                    output_dimensionality=self.dims,
                ),
            )
            out.extend(_normalize(list(e.values)) for e in response.embeddings)
        return out


def make_embedder(settings: Settings | None = None) -> Embedder:
    settings = settings or get_settings()
    if settings.gemini_fake or not settings.gemini_api_key:
        return HashEmbedder()
    return GeminiEmbedder(settings)


# ---------- Разбор PDF ----------

def extract_pages(pdf: bytes) -> list[str]:
    """Текст каждой страницы (нумерация страниц — с 1, как в учебнике)."""
    import pymupdf

    try:
        with pymupdf.open(stream=pdf, filetype="pdf") as doc:
            return [page.get_text("text") for page in doc]
    except Exception as exc:
        raise RagError("bad_pdf", 415) from exc


def chunk_pages(pages: list[str]) -> list[tuple[int, str]]:
    """(страница, фрагмент). Фрагмент не пересекает границу страницы — ссылка на
    страницу всегда точная; соседние фрагменты перекрываются, чтобы мысль не рвалась."""
    chunks: list[tuple[int, str]] = []
    for number, raw in enumerate(pages, start=1):
        text = re.sub(r"[ \t]+", " ", raw).strip()
        text = re.sub(r"\n{2,}", "\n", text)
        start = 0
        while start < len(text):
            end = min(len(text), start + CHUNK_CHARS)
            if end < len(text):  # режем по пробелу, не посреди слова
                space = text.rfind(" ", start + CHUNK_CHARS // 2, end)
                end = space if space > 0 else end
            piece = text[start:end].strip()
            if len(piece) >= 40:
                chunks.append((number, piece))
            if end >= len(text):
                break
            start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


async def ingest(textbook_id: int, pdf: bytes, embedder: Embedder | None = None) -> None:
    """Индексация учебника (в фоне после загрузки). Ошибка — статус failed с кодом."""
    embedder = embedder or make_embedder()
    async with SessionLocal() as session:
        book = await session.get(Textbook, textbook_id)
        if book is None:
            return
        try:
            pages = await asyncio.to_thread(extract_pages, pdf)
            if sum(len(p.strip()) for p in pages) < MIN_TEXT_CHARS:
                raise RagError("no_text_layer", 422)
            chunks = chunk_pages(pages)
            vectors = await embedder.embed([text for _, text in chunks])
            await session.execute(delete(TextbookChunk).where(TextbookChunk.textbook_id == book.id))
            for i, ((page, text), vec) in enumerate(zip(chunks, vectors, strict=True)):
                session.add(TextbookChunk(textbook_id=book.id, page=page, ordinal=i, text=text[:4000], embedding=vec))
            book.pages = len(pages)
            book.embed_model = embedder.name
            book.status = "ready"
            book.error = None
        except RagError as exc:
            book.status, book.error = "failed", exc.code
        except Exception as exc:
            log.exception("Индексация учебника %s", textbook_id)
            book.status, book.error = "failed", str(exc)[:255]
        await session.commit()


# ---------- Поиск ----------

@dataclass
class Fragment:
    page: int
    text: str
    score: float


async def retrieve(
    session: AsyncSession, book: Textbook, query: str, embedder: Embedder, k: int = 8
) -> list[Fragment]:
    if book.status != "ready":
        raise RagError("textbook_not_ready")
    if book.embed_model != embedder.name:
        raise RagError("reindex_required")  # индекс построен другой моделью эмбеддингов
    [q] = await embedder.embed([query], query=True)
    rows = await session.execute(
        select(TextbookChunk.page, TextbookChunk.text, TextbookChunk.embedding).where(TextbookChunk.textbook_id == book.id)
    )
    scored = [Fragment(page, text, sum(a * b for a, b in zip(q, emb))) for page, text, emb in rows.all()]
    scored.sort(key=lambda f: f.score, reverse=True)
    # Порог отсекает случайные совпадения: нет ничего по теме — не выдумываем урок
    return [f for f in scored[:k] if f.score > MIN_SCORE]
