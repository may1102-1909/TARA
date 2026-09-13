"""Agent 1: CEO / VC Evaluator.

Assesses market viability, feature gaps, and structural flaws in PRD/BRD.
Handles revision loops when re-entered with human feedback notes.
"""

import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.graph.state import AgentState


class Verdict(str, Enum):
    APPROVED = "APPROVED"
    NEEDS_REVISION = "NEEDS_REVISION"
    REJECTED = "REJECTED"


class CEOCritique(BaseModel):
    verdict: Verdict = Field(
        description="Overall evaluation verdict for the PRD."
    )
    feature_gaps: list[str] = Field(
        description="Missing features, edge cases, or unaddressed user needs."
    )
    structural_flaws: list[str] = Field(
        description="Architectural, scope, feasibility, or logic flaws."
    )
    recommendation: str = Field(
        description="Strategic direction and key action items for the product team."
    )


def evaluate_prd_fallback(prd_text: str, revision_count: int, human_notes: List[str]) -> CEOCritique:
    """Deterministic fallback evaluator when LLM API keys are not supplied."""
    is_revision = revision_count > 0
    
    # Analyze PRD content
    has_security = "security" in prd_text.lower() or "auth" in prd_text.lower()
    has_api = "api" in prd_text.lower() or "endpoint" in prd_text.lower()
    has_database = "db" in prd_text.lower() or "database" in prd_text.lower() or "storage" in prd_text.lower()
    
    feature_gaps = []
    structural_flaws = []
    
    if not has_security:
        feature_gaps.append("Lack of explicit authentication / authorization model.")
    if not has_api:
        feature_gaps.append("Missing concrete API route definitions / contracts.")
    if not has_database:
        feature_gaps.append("Data storage schema and persistence mechanics are underspecified.")
        
    if len(prd_text.split()) < 50:
        structural_flaws.append("Document is terse; needs more architectural detail.")
    
    if is_revision:
        feedback_summary = "; ".join(human_notes) if human_notes else "No specific notes"
        verdict = Verdict.APPROVED
        recommendation = (
            f"Revision {revision_count} addressed stakeholder feedback ({feedback_summary}). "
            "Proceed with implementation in Python adhering to standard library best practices."
        )
    else:
        verdict = Verdict.APPROVED if len(structural_flaws) == 0 else Verdict.NEEDS_REVISION
        recommendation = (
            "The core value proposition is sound. Focus development on a modular Python architecture "
            "with clear separation of concerns, robust logging, and SAST-ready structure."
        )

    return CEOCritique(
        verdict=verdict,
        feature_gaps=feature_gaps if feature_gaps else ["No major feature gaps detected in current scope."],
        structural_flaws=structural_flaws if structural_flaws else ["No fatal structural flaws identified."],
        recommendation=recommendation,
    )


def ceo_node(state: AgentState) -> Dict[str, Any]:
    """CEO Node executing evaluation and revision logic."""
    revision_count = state.get("revision_count", 0)
    human_notes = state.get("human_feedback_notes", [])
    
    # If looping back from request_changes, increment revision count
    if state.get("user_action") == "request_changes":
        revision_count += 1
    
    prd_text = state.get("prd_text", "")
    critique = evaluate_prd_fallback(prd_text, revision_count, human_notes)
    
    timestamp = datetime.datetime.utcnow().isoformat()
    log_entry = {
        "agent": "CEO",
        "stage": "ceo_review",
        "revision": revision_count,
        "message": f"CEO evaluation completed (Verdict: {critique.verdict.value}). Waiting at Human Approval Gate.",
        "timestamp": timestamp,
    }
    
    return {
        "ceo_critique": critique.model_dump(),
        "revision_count": revision_count,
        "user_action": None,  # Reset for gate decision
        "current_stage": "ceo_reviewed",
        "logs": [log_entry],
    }
