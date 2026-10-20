"""Direct sequential multi-agent graph builder."""

import sys
from pathlib import Path

# Ensure backend root is on sys.path for direct script execution
_backend_dir = str(Path(__file__).resolve().parent.parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from langgraph.graph import StateGraph, END
from app.graph.state import AgentState
from app.graph.router import post_qa_builder_router
from app.agents.ceo import ceo_node
from app.agents.planner import planner_node
from app.agents.developer import developer_node
from app.agents.qa import qa_node
from app.agents.security import security_node

# Create graph
builder = StateGraph(AgentState)

# Add agent nodes
builder.add_node("ceo", ceo_node)
builder.add_node("planner", planner_node)
builder.add_node("developer", developer_node)
builder.add_node("qa", qa_node)
builder.add_node("security", security_node)

# Set execution flow: CEO -> Planner -> Developer -> QA (with repair loop) -> Security -> END
builder.set_entry_point("ceo")
builder.add_edge("ceo", "planner")
builder.add_edge("planner", "developer")
builder.add_edge("developer", "qa")
builder.add_conditional_edges(
    "qa",
    post_qa_builder_router,
    {
        "developer": "developer",
        "security": "security",
    }
)
builder.add_edge("security", END)

graph = builder.compile()
