"""ImageParser — 支持 .png / .jpg / .jpeg / .gif / .webp 图片 OCR 提取文字。"""

from __future__ import annotations

import asyncio
import io
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.base import BaseParser, ParsedSection, ParseResult

logger = get_logger("app.providers.parsers.image")


class ImageParser(BaseParser):
    supported_extensions = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"]

    async def _parse_impl(self, source: bytes, *, metadata: dict[str, Any] | None = None) -> ParseResult:
        settings = get_settings()

        if not settings.ingestion.ocr_enabled:
            return ParseResult(
                sections=[],
                total_pages=1,
                source_type="image",
                metadata=metadata or {},
                error="OCR is disabled in configuration",
            )

        text = await self._ocr_image(source)

        sections: list[ParsedSection] = []
        if text.strip():
            sections.append(ParsedSection(
                content=text.strip(),
                page=1,
                metadata={"source": "ocr"},
            ))

        return ParseResult(
            sections=sections,
            total_pages=1,
            source_type="image",
            metadata=metadata or {},
        )

    @staticmethod
    async def _ocr_image(image_bytes: bytes) -> str:
        """使用 Tesseract OCR 提取图片中的文字。"""
        settings = get_settings()
        lang = settings.ingestion.ocr_lang

        def _run_ocr() -> str:
            try:
                from PIL import Image  # type: ignore[import-untyped]
                import pytesseract  # type: ignore[import-untyped]

                img = Image.open(io.BytesIO(image_bytes))
                return str(pytesseract.image_to_string(img, lang=lang))
            except ImportError:
                logger.warning("ocr.dependency_missing", extra={"hint": "Install pytesseract + Pillow"})
                return ""

        return await asyncio.to_thread(_run_ocr)
