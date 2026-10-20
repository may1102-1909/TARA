"""Automated tests for TARA multi-agent LangGraph workflow.

Tests the complete PRD-to-code pipeline:
1. CEO critique and Human Approval Gate
2. Architecture Planner (differentiating web apps vs non-web projects)
3. Developer code generation (separate files matching PRD domain)
4. QA verification, unit test execution, and web preview validation
5. Up to 3 repair attempts when QA checks fail
6. Security hardening, release packaging, and audit reporting
"""

import pytest
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver

from app.graph.state import create_initial_state
from app.graph.workflow import create_tara_workflow
from app.graph.router import post_qa_router
from app.agents.qa import qa_node
from app.agents.developer import developer_node


SAMPLE_CACHE_PRD = """# PRD: Intelligent Cache Service
Build a high-performance in-memory caching service in Python.
Requirements:
- Store key-value pairs with TTL.
- Provide cleanup mechanism for expired entries.
- Include robust error handling and logging.
"""

SAMPLE_WEB_PRD = """# PRD: Analytics Dashboard Web Application
Build an interactive browser dashboard for real-time analytics.
Requirements:
- Web interface with charts and live metric cards.
- Interactive filter controls for date range and status.
- Responsive HTML/CSS layout with client-side JavaScript.
- Backend API endpoint in FastAPI to serve metrics and index.html.
"""


def test_full_approval_path():
    """Verify Start -> CEO -> Gate Interrupt -> Approve -> Planner -> Developer -> QA -> Security -> Complete."""
    checkpointer = MemorySaver()
    app = create_tara_workflow(checkpointer=checkpointer)
    
    session_id = "test-session-approval"
    config = {"configurable": {"thread_id": session_id}}
    initial_state = create_initial_state(session_id, SAMPLE_CACHE_PRD)
    
    # 1. Run workflow until interrupt at human_approval_gate
    for _ in app.stream(initial_state, config=config):
        pass
        
    state = app.get_state(config)
    assert len(state.tasks) > 0
    assert len(state.tasks[0].interrupts) > 0
    interrupt_value = state.tasks[0].interrupts[0].value
    assert interrupt_value["stage"] == "approval_gate"
    assert interrupt_value["critique"] is not None
    assert interrupt_value["revision_count"] == 0
    
    # Verify no code generated yet
    assert state.values["dev_code_files"] == {}
    assert state.values["security_patches"] == {}
    assert state.values["plan"] is None
    
    # 2. Resume with 'approve'
    resume_cmd = Command(resume={"action": "approve", "notes": "Looks good, proceed."})
    for _ in app.stream(resume_cmd, config=config):
        pass
        
    final_state = app.get_state(config)
    assert len(final_state.tasks) == 0
    assert final_state.values["user_action"] == "approve"
    
    # Verify Planner step output
    plan = final_state.values.get("plan")
    assert plan is not None
    assert plan["requires_web"] is False, "Cache service should not require web interface"
    assert len(plan["required_features"]) > 0
    assert len(plan["file_plan"]) > 0
    assert len(plan["acceptance_criteria"]) > 0
    
    # Verify Developer generated separate files without forced index.html
    dev_files = final_state.values["dev_code_files"]
    assert len(dev_files) >= 3
    assert "main.py" in dev_files
    assert "cache.py" in dev_files
    assert "index.html" not in dev_files, "Do not force web files on non-web projects"
    
    # Verify QA ran and passed
    assert final_state.values["qa_passed"] is True
    assert len(final_state.values["qa_refactored_files"]) > 0
    
    # Verify Security node executed
    assert len(final_state.values["security_patches"]) > 0
    assert final_state.values["audit_summary"] is not None
    assert final_state.values["current_stage"] == "security_completed"


