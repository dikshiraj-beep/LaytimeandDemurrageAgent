"""LangGraph wiring: nodes, the three self-correction loops and the human-approval checkpoint."""
from __future__ import annotations

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from .. import config
from . import nodes as N
from .state import AgentState


def build_graph(checkpointer=None):
    g = StateGraph(AgentState)
    g.add_node("plan", N.plan)
    g.add_node("extract", N.extract)
    g.add_node("retrieve", N.retrieve)
    g.add_node("grade", N.grade)
    g.add_node("validate", N.validate)
    g.add_node("calculate", N.calculate)
    g.add_node("verify", N.verify)
    g.add_node("approval", N.approval)
    g.add_node("draft", N.draft)

    g.add_edge(START, "plan")
    g.add_edge("plan", "extract")
    # after the first extraction we go to retrieval; after a loop-B re-read we go back to validation
    g.add_conditional_edges("extract", lambda s: "validate" if s.get("reread_done") else "retrieve",
                            {"validate": "validate", "retrieve": "retrieve"})
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges("grade", N.route_after_grade, {"retrieve": "retrieve", "validate": "validate"})   # loop A
    g.add_conditional_edges("validate", N.route_after_validate,
                            {"extract": "extract", "calculate": "calculate", "approval": "approval"})      # loop B
    g.add_edge("calculate", "verify")
    g.add_conditional_edges("verify", N.route_after_verify, {"validate": "validate", "approval": "approval"})  # loop C
    g.add_conditional_edges("approval", N.route_after_approval, {"draft": "draft", "end": END})
    g.add_edge("draft", END)
    return g.compile(checkpointer=checkpointer)


_GRAPH = None
_CHECKPOINTER_CONN = None


def get_graph():
    """Compile with PostgreSQL checkpoints when configured, otherwise use local SQLite."""
    global _GRAPH, _CHECKPOINTER_CONN
    if _GRAPH is None:
        config.ensure_dirs()
        if config.DATABASE_URL:
            import psycopg
            from langgraph.checkpoint.postgres import PostgresSaver

            _CHECKPOINTER_CONN = psycopg.connect(config.DATABASE_URL, autocommit=True)
            checkpointer = PostgresSaver(_CHECKPOINTER_CONN)
            checkpointer.setup()
        else:
            conn = sqlite3.connect(config.CHECKPOINT_DB, check_same_thread=False)
            checkpointer = SqliteSaver(conn)
        _GRAPH = build_graph(checkpointer)
    return _GRAPH


def mermaid() -> str:
    return build_graph().get_graph().draw_mermaid()
