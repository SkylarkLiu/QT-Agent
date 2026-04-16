"""WebSearch 子图节点：联网搜索 + 结果清洗 + LLM 总结（含降级提示）。

节点流程：
  web_prepare -> web_search -> result_clean -> answer_by_web
                                                  ↓
                                                END (回主图)
"""

from __future__ import annotations

import re
import time
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.factories import LLMProviderFactory, SearchProviderFactory
from app.schemas.provider import LLMMessage

logger = get_logger("app.graph.web")


# ---------------------------------------------------------------------------
# P7-T3: 降级提示 Prompt
# ---------------------------------------------------------------------------

_WEB_FALLBACK_NOTICE = "⚠️ 当前知识库中未找到与您问题高度相关的内容，以下回答基于网络搜索结果整理，请注意甄别信息准确性。"

_WEB_SYSTEM_PROMPT = """\
你是一个专业的信息检索助手。请根据以下网络搜索结果回答用户的问题。

回答要求：
1. 基于搜索结果进行总结，确保信息准确
2. 标注信息来源链接，便于用户进一步核实
3. 如果搜索结果之间有矛盾，请指出来
4. 回答应条理清晰、简洁专业
"""

_WEB_SYSTEM_PROMPT_WITH_FALLBACK = f"""\
{_WEB_FALLBACK_NOTICE}

你是一个专业的信息检索助手。请根据以下网络搜索结果回答用户的问题。

回答要求：
1. 基于搜索结果进行总结，确保信息准确
2. 标注信息来源链接，便于用户进一步核实
3. 如果搜索结果之间有矛盾，请指出来
4. 回答应条理清晰、简洁专业
"""

_WEB_CONTEXT_TEMPLATE = """\
搜索关键词：{query}

搜索结果：
{results}
"""


# ---------------------------------------------------------------------------
# P7-T2: WebSearch 子图节点
# ---------------------------------------------------------------------------


async def web_prepare(state: dict) -> dict:
    """WebSearch 子图入口：准备搜索参数。"""
    settings = get_settings()
    query = state.get("normalized_query", state.get("user_message", ""))
    return {
        "web_search_query": query,
        "web_search_results": [],
        "top_k": min(state.get("top_k", 5), settings.web_search.max_results),
    }


async def web_search_execute(state: dict) -> dict:
    """执行联网搜索：调用 SearchProvider 获取结果。"""
    start = time.perf_counter()
    query = state.get("web_search_query", state.get("normalized_query", ""))
    top_k = state.get("top_k", 5)

    provider = SearchProviderFactory.create()
    results = await provider.search(query, top_k=top_k)

    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        "web.search_execute",
        extra={
            "provider": provider.provider_name,
            "query": query[:50],
            "result_count": len(results),
            "latency_ms": elapsed_ms,
        },
    )

    return {"web_search_results": results}


async def result_clean(state: dict) -> dict:
    """清洗搜索结果：去重、截断、过滤无效内容。"""
    raw_results = state.get("web_search_results", [])

    cleaned: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for item in raw_results:
        url = item.get("url", "").strip()
        title = item.get("title", "").strip()
        content = item.get("content", "").strip()

        # 过滤空内容
        if not title and not content:
            continue

        # URL 去重
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)

        # 内容截断（保留前 500 字符）
        if len(content) > 500:
            content = content[:500] + "..."

        # 清洗 HTML 标签
        content = re.sub(r"<[^>]+>", "", content)

        cleaned.append({
            "title": title,
            "url": url,
            "content": content,
            "score": item.get("score", 0.0),
        })

    logger.info(
        "web.result_clean",
        extra={
            "input_count": len(raw_results),
            "output_count": len(cleaned),
            "deduplicated_urls": len(seen_urls),
        },
    )

    return {"web_search_results": cleaned}


async def answer_by_web(state: dict) -> dict:
    """基于搜索结果生成回答：将搜索结果喂给 LLM 总结。

    当 need_web_fallback=True 时，使用带降级提示的系统 prompt。
    """
    start = time.perf_counter()
    settings = get_settings()

    results = state.get("web_search_results", [])
    query = state.get("web_search_query", state.get("normalized_query", ""))
    is_fallback = state.get("need_web_fallback", False)

    # 构建搜索结果上下文
    result_blocks: list[str] = []
    for idx, item in enumerate(results, start=1):
        source = item.get("title", "未知来源")
        url = item.get("url", "")
        content = item.get("content", "")
        location = f" ({url})" if url else ""
        result_blocks.append(f"[{idx}] {source}{location}\n{content}")

    if not result_blocks:
        web_context = "（搜索未返回有效结果）"
    else:
        web_context = "\n\n".join(result_blocks)

    context_text = _WEB_CONTEXT_TEMPLATE.format(query=query, results=web_context)

    # 根据是否降级选择不同的系统 prompt
    system_prompt = _WEB_SYSTEM_PROMPT_WITH_FALLBACK if is_fallback else _WEB_SYSTEM_PROMPT

    # 构建历史消息
    history: list[dict[str, str]] = []
    for msg in state.get("history_messages", []):
        history.append({"role": msg.role, "content": msg.content})

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": context_text + f"\n\n用户问题：{query}"})

    provider = LLMProviderFactory.create()

    if state.get("stream"):
        aggregated = ""
        stream_chunks: list[dict] = []
        finish_reason: str | None = None

        # 如果是降级场景，前缀添加降级提示
        if is_fallback:
            aggregated = _WEB_FALLBACK_NOTICE + "\n\n"

        llm_messages = [LLMMessage(**m) for m in messages]
        async for chunk in provider.stream_chat(llm_messages, model=state.get("model")):
            if chunk.delta:
                aggregated += chunk.delta
                stream_chunks.append(chunk.model_dump())
            finish_reason = chunk.finish_reason or finish_reason

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "web.answer_by_web",
            extra={
                "mode": "stream",
                "is_fallback": is_fallback,
                "result_count": len(results),
                "latency_ms": elapsed_ms,
                "chunk_count": len(stream_chunks),
            },
        )
        return {
            "response_text": aggregated,
            "provider_name": provider.provider_name,
            "finish_reason": finish_reason,
            "stream_chunks": stream_chunks,
            "route_type": "web_search",
        }

    llm_messages = [LLMMessage(**m) for m in messages]
    result = await provider.chat(llm_messages, model=state.get("model"))
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

    # 降级场景前缀
    final_text = result.content
    if is_fallback:
        final_text = _WEB_FALLBACK_NOTICE + "\n\n" + final_text

    logger.info(
        "web.answer_by_web",
        extra={
            "mode": "non-stream",
            "is_fallback": is_fallback,
            "result_count": len(results),
            "latency_ms": elapsed_ms,
            "model": result.model,
        },
    )
    return {
        "response_text": final_text,
        "provider_name": result.provider,
        "model": result.model,
        "finish_reason": result.finish_reason,
        "usage": result.usage,
        "route_type": "web_search",
    }
