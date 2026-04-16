"""RAG 子图节点：实现知识库问答的完整检索增强生成链路。

节点流程：
  rag_prepare -> recall_documents -> rerank_documents -> evaluate_relevance
     ↓ (score 低)                      ↓ (score 高)
  reform_query -> recall_documents    answer_by_rag
     ↓ (达到 max_recall)              ↓
  fallback_to_websearch               END (回主图)
"""

from __future__ import annotations

import time
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.factories import EmbeddingProviderFactory, LLMProviderFactory
from app.retrieval.base import VectorDocument
from app.retrieval.retriever import get_retriever

logger = get_logger("app.graph.rag")


# ---------------------------------------------------------------------------
# P5-T4: RAG Answer Prompt
# ---------------------------------------------------------------------------

_RAG_SYSTEM_PROMPT = """\
你是一个专业的知识库问答助手。请根据以下检索到的参考资料回答用户的问题。

回答要求：
1. 仅基于提供的参考资料进行回答，不要编造信息
2. 如果参考资料不足以完整回答问题，请明确说明缺失的部分
3. 引用来源时，使用 [来源X] 的格式标注
4. 回答应条理清晰、专业准确
"""

_CITATION_TEMPLATE = """\
参考资料：
{citations}

---
请基于以上参考资料回答用户问题。
"""


def _build_citation_context(docs: list[VectorDocument]) -> str:
    """将检索到的文档片段组装为 citation context。"""
    if not docs:
        return "（未检索到相关参考资料）"
    blocks: list[str] = []
    for idx, doc in enumerate(docs, start=1):
        source = doc.metadata.get("source", doc.metadata.get("filename", "未知来源"))
        page = doc.metadata.get("page", "")
        location = f"，第{page}页" if page else ""
        blocks.append(f"[来源{idx}] {source}{location}\n{doc.content}")
    return "\n\n".join(blocks)


