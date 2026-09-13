"""Automated tests for TARA multi-agent LangGraph workflow."""

import pytest
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver

from app.graph.state import create_initial_state
from app.graph.workflow import create_tara_workflow


SAMPLE_PRD = """# PRD: Intelligent Cache Service
Build a high-performance in-memory caching service in Python.
Requirements:
- Store key-value pairs with TTL.
- Provide cleanup mechanism for expired entries.
- Include robust error handling and logging.
"""


def test_full_approval_path():
    """Verify Start -> CEO -> Gate Interrupt -> Approve -> Dev/QA -> Security -> Complete."""
    checkpointer = MemorySaver()
    app = create_tara_workflow(checkpointer=checkpointer)
    
    session_id = "test-session-approval"
    config = {"configurable": {"thread_id": session_id}}
    initial_state = create_initial_state(session_id, SAMPLE_PRD)
    
    # 1. Run workflow until interrupt at human_approval_gate
    events = []
    for event in app.stream(initial_state, config=config):
        events.append(event)
        
    state = app.get_state(config)
    assert len(state.tasks) > 0
    # Verify interrupt is active
    assert len(state.tasks[0].interrupts) > 0
    interrupt_value = state.tasks[0].interrupts[0].value
    assert interrupt_value["stage"] == "approval_gate"
    assert interrupt_value["critique"] is not None
    assert interrupt_value["revision_count"] == 0
    
    # Verify no code generated yet
    assert state.values["dev_code_files"] == {}
    assert state.values["security_patches"] == {}
    
    # 2. Resume with 'approve'
    resume_cmd = Command(resume={"action": "approve", "notes": "Looks good, proceed."})
    for event in app.stream(resume_cmd, config=config):
        events.append(event)
        
    final_state = app.get_state(config)
    # Execution should now be finished (no pending tasks)
    assert len(final_state.tasks) == 0
    assert final_state.values["user_action"] == "approve"
    assert len(final_state.values["dev_code_files"]) > 0
    assert "main.py" in final_state.values["dev_code_files"]
    assert len(final_state.values["qa_refactored_files"]) > 0
    assert len(final_state.values["security_patches"]) > 0
    assert final_state.values["audit_summary"] is not None
    assert final_state.values["current_stage"] == "security_completed"


def test_request_changes_revision_loop():
    """Verify Start -> CEO -> Gate -> Request Changes -> CEO (revised) -> Gate -> Approve -> Complete."""
    checkpointer = MemorySaver()
    app = create_tara_workflow(checkpointer=checkpointer)
    
    session_id = "test-session-revision"
    config = {"configurable": {"thread_id": session_id}}
    initial_state = create_initial_state(session_id, SAMPLE_PRD)
    
    # 1. Run until initial interrupt
    for _ in app.stream(initial_state, config=config):
        pass
        
    state_v0 = app.get_state(config)
    assert state_v0.tasks[0].interrupts[0].value["revision_count"] == 0
    
    # 2. Request changes
    notes = "Add explicit memory bounds and LRU eviction policy."
    resume_request_changes = Command(resume={"action": "request_changes", "notes": notes})
    
    for _ in app.stream(resume_request_changes, config=config):
        pass
        
    state_v1 = app.get_state(config)
    # Graph should have looped back to ceo_node and halted AGAIN at human_approval_gate!
    assert len(state_v1.tasks) > 0
    assert len(state_v1.tasks[0].interrupts) > 0
    interrupt_v1 = state_v1.tasks[0].interrupts[0].value
    assert interrupt_v1["revision_count"] == 1
    assert notes in state_v1.values["human_feedback_notes"]
    
    # 3. Now approve revision 1
    resume_approve = Command(resume={"action": "approve"})
    for _ in app.stream(resume_approve, config=config):
        pass
        
    final_state = app.get_state(config)
    assert len(final_state.tasks) == 0
    assert final_state.values["revision_count"] == 1
    assert final_state.values["user_action"] == "approve"
    assert len(final_state.values["dev_code_files"]) > 0


def test_rejection_path():
    """Verify Start -> CEO -> Gate -> Reject -> Terminate with no code generated."""
    checkpointer = MemorySaver()
    app = create_tara_workflow(checkpointer=checkpointer)
    
    session_id = "test-session-reject"
    config = {"configurable": {"thread_id": session_id}}
    initial_state = create_initial_state(session_id, SAMPLE_PRD)
    
    # 1. Run until interrupt
    for _ in app.stream(initial_state, config=config):
        pass
        
    # 2. Reject
    resume_reject = Command(resume={"action": "reject", "notes": "Not viable at this time."})
    for _ in app.stream(resume_reject, config=config):
        pass
        
    final_state = app.get_state(config)
    assert len(final_state.tasks) == 0
    assert final_state.values["user_action"] == "reject"
    # FR-4/7: No code should be generated or executed
    assert final_state.values["dev_code_files"] == {}
    assert final_state.values["security_patches"] == {}
    assert final_state.values["audit_summary"] is None
