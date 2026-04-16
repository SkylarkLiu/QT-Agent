"""TextParser — 支持 .txt / .md 等纯文本文件。"""

from __future__ import annotations

from typing import Any

from app.providers.base import BaseParser, ParsedSection, ParseResult


class TextParser(BaseParser):
    supported_extensions = [".txt", ".md", ".csv", ".json", ".xml", ".html", ".log", ".yaml", ".yml"]

    async def _parse_impl(self, source: bytes, *, metadata: dict[str, Any] | None = None) -> ParseResult:
        try:
            text = source.decode("utf-8")
        except UnicodeDecodeError:
            # fallback: gbk / gb2312
            try:
                text = source.decode("gbk")
            except UnicodeDecodeError:
                text = source.decode("latin-1")

        lines = text.splitlines()
        sections: list[ParsedSection] = []

        # 按空行分段，每段作为一个 section
        current_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped:
                current_lines.append(line)
            else:
                if current_lines:
                    sections.append(ParsedSection(content="\n".join(current_lines)))
                    current_lines = []
        if current_lines:
            sections.append(ParsedSection(content="\n".join(current_lines)))

        # 如果没有段落，把全部文本作为一个 section
        if not sections and text.strip():
            sections.append(ParsedSection(content=text))

        return ParseResult(
            sections=sections,
            total_pages=1,
            source_type="text",
            metadata=metadata or {},
        )
