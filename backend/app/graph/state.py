"""AgentState definition for TARA multi-agent orchestration."""

from typing import Annotated, Dict, List, Literal, Optional, Any
from typing_extensions import TypedDict
import operator

class CEOCritique(TypedDict, total=False):
    verdict: str  # e.g. "viable", "needs_revision", "rejected"
    market_viability: str
    feature_gaps: List[str]
    structural_flaws: List[str]
    recommendation: str
    raw_commentary: str

class SecurityFinding(TypedDict, total=False):
    category: str  # OWASP category, e.g. "A03:2021-Injection"
    severity: Literal["low", "medium", "high", "critical"]
    file: str
    line: Optional[int]
    description: str
    patch_applied: Optional[str]
    residual_risk: Optional[str]

class AuditSummary(TypedDict, total=False):
    timeline: List[Dict[str, str]]
    key_decisions: List[str]
    unresolved_risks: List[str]
    completed_at: Optional[str]

class PlannedFile(TypedDict, total=False):
    path: str
    responsibility: str

class PlannerOutput(TypedDict, total=False):
    project_summary: str
    required_features: List[str]
    architecture_type: str  # e.g. "web_app", "backend_api", "cli_tool", "library"
    tech_stack: List[str]
    file_plan: List[PlannedFile]
    acceptance_criteria: List[str]
    requires_web: bool
    is_fallback: bool

class AgentState(TypedDict, total=False):
    session_id: str
    prd_filename: str
    prd_text: str
    
    # CEO Review & Revision Loop
    ceo_critique: Optional[CEOCritique]
    user_action: Optional[Literal["approve", "request_changes", "reject"]]
    human_feedback_notes: Annotated[List[str], operator.add]
    revision_count: int

    # Planner Artifacts
    plan: Optional[PlannerOutput]
    
    # Developer Artifacts
    dev_code_files: Dict[str, str]  # filepath -> content
    generated_code: Optional[Dict[str, str]]
    code_summary: Optional[str]
    
    # QA & Repair Artifacts
    qa_refactored_files: Dict[str, str]
    qa_changelog: List[Dict[str, str]]
    qa_report: Optional[Dict[str, Any]]
    qa_passed: Optional[bool]
    repair_count: int
    qa_repair_context: Optional[Dict[str, Any]]
    test_output: Optional[str]
    failing_files: Optional[List[str]]
    
    # Security Hardening & Audit
    security_patches: Dict[str, str]
    security_findings: List[SecurityFinding]
    security_report: Optional[Dict[str, Any]]
    security_passed: Optional[bool]
    audit_summary: Optional[AuditSummary]
    
    # Workflow Stage & Stream Logs
    current_stage: str
    logs: Annotated[List[Dict[str, Any]], operator.add]
    error: Optional[str]

def create_initial_state(
    session_id: str,
    prd_text: str,
    prd_filename: str = "PRD.md"
) -> AgentState:
    """Helper to initialize a clean AgentState for a new session."""
    return {
        "session_id": session_id,
        "prd_filename": prd_filename,
        "prd_text": prd_text,
        "ceo_critique": None,
        "user_action": None,
        "human_feedback_notes": [],
        "revision_count": 0,
        "plan": None,
        "dev_code_files": {},
        "qa_refactored_files": {},
        "qa_changelog": [],
        "qa_report": None,
        "qa_passed": None,
        "repair_count": 0,
        "qa_repair_context": None,
        "test_output": None,
        "failing_files": [],
        "security_patches": {},
        "security_findings": [],
        "audit_summary": None,
        "current_stage": "initialized",
        "logs": [],
        "error": None,
    }

