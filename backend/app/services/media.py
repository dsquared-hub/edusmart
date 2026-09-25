"""Файлы рукописных работ: проверка типа по содержимому, предобработка и хранение.

Предобработка фото (шаг 1 конвейера Модуля 5.1): поворот по EXIF, обрезка пустых
полей, автоконтраст, ограничение размера; HEIC (iPhone) → JPEG. Выравнивание
перспективы не делаем: Vision-модель устойчива к наклону, а для точной геометрии
нужен OpenCV — отдельный шаг, если понадобится.
"""
from __future__ import annotations

import io
import secrets
from pathlib import Path

from app.core.config import get_settings

MAX_SIDE = 2400  # достаточно для почерка и формул, при этом ~0.5–1 МБ на фото


class MediaError(Exception):
    def __init__(self, code: str, status: int = 415):
        super().__init__(code)
        self.code = code
        self.status = status


def sniff_mime(data: bytes) -> str | None:
    """Тип по сигнатуре файла — заголовку Content-Type от клиента не доверяем."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"hevc", b"heim", b"heis", b"mif1", b"msf1"):
        return "image/heic"
    return None


def preprocess(data: bytes, mime: str) -> tuple[bytes, str]:
    """Фото → выровненный по EXIF, обрезанный и контрастный JPEG. PDF — как есть."""
    if mime == "application/pdf":
        return data, mime
    from PIL import Image, ImageChops, ImageOps

    if mime == "image/heic":
        import pillow_heif

        pillow_heif.register_heif_opener()
    try:
        image = Image.open(io.BytesIO(data))
        image = ImageOps.exif_transpose(image).convert("RGB")
    except Exception as exc:  # битый файл
        raise MediaError("bad_file", 415) from exc

    # Обрезка однотонных полей (стол, фон вокруг листа) по цвету угла
    background = Image.new("RGB", image.size, image.getpixel((0, 0)))
    diff = ImageChops.difference(image, background).convert("L").point(lambda v: 255 if v > 40 else 0)
    box = diff.getbbox()
    if box and (box[2] - box[0]) * (box[3] - box[1]) > 0.3 * image.width * image.height:
        pad = 12
        image = image.crop((max(0, box[0] - pad), max(0, box[1] - pad),
                            min(image.width, box[2] + pad), min(image.height, box[3] + pad)))

    image = ImageOps.autocontrast(image, cutoff=1)
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=88, optimize=True)
    return out.getvalue(), "image/jpeg"


def _root() -> Path:
    root = Path(get_settings().media_dir) / "checks"
    root.mkdir(parents=True, exist_ok=True)
    return root


def save(data: bytes, mime: str) -> str:
    """Сохраняет файл под случайным именем (не угадать, не совпадает с именем ученика)."""
    ext = ".pdf" if mime == "application/pdf" else ".jpg"
    key = secrets.token_hex(16) + ext
    (_root() / key).write_bytes(data)
    return key


def load(key: str) -> bytes:
    path = (_root() / key).resolve()
    if path.parent != _root().resolve():  # защита от ../ в ключе
        raise MediaError("not_found", 404)
    return path.read_bytes()


def delete(key: str) -> None:
    try:
        (_root() / key).unlink(missing_ok=True)
    except OSError:
        pass
