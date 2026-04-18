from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.graph.skill_nodes import build_skill_executor, resolve_skill, route_after_resolve_skill, skill_unavailable
from app.graph.state import GraphState
from app.skills.registry import register_default_skills


def build_skill_router_subgraph() -> StateGraph:
    register_default_skills()

    builder = StateGraph(GraphState)
    builder.add_node("resolve_skill", resolve_skill)
    builder.add_node("knowledge_qa", build_skill_executor("knowledge_qa"))
    builder.add_node("mcp_tool", build_skill_executor("mcp_tool"))
    builder.add_node("web_search", build_skill_executor("web_search"))
    builder.add_node("report_analysis", build_skill_executor("report_analysis"))
    builder.add_node("policy_compare", build_skill_executor("policy_compare"))
    builder.add_node("skill_unavailable", skill_unavailable)

    builder.add_edge(START, "resolve_skill")
    builder.add_conditional_edges(
        "resolve_skill",
        route_after_resolve_skill,
        {
            "knowledge_qa": "knowledge_qa",
            "mcp_tool": "mcp_tool",
            "web_search": "web_search",
            "report_analysis": "report_analysis",
            "policy_compare": "policy_compare",
            "skill_unavailable": "skill_unavailable",
        },
    )
    builder.add_edge("knowledge_qa", END)
    builder.add_edge("mcp_tool", END)
    builder.add_edge("web_search", END)
    builder.add_edge("report_analysis", END)
    builder.add_edge("policy_compare", END)
    builder.add_edge("skill_unavailable", END)
    return builder
