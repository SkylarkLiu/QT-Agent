"""RAG 子图：将 RAG 节点编译为 LangGraph 子图，供主图接入。"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.graph.rag_nodes import (
    answer_by_rag,
    evaluate_relevance,
    fallback_to_websearch,
    rag_prepare,
    recall_documents,
    reform_query,
    rerank_documents,
    route_after_evaluate,
    route_after_reform,
)
from app.graph.state import GraphState


def build_rag_subgraph() -> StateGraph:
    """构建 RAG 子图。

    流程:
      START → rag_prepare → recall_documents → rerank_documents → evaluate_relevance
                                                                          ├─ answer_by_rag → END
                                                                          ├─ reform_query → recall_documents (循环)
                                                                          └─ fallback_to_websearch → END
    """
    builder = StateGraph(GraphState)

    # 添加节点
    builder.add_node("rag_prepare", rag_prepare)
    builder.add_node("recall_documents", recall_documents)
    builder.add_node("rerank_documents", rerank_documents)
    builder.add_node("evaluate_relevance", evaluate_relevance)
    builder.add_node("reform_query", reform_query)
    builder.add_node("answer_by_rag", answer_by_rag)
    builder.add_node("fallback_to_websearch", fallback_to_websearch)

    # 添加边
    builder.add_edge(START, "rag_prepare")
    builder.add_edge("rag_prepare", "recall_documents")
    builder.add_edge("recall_documents", "rerank_documents")
    builder.add_edge("rerank_documents", "evaluate_relevance")

    # 条件路由：evaluate 后决定走向
    builder.add_conditional_edges(
        "evaluate_relevance",
        route_after_evaluate,
        {
            "answer_by_rag": "answer_by_rag",
            "reform_query": "reform_query",
            "fallback_to_websearch": "fallback_to_websearch",
        },
    )

    # reform 后回到 recall（循环）
    builder.add_conditional_edges(
        "reform_query",
        route_after_reform,
        {"recall_documents": "recall_documents"},
    )

    # 终止边
    builder.add_edge("answer_by_rag", END)
    builder.add_edge("fallback_to_websearch", END)

    return builder
