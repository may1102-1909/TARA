"""Conditional routers for TARA StateGraph orchestration."""

from langgraph.graph import END
from app.graph.state import AgentState


def post_ceo_router(state: AgentState) -> str:
    """Routes execution after the human approval gate.
    
    - 'approve' -> Proceeds to planner_node for project architecture planning.
    - 'request_changes' -> Loops back to ceo_node with appended human feedback notes.
    - 'reject' / None -> Terminates workflow at END.
    """
    user_action = state.get("user_action")
    if user_action == "approve":
        return "planner_node"
    elif user_action == "request_changes":
        return "ceo_node"
    return END


def post_qa_router(state: AgentState) -> str:
    """Routes execution after QA verification and automated testing.
    
    - qa_passed is True -> Proceeds to security_node for hardening and release.
    - qa_passed is False and repair_count < 3 -> Loops back to developer_node for repair attempt.
    - qa_passed is False and repair_count >= 3 -> Proceeds to security_node with problems reported clearly.
    """
    qa_passed = state.get("qa_passed", False)
    repair_count = state.get("repair_count", 0)

    if qa_passed:
        return "security_node"

    if repair_count < 3:
        return "developer_node"

    return "security_node"


def post_qa_builder_router(state: AgentState) -> str:
    """Router for direct sequential builder graph."""
    qa_passed = state.get("qa_passed", False)
    repair_count = state.get("repair_count", 0)

    if qa_passed:
        return "security"

    if repair_count < 3:
        return "developer"

    return "security"
