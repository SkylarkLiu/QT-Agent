"""Chunker — 将解析后的文本段落切分为固定大小的 chunk，附带重叠。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings
from app.providers.base import ParsedSection


@dataclass(slots=True)
class Chunk:
    """一个文本 chunk，附带完整的 metadata。"""

    content: str
    chunk_index: int
    metadata: dict[str, Any] = field(default_factory=dict)


class Chunker:
    """文本分块器。

    策略：
    - 对每个 ParsedSection 的 content，按 ``chunk_size`` 字符切分
    - 相邻 chunk 之间保留 ``chunk_overlap`` 字符的重叠
    - 每个 Chunk 自动继承 section 的 metadata（page, section_title 等）
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.chunk_size = settings.ingestion.chunk_size
        self.chunk_overlap = settings.ingestion.chunk_overlap

    def chunk_sections(
        self,
        sections: list[ParsedSection],
        *,
        doc_id: str = "",
        kb_id: str = "",
        owner_user_id: str = "",
        source_type: str = "unknown",
    ) -> list[Chunk]:
        """将解析段落列表切分为 chunk 列表。"""
        chunks: list[Chunk] = []
        global_index = 0

        for section in sections:
            text = section.content.strip()
            if not text:
                continue

            section_chunks = self._split_text(text)
            for i, chunk_text in enumerate(section_chunks):
                chunk_metadata: dict[str, Any] = {
                    "doc_id": doc_id,
                    "kb_id": kb_id,
                    "owner_user_id": owner_user_id,
                    "source_type": source_type,
                }
                # 继承 section 级别的 metadata
                if section.page is not None:
                    chunk_metadata["page"] = section.page
                if section.section_title:
                    chunk_metadata["section_title"] = section.section_title
                chunk_metadata.update(section.metadata)

                chunks.append(Chunk(
                    content=chunk_text.strip(),
                    chunk_index=global_index,
                    metadata=chunk_metadata,
                ))
                global_index += 1

        return chunks

    def _split_text(self, text: str) -> list[str]:
        """按字符数切分文本，保留 overlap。"""
        if len(text) <= self.chunk_size:
            return [text]

        result: list[str] = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            # 尝试在句号/换行处断句
            if end < len(text):
                # 寻找最后一个句号、感叹号、问号或换行
                break_point = text.rfind("\n", start, end)
                if break_point <= start:
                    break_point = text.rfind("。", start, end)
                if break_point <= start:
                    break_point = text.rfind(".", start, end)
                if break_point <= start:
                    break_point = end
                end = break_point + 1  # 包含分隔符

            result.append(text[start:end].strip())
            start = end - self.chunk_overlap
            # 避免死循环
            if start >= len(text):
                break

        return [c for c in result if c]