def test_request_changes_revision_loop():
    """Verify Start -> CEO -> Gate -> Request Changes -> CEO (revised) -> Gate -> Approve -> Complete."""
    checkpointer = MemorySaver()
    app = create_tara_workflow(checkpointer=checkpointer)
    
    session_id = "test-session-revision"
    config = {"configurable": {"thread_id": session_id}}
    initial_state = create_initial_state(session_id, SAMPLE_CACHE_PRD)
    
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
    initial_state = create_initial_state(session_id, SAMPLE_CACHE_PRD)
    
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
    assert final_state.values["dev_code_files"] == {}
    assert final_state.values["security_patches"] == {}
    assert final_state.values["audit_summary"] is None


def test_workflow_web_app_generation():
    """Verify that a Web PRD generates separate HTML, CSS, JS frontend files + Python backend."""
    checkpointer = MemorySaver()
    app = create_tara_workflow(checkpointer=checkpointer)
    
    session_id = "test-session-web"
    config = {"configurable": {"thread_id": session_id}}
    initial_state = create_initial_state(session_id, SAMPLE_WEB_PRD)
    
    for _ in app.stream(initial_state, config=config):
        pass
        
    # Resume with approval
    resume_cmd = Command(resume={"action": "approve"})
    for _ in app.stream(resume_cmd, config=config):
        pass
        
    final_state = app.get_state(config)
    plan = final_state.values.get("plan")
    assert plan is not None
    assert plan["requires_web"] is True, "Web PRD must set requires_web=True"
    
    dev_files = final_state.values["dev_code_files"]
    assert "index.html" in dev_files or "frontend/index.html" in dev_files, "Web app must generate index.html"
    assert "static/styles.css" in dev_files or "frontend/styles.css" in dev_files, "Web app must generate CSS"
    assert "static/app.js" in dev_files or "frontend/app.js" in dev_files, "Web app must generate JS"
    assert "main.py" in dev_files, "Web app with backend behavior must generate main.py"
    
    assert final_state.values["qa_passed"] is True


def test_qa_repair_loop_feedback():
    """Verify that QA reports failing files and test output back to Developer for repair."""
    state = create_initial_state("test-repair", SAMPLE_CACHE_PRD)
    state["plan"] = {
        "project_summary": "Intelligent Cache Service",
        "required_features": ["Store key-value with TTL", "Cleanup expired entries"],
        "architecture_type": "backend_service",
        "tech_stack": ["Python 3.11"],
        "file_plan": [
            {"path": "main.py", "responsibility": "Entrypoint"},
            {"path": "cache.py", "responsibility": "Cache logic"},
        ],
        "acceptance_criteria": ["Valid syntax", "Cache TTL operations work"],
        "requires_web": False,
        "is_fallback": True,
    }

    # 1. Developer generates initial code
    dev_out = developer_node(state)
    state = {**state, **dev_out}

    # 2. Corrupt one file to trigger QA failure
    broken_files = dict(state["dev_code_files"])
    broken_files["broken_module.py"] = "def syntax_err(: pass"
    state["dev_code_files"] = broken_files
    state["generated_code"] = broken_files

    qa_out_1 = qa_node(state)
    assert qa_out_1["qa_passed"] is False
    assert "broken_module.py" in qa_out_1["failing_files"]
    assert qa_out_1["qa_repair_context"] is not None
    assert "broken_module.py" in qa_out_1["qa_repair_context"]["failing_files"]

    # Verify router loops back to developer_node
    merged_state = {**state, **qa_out_1}
    assert post_qa_router(merged_state) == "developer_node"

    # 3. Simulate Developer fixing the broken file
    del broken_files["broken_module.py"]
    state["dev_code_files"] = broken_files
    state["generated_code"] = broken_files

    qa_out_2 = qa_node(state)
    assert qa_out_2["qa_passed"] is True
    merged_state_2 = {**state, **qa_out_2}
    assert post_qa_router(merged_state_2) == "security_node"


def test_qa_repair_max_attempts_cutoff():
    """Verify that after 3 failed repair attempts, problems are reported clearly and execution proceeds to security."""
    state = create_initial_state("test-max-repairs", SAMPLE_CACHE_PRD)
    state["repair_count"] = 3
    state["qa_passed"] = False
    
    # At attempt 3, router must proceed to security_node instead of looping infinitely
    route = post_qa_router(state)
    assert route == "security_node"
