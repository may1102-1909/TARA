"""Conditional routers for TARA StateGraph orchestration."""

from langgraph.graph import END
from app.graph.state import AgentState


def post_ceo_router(state: AgentState) -> str:
    """Routes execution after the human approval gate.
    
    - 'approve' -> Proceeds to dev_qa_node for code generation and refactoring.
    - 'request_changes' -> Loops back to ceo_node with appended human feedback notes.
    - 'reject' / None -> Terminates workflow at END.
    """
    user_action = state.get("user_action")
    if user_action == "approve":
        return "dev_qa_node"
    elif user_action == "request_changes":
        return "ceo_node"
    return END