def _build_rag_messages(
    query: str,
    docs: list[VectorDocument],
    history: list[dict[str, str]],
) -> list[dict[str, str]]:
    """构建 RAG 问答的完整 messages 列表。"""
    citation_context = _build_citation_context(docs)
    rag_user_content = _CITATION_TEMPLATE.format(citations=citation_context) + f"\n\n用户问题：{query}"

    messages: list[dict[str, str]] = [{"role": "system", "content": _RAG_SYSTEM_PROMPT}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": rag_user_content})
    return messages


# ---------------------------------------------------------------------------
# P5-T2: RAG 子图节点
# ---------------------------------------------------------------------------


async def rag_prepare(state: dict) -> dict:
    """RAG 子图入口：准备检索参数。"""
    settings = get_settings()
    return {
        "recall_count": 0,
        "max_recall_count": settings.rag.max_recall_count,
        "top_k": state.get("top_k", 5),
        "retrieved_docs": [],
        "relevance_score": 0.0,
        "need_web_fallback": False,
    }


async def recall_documents(state: dict) -> dict:
    """向量召回：对 query 做 embedding 后检索 Milvus。"""
    settings = get_settings()
    start = time.perf_counter()

    query = state["normalized_query"] if state.get("recall_count", 0) == 0 else state.get("rewritten_query", state["normalized_query"])
    retriever = get_retriever()

    docs = await retriever.retrieve(
        query,
        top_k=state.get("top_k", 5),
        user_id=state.get("user_id"),
    )

    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    top_score = docs[0].score if docs else 0.0
    logger.info(
        "rag.recall_documents",
        extra={
            "recall_count": state.get("recall_count", 0),
            "query_length": len(query),
            "returned_docs": len(docs),
            "top_score": top_score,
            "latency_ms": elapsed_ms,
        },
    )

    # 将 VectorDocument 转为可序列化的 dict
    doc_dicts = [
        {
            "id": d.id,
            "content": d.content,
            "metadata": d.metadata,
            "score": d.score,
        }
        for d in docs
    ]

    return {
        "retrieved_docs": doc_dicts,
        "relevance_score": top_score,
    }


async def rerank_documents(state: dict) -> dict:
    """重排序：基于 relevance score 过滤低分文档，保留 top-k。

    当前实现使用向量相似度 score 作为排序依据（cosine similarity）。
    后续可替换为 cross-encoder reranker。
    """
    settings = get_settings()
    docs = state.get("retrieved_docs", [])
    rerank_top_k = settings.rag.rerank_top_k

    # 按 score 降序排列，过滤掉 score 过低的
    filtered = [d for d in docs if d.get("score", 0) > 0.1]
    reranked = sorted(filtered, key=lambda d: d.get("score", 0), reverse=True)[:rerank_top_k]

    logger.info(
        "rag.rerank_documents",
        extra={
            "input_count": len(docs),
            "output_count": len(reranked),
            "rerank_top_k": rerank_top_k,
        },
    )
    return {"retrieved_docs": reranked}


async def evaluate_relevance(state: dict) -> dict:
    """评估检索结果的相关性。

    判断逻辑：
    - 如果最高分 >= relevance_threshold → 相关，进入 answer_by_rag
    - 如果 recall_count < max_recall_count → 尝试改写 query 重新检索
    - 否则 → 降级到 web search
    """
    settings = get_settings()
    score = state.get("relevance_score", 0.0)
    threshold = settings.rag.relevance_threshold
    recall_count = state.get("recall_count", 0)
    max_recall = state.get("max_recall_count", settings.rag.max_recall_count)

    logger.info(
        "rag.evaluate_relevance",
        extra={
            "score": score,
            "threshold": threshold,
            "recall_count": recall_count,
            "max_recall_count": max_recall,
        },
    )

    if score >= threshold:
        return {
            "relevance_score": score,
            "need_web_fallback": False,
            "should_reform_query": False,
            "should_answer_rag": True,
        }

    if recall_count < max_recall:
        return {
            "should_reform_query": True,
            "should_answer_rag": False,
            "need_web_fallback": False,
        }

    # 达到最大 recall 次数仍未达标，降级
    return {
        "need_web_fallback": True,
        "should_reform_query": False,
        "should_answer_rag": False,
    }


async def reform_query(state: dict) -> dict:
    """改写 query：让 LLM 优化用户问题以提高检索命中率。"""
    settings = get_settings()
    if not settings.rag.query_rewrite_enabled:
        return {"recall_count": state.get("recall_count", 0) + 1}

    original_query = state["normalized_query"]
    docs_summary = ""
    if state.get("retrieved_docs"):
        top_content = state["retrieved_docs"][0].get("content", "")[:200] if state["retrieved_docs"] else ""
        docs_summary = f"\n已有检索结果摘要（相关度偏低）：{top_content}"

    rewrite_prompt = f"""\
请帮我改写以下查询，使其更适合在知识库中检索相关信息。
要求：保持原意，使用更精确的关键词，去除口语化表述。

原始查询：{original_query}{docs_summary}

请直接输出改写后的查询，不要输出其他内容。"""

    provider = LLMProviderFactory.create()
    result = await provider.chat(
        [
            {"role": "system", "content": "你是一个查询优化助手，只输出改写后的查询文本。"},
            {"role": "user", "content": rewrite_prompt},
        ],
        temperature=0.0,
        max_tokens=128,
    )

    rewritten = result.content.strip().strip('"').strip("'")
    logger.info(
        "rag.reform_query",
        extra={
            "original": original_query[:50],
            "rewritten": rewritten[:50],
            "recall_count": state.get("recall_count", 0),
        },
    )

    return {
        "rewritten_query": rewritten,
        "recall_count": state.get("recall_count", 0) + 1,
    }


async def answer_by_rag(state: dict) -> dict:
    """基于检索结果生成回答：将 citation context 喂给 LLM。"""
    settings = get_settings()
    start = time.perf_counter()

    doc_dicts = state.get("retrieved_docs", [])
    docs = [VectorDocument(id=d["id"], content=d["content"], metadata=d.get("metadata", {}), score=d.get("score")) for d in doc_dicts]

    # 构建历史消息
    history = []
    for msg in state.get("history_messages", []):
        history.append({"role": msg.role, "content": msg.content})

    messages = _build_rag_messages(state["user_message"], docs, history)
    provider = LLMProviderFactory.create()

    if state.get("stream"):
        aggregated = ""
        stream_chunks: list[dict] = []
        finish_reason: str | None = None
        async for chunk in provider.stream_chat(
            [__import__("app.schemas.provider", fromlist=["LLMMessage"]).LLMMessage(**m) for m in messages],
            model=state.get("model"),
        ):
            if chunk.delta:
                aggregated += chunk.delta
                stream_chunks.append(chunk.model_dump())
            finish_reason = chunk.finish_reason or finish_reason

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "rag.answer_by_rag",
            extra={
                "mode": "stream",
                "doc_count": len(docs),
                "latency_ms": elapsed_ms,
                "chunk_count": len(stream_chunks),
            },
        )
        return {
            "response_text": aggregated,
            "provider_name": provider.provider_name,
            "finish_reason": finish_reason,
            "stream_chunks": stream_chunks,
        }

    from app.schemas.provider import LLMMessage

    llm_messages = [LLMMessage(**m) for m in messages]
    result = await provider.chat(llm_messages, model=state.get("model"))
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

    logger.info(
        "rag.answer_by_rag",
        extra={
            "mode": "non-stream",
            "doc_count": len(docs),
            "latency_ms": elapsed_ms,
            "model": result.model,
        },
    )
    return {
        "response_text": result.content,
        "provider_name": result.provider,
        "model": result.model,
        "finish_reason": result.finish_reason,
        "usage": result.usage,
    }


async def fallback_to_websearch(state: dict) -> dict:
    """RAG 降级标记：设置 need_web_fallback 标志，由主图路由到 web_search。"""
    logger.info(
        "rag.fallback_to_websearch",
        extra={
            "recall_count": state.get("recall_count", 0),
            "relevance_score": state.get("relevance_score", 0),
            "user_query": state.get("normalized_query", "")[:50],
        },
    )
    return {
        "need_web_fallback": True,
        "route_type": "web_search",
    }


# ---------------------------------------------------------------------------
# P5-T3: Recall 循环路由函数
# ---------------------------------------------------------------------------


def route_after_evaluate(state: dict) -> str:
    """evaluate_relevance 后的路由决策。

    - should_answer_rag=True → answer_by_rag
    - should_reform_query=True → reform_query
    - 都为 False（降级）→ fallback_to_websearch
    """
    if state.get("should_answer_rag"):
        return "answer_by_rag"
    if state.get("should_reform_query"):
        return "reform_query"
    return "fallback_to_websearch"


def route_after_reform(state: dict) -> str:
    """reform_query 后的路由：回到 recall_documents 重新检索。"""
    return "recall_documents"
