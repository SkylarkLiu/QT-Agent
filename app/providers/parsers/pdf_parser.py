"""PDFParser — 支持 .pdf 文件解析，扫描型 PDF 自动 OCR fallback。"""

from __future__ import annotations

import io
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.base import BaseParser, ParsedSection, ParseResult

logger = get_logger("app.providers.parsers.pdf")


class PDFParser(BaseParser):
    supported_extensions = [".pdf"]

    async def _parse_impl(self, source: bytes, *, metadata: dict[str, Any] | None = None) -> ParseResult:
        settings = get_settings()
        sections: list[ParsedSection] = []
        total_pages = 0

        try:
            import pymupdf  # type: ignore[import-untyped]

            doc = pymupdf.open(stream=source, filetype="pdf")
            total_pages = len(doc)

            for page_num in range(total_pages):
                page = doc[page_num]
                text = page.get_text().strip()

                if text:
                    # 文本型 PDF — 直接提取
                    sections.append(ParsedSection(
                        content=text,
                        page=page_num + 1,
                        metadata={"page_type": "text"},
                    ))
                elif settings.ingestion.ocr_enabled:
                    # 扫描型 PDF — OCR fallback
                    logger.info(
                        "pdf.ocr_fallback",
                        extra={"page": page_num + 1, "total_pages": total_pages},
                    )
                    pix = page.get_pixmap(dpi=300)
                    img_bytes = pix.tobytes("png")
                    ocr_text = await self._ocr_image(img_bytes)
                    if ocr_text.strip():
                        sections.append(ParsedSection(
                            content=ocr_text.strip(),
                            page=page_num + 1,
                            metadata={"page_type": "ocr"},
                        ))

            doc.close()

        except ImportError:
            logger.warning("pdf.pymupdf_missing", extra={"hint": "Install pymupdf: pip install pymupdf"})
            # 没有 pymupdf 时尝试纯 OCR 方案
            if settings.ingestion.ocr_enabled:
                ocr_text = await self._ocr_image(source)
                sections.append(ParsedSection(content=ocr_text.strip(), source_type="pdf_ocr"))
            else:
                return ParseResult(
                    sections=[],
                    total_pages=0,
                    source_type="pdf",
                    metadata=metadata or {},
                    error="pymupdf not installed and OCR disabled",
                )

        return ParseResult(
            sections=sections,
            total_pages=total_pages,
            source_type="pdf",
            metadata=metadata or {},
        )

    @staticmethod
    async def _ocr_image(image_bytes: bytes) -> str:
        """使用 Tesseract OCR 提取图片中的文字。"""
        import asyncio

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
