"""Parsers — 文本、PDF、图片解析器。"""

from app.providers.base import BaseParser, ParseResult
from app.providers.parsers.image_parser import ImageParser
from app.providers.parsers.pdf_parser import PDFParser
from app.providers.parsers.text_parser import TextParser

# ─── Parser Registry ──────────────────────────────────────

_PARSERS: list[BaseParser] = [
    TextParser(),
    PDFParser(),
    ImageParser(),
]

_EXTENSION_MAP: dict[str, BaseParser] = {}
for _p in _PARSERS:
    for _ext in _p.supported_extensions:
        _EXTENSION_MAP[_ext.lower()] = _p


def get_parser(filename: str) -> BaseParser:
    """根据文件扩展名返回匹配的 Parser，未匹配则抛出 ValueError。"""
    import os

    ext = os.path.splitext(filename)[1].lower()
    parser = _EXTENSION_MAP.get(ext)
    if parser is None:
        supported = sorted(_EXTENSION_MAP.keys())
        raise ValueError(f"Unsupported file type '{ext}'. Supported: {supported}")
    return parser


__all__ = ["BaseParser", "ImageParser", "PDFParser", "ParseResult", "TextParser", "get_parser"]
