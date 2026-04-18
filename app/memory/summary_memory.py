"""SummaryMemoryService — 长历史压缩摘要记忆。

三层记忆架构：
  Layer 1: 摘要层 (Summary) — 早期历史经 LLM 压缩为摘要
  Layer 2: 近期窗口 (Recent Window) — 最近 N 条原始消息（不被压缩）
  Layer 3: Redis 热缓存 (Hot Cache) — 当前会话的最近消息（由 HistoryLoader 管理）

触发条件：当 PostgreSQL 中的历史消息数量超过 summary_threshold 时，
自动将早期历史压缩为摘要，保留最近 N 条原始消息。

摘要存储：PostgreSQL sessions 表的 metadata JSON 字段中。
  - metadata.summary: 摘要文本
  - metadata.summary_up_to: 摘要覆盖的最后消息 ID
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.factories import LLMProviderFactory
from app.schemas.provider import LLMMessage

logger = get_logger("app.memory.summary")


_SUMMARY_SYSTEM_PROMPT = """\
请将以下对话历史压缩为一段简洁的摘要。要求：
1. 保留关键信息、决策、结论和重要上下文
2. 省略寒暄、重复内容和无意义的对话
3. 使用第三人称描述
4. 摘要长度控制在 {max_length} 字以内
5. 使用中文

对话历史：
{history}
"""


@dataclass(slots=True)
class MemoryLayers:
    """三层记忆结果。"""

    summary: str | None  # Layer 1: 摘要
    recent_messages: list[LLMMessage]  # Layer 2: 近期窗口
    total_original_count: int  # 原始消息总数
    summary_covers: int  # 摘要覆盖的消息数量


class SummaryMemoryService:
    """摘要记忆服务。

    工作流程：
    1. check_and_compress() — 检查是否需要压缩，需要则调用 LLM 生成摘要
    2. load_memory() — 加载三层记忆（摘要 + 近期消息）
    3. _generate_summary() — 调用 LLM 压缩历史
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.summary_threshold = settings.memory.summary_threshold
        self.summary_keep_recent = settings.memory.summary_keep_recent
        self.summary_max_length = settings.memory.summary_max_length

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    async def check_and_compress(
        self,
        messages: list[dict],
        *,
        session_id: str,
        existing_summary: str | None = None,
        summary_up_to: int | None = None,
    ) -> str | None:
        """检查是否需要压缩历史，需要则生成新摘要。

        Args:
            messages: 全量历史消息列表 [{"role": ..., "content": ..., "id": ...}]
            session_id: 会话 ID
            existing_summary: 已有摘要（增量更新时拼接）
            summary_up_to: 已有摘要覆盖到第几条消息

        Returns:
            新摘要文本（如果生成），或 None（不需要压缩）
        """
        if len(messages) <= self.summary_threshold:
            return None

        # 需要压缩的消息：排除最近的 keep_recent 条
        messages_to_summarize = messages[: -self.summary_keep_recent]
        if not messages_to_summarize:
            return None

        logger.info(
            "summary.compress_needed",
            extra={
                "session_id": session_id,
                "total_messages": len(messages),
                "to_summarize": len(messages_to_summarize),
                "existing_summary": bool(existing_summary),
            },
        )

        # 生成摘要
        summary = await self._generate_summary(messages_to_summarize)

        # 如果有已有摘要，拼接
        if existing_summary:
            summary = f"{existing_summary}\n\n{summary}"

        logger.info(
            "summary.generated",
            extra={
                "session_id": session_id,
                "summary_length": len(summary),
                "covers_up_to": len(messages) - self.summary_keep_recent,
            },
        )
        return summary

    async def load_memory(
        self,
        messages: list[dict],
        *,
        summary: str | None = None,
    ) -> MemoryLayers:
        """加载三层记忆。

        Args:
            messages: 全量历史消息
            summary: 已有摘要

        Returns:
            MemoryLayers 包含摘要和近期消息
        """
        total_count = len(messages)

        if total_count == 0:
            return MemoryLayers(
                summary=summary,
                recent_messages=[],
                total_original_count=0,
                summary_covers=0,
            )

        # 近期窗口：取最后 keep_recent 条
        recent_raw = messages[-self.summary_keep_recent:] if total_count > self.summary_keep_recent else messages
        recent_messages = [
            LLMMessage(role=m.get("role", "user"), content=m.get("content", ""))
            for m in recent_raw
        ]

        # 摘要覆盖的消息数
        summary_covers = max(0, total_count - len(recent_raw))

        return MemoryLayers(
            summary=summary,
            recent_messages=recent_messages,
            total_original_count=total_count,
            summary_covers=summary_covers,
        )

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    async def _generate_summary(self, messages: list[dict]) -> str:
        """调用 LLM 生成摘要。"""
        # 构建对话历史文本
        history_lines: list[str] = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            # 截断过长的单条消息
            if len(content) > 200:
                content = content[:200] + "..."
            history_lines.append(f"{role}: {content}")

        history_text = "\n".join(history_lines)

        # 调用 LLM
        prompt = _SUMMARY_SYSTEM_PROMPT.format(
            max_length=self.summary_max_length,
            history=history_text,
        )

        provider = LLMProviderFactory.create(model="mock-echo" if self.settings.app.env != "production" else None)
        result = await provider.chat(
            [
                {"role": "system", "content": "你是一个对话摘要助手，擅长提取关键信息并简洁表达。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=self.summary_max_length * 2,
        )

        return result.content.strip()


# ------------------------------------------------------------------
# 模块级单例
# ------------------------------------------------------------------

_service: SummaryMemoryService | None = None


def get_summary_memory_service() -> SummaryMemoryService:
    global _service
    if _service is None:
        _service = SummaryMemoryService()
    return _service
