"""Workflow graph assembly for TARA multi-agent orchestration."""

import datetime
from typing import Any, Dict, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langgraph.checkpoint.memory import MemorySaver

from app.graph.state import AgentState
from app.graph.router import post_ceo_router
from app.agents.ceo import ceo_node
from app.agents.developer import developer_node
from app.agents.qa import qa_node
from app.agents.security import security_node


def human_approval_gate(state: AgentState) -> Dict[str, Any]:
    """Halts execution and awaits human sign-off via LangGraph interrupt."""
    critique = state.get("ceo_critique")
    revision_count = state.get("revision_count", 0)
    
    # Interrupt execution, yielding control and payload to caller/API
    human_response = interrupt({
        "stage": "approval_gate",
        "critique": critique,
        "revision_count": revision_count,
        "prompt": "CEO critique awaiting review. Required action: 'approve', 'request_changes', or 'reject'."
    })
    
    # Resume payload handling
    if isinstance(human_response, dict):
        action = human_response.get("action", "reject")
        notes = human_response.get("notes", "")
    else:
        action = str(human_response)
        notes = ""
        
    log_msg = f"Human decision received: {action.upper()}"
    if notes:
        log_msg += f" | Notes: {notes}"
        
    updates: Dict[str, Any] = {
        "user_action": action,
        "current_stage": f"approval_{action}",
        "logs": [{
            "agent": "Human-in-the-Loop",
            "stage": "approval_gate",
            "message": log_msg,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }]
    }
    if notes:
        updates["human_feedback_notes"] = [notes]
        
    return updates


def dev_qa_node(state: AgentState) -> Dict[str, Any]:
    """Runs Developer code generation followed by QA standard-library refactoring."""
    # 1. Developer generates initial scaffold
    dev_out = developer_node(state)
    
    # 2. QA refactors generated files
    merged_state: AgentState = {**state, **dev_out}  # type: ignore
    qa_out = qa_node(merged_state)
    
    combined_logs = dev_out.get("logs", []) + qa_out.get("logs", [])
    
    return {
        "dev_code_files": dev_out.get("dev_code_files", {}),
        "qa_refactored_files": qa_out.get("qa_refactored_files", {}),
        "qa_changelog": qa_out.get("qa_changelog", []),
        "current_stage": "dev_qa_completed",
        "logs": combined_logs,
    }


def create_tara_workflow(checkpointer=None):
    """Compiles the TARA StateGraph with checkpointing and HITL gate."""
    workflow = StateGraph(AgentState)
    
    # Register graph nodes
    workflow.add_node("ceo_node", ceo_node)
    workflow.add_node("human_approval_gate", human_approval_gate)
    workflow.add_node("dev_qa_node", dev_qa_node)
    workflow.add_node("security_node", security_node)
    
    # Flow edges
    workflow.add_edge(START, "ceo_node")
    workflow.add_edge("ceo_node", "human_approval_gate")
    
    # Conditional edge post approval gate
    workflow.add_conditional_edges(
        "human_approval_gate",
        post_ceo_router,
        {
            "dev_qa_node": "dev_qa_node",
            "ceo_node": "ceo_node",
            END: END
        }
    )
    
    workflow.add_edge("dev_qa_node", "security_node")
    workflow.add_edge("security_node", END)
    
    if checkpointer is None:
        checkpointer = MemorySaver()
        
    return workflow.compile(checkpointer=checkpointer)
