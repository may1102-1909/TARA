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

class AgentState(TypedDict, total=False):
    session_id: str
    prd_filename: str
    prd_text: str
    
    # CEO Review & Revision Loop
    ceo_critique: Optional[CEOCritique]
    user_action: Optional[Literal["approve", "request_changes", "reject"]]
    human_feedback_notes: Annotated[List[str], operator.add]
    revision_count: int
    
    # Developer Artifacts
    dev_code_files: Dict[str, str]  # filepath -> content
    
    # QA Refactoring Artifacts
    qa_refactored_files: Dict[str, str]
    qa_changelog: List[Dict[str, str]]
    
    # Security Hardening & Audit
    security_patches: Dict[str, str]
    security_findings: List[SecurityFinding]
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
        "dev_code_files": {},
        "qa_refactored_files": {},
        "qa_changelog": [],
        "security_patches": {},
        "security_findings": [],
        "audit_summary": None,
        "current_stage": "initialized",
        "logs": [],
        "error": None,
    }
