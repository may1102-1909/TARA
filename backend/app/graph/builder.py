import sys
from pathlib import Path

# Ensure backend root is on sys.path for direct script execution
_backend_dir = str(Path(__file__).resolve().parent.parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from langgraph.graph import StateGraph, END
from app.graph.state import AgentState
from app.agents.ceo import ceo_node
from app.agents.developer import developer_node
from app.agents.qa import qa_node
from app.agents.security import security_node

# Create graph
builder = StateGraph(AgentState)

# Add agent nodes
builder.add_node("ceo", ceo_node)
builder.add_node("developer", developer_node)
builder.add_node("qa", qa_node)
builder.add_node("security", security_node)

# Set execution flow: CEO -> Developer -> QA -> Security
builder.set_entry_point("ceo")
builder.add_edge("ceo", "developer")
builder.add_edge("developer", "qa")
builder.add_edge("qa", "security")
builder.add_edge("security", END)

graph = builder.compile()
