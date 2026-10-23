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

class PRDChecklistItem(TypedDict, total=False):
    id: str  # e.g. "REQ-1"
    title: str
    category: str  # e.g. "functional", "technical", "ui", "data"
    description: str
    clarity: Literal["clear", "unclear", "missing_detail"]
    flag_notes: Optional[str]

class RequirementReview(TypedDict, total=False):
    id: str
    title: str
    status: Literal["passed", "failed", "not_checked"]
    reason: str

class PlannedFileReview(TypedDict, total=False):
    path: str
    purpose: str
    status: Literal["passed", "failed", "missing"]
    reason: str

class IntegrationReview(TypedDict, total=False):
    name: str
    passed: bool
    details: str

class PreviewReview(TypedDict, total=False):
    can_preview: bool
    preview_type: str  # "web_preview", "api_docs", "terminal_cli"
    preview_url: Optional[str]
    details: str

class PlannedFile(TypedDict, total=False):
    path: str
    purpose: str
    responsibility: str  # backward-compatible alias for purpose

class PlannerOutput(TypedDict, total=False):
    app_summary: str
    feature_list: List[str]
    proposed_files: List[PlannedFile]
    implementation_order: List[str]
    # Backward-compatible fields
    project_summary: str
    required_features: List[str]
    architecture_type: str  # e.g. "web_app", "backend_api", "cli_tool", "library"
    tech_stack: List[str]
    file_plan: List[PlannedFile]
    acceptance_criteria: List[str]
    requires_web: bool
    selected_skills: List[str]
    is_fallback: bool

class AgentState(TypedDict, total=False):
    session_id: str
    prd_filename: str
    prd_text: str
    prd_checklist: List[PRDChecklistItem]
    unclear_requirements: List[str]
    
    # CEO Review & Revision Loop
    ceo_critique: Optional[CEOCritique]
    user_action: Optional[Literal["approve", "request_changes", "reject"]]
    human_feedback_notes: Annotated[List[str], operator.add]
    revision_count: int

    # Planner Artifacts
    plan: Optional[PlannerOutput]
    selected_skills: List[str]
    
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
    qa_unresolved_summary: Optional[str]
    
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
        "prd_checklist": [],
        "unclear_requirements": [],
        "ceo_critique": None,
        "user_action": None,
        "human_feedback_notes": [],
        "revision_count": 0,
        "plan": None,
        "selected_skills": [],
        "dev_code_files": {},
        "qa_refactored_files": {},
        "qa_changelog": [],
        "qa_report": None,
        "qa_passed": None,
        "repair_count": 0,
        "qa_repair_context": None,
        "test_output": None,
        "failing_files": [],
        "qa_unresolved_summary": None,
        "security_patches": {},
        "security_findings": [],
        "audit_summary": None,
        "current_stage": "initialized",
        "logs": [],
        "error": None,
    }

