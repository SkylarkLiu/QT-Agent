"""WebSearch 子图：将 WebSearch 节点编译为 LangGraph 子图，供主图接入。

流程:
  START → web_prepare → web_search_execute → result_clean → answer_by_web → END
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.graph.state import GraphState
from app.graph.web_nodes import answer_by_web, result_clean, web_prepare, web_search_execute


def build_web_search_subgraph() -> StateGraph:
    """构建 WebSearch 子图。

    流程:
      START → web_prepare → web_search_execute → result_clean → answer_by_web → END
    """
    builder = StateGraph(GraphState)

    # 添加节点
    builder.add_node("web_prepare", web_prepare)
    builder.add_node("web_search_execute", web_search_execute)
    builder.add_node("result_clean", result_clean)
    builder.add_node("answer_by_web", answer_by_web)

    # 添加边
    builder.add_edge(START, "web_prepare")
    builder.add_edge("web_prepare", "web_search_execute")
    builder.add_edge("web_search_execute", "result_clean")
    builder.add_edge("result_clean", "answer_by_web")
    builder.add_edge("answer_by_web", END)

    return builder
