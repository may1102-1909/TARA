"""Agent 1: CEO / VC Evaluator.

Assesses market viability, feature gaps, and structural flaws in PRD/BRD.
Handles revision loops when re-entered with human feedback notes.
Supports both live Google Gemini (via google-genai) and deterministic local evaluation.
"""

import datetime
import logging
import os
import sys
from pathlib import Path
from enum import Enum
from typing import Any, Dict, List, Optional
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# Ensure backend root is on sys.path for direct script execution
_backend_dir = str(Path(__file__).resolve().parent.parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from app.graph.state import AgentState
from app.core.config import settings

logger = logging.getLogger(__name__)

# Client picks up environment variable GEMINI_API_KEY automatically
try:
    client = genai.Client()
except Exception:
    client = None


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


def evaluate_prd_fallback(
    prd_text: str,
    revision_count: int = 0,
    human_notes: Optional[List[str]] = None,
) -> CEOCritique:
    """Deterministic fallback evaluator when LLM API keys are not supplied or network fails."""
    notes = human_notes or []
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
        feedback_summary = "; ".join(notes) if notes else "No specific notes"
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


def evaluate_prd(
    prd_content: str,
    revision_count: int = 0,
    human_notes: Optional[List[str]] = None,
) -> CEOCritique:
    """Evaluates a PRD from a CEO perspective and returns a structured CEOCritique."""
    global client
    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
    if client is None and api_key:
        try:
            client = genai.Client(api_key=api_key)
        except Exception as init_exc:
            logger.warning("Failed to initialize GenAI client in CEO agent: %s", init_exc)
            client = None

    if client is not None:
        try:
            system_instruction = (
                "You are an expert Chief Executive Officer (CEO). Your role is to critically "
                "evaluate Product Requirement Documents (PRDs) for strategic alignment, "
                "market viability, missing requirements, and operational feasibility. "
                "Be candid, concise, and rigorous in your evaluation."
            )

            prompt = f"Evaluate the following Product Requirement Document (PRD):\n\n{prd_content}"
            if revision_count and revision_count > 0:
                notes_str = "\n- ".join(human_notes or []) if human_notes else "None"
                prompt += (
                    f"\n\n### Revision Round: #{revision_count}\n"
                    f"### Stakeholder Feedback to Incorporate:\n- {notes_str}\n"
                )

            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=CEOCritique,
                temperature=0.2,  # Low temperature for consistent analytical evaluation
            )

            response = client.models.generate_content(
                model=settings.default_model or "gemini-3.6-flash",
                contents=prompt,
                config=config,
            )

            # response.parsed contains the automatically deserialized CEOCritique instance
            if response.parsed and isinstance(response.parsed, CEOCritique):
                return response.parsed
            if response.text:
                return CEOCritique.model_validate_json(response.text)
        except Exception as exc:
            logger.warning("Gemini evaluation error, falling back to local heuristic evaluator: %s", exc)

    return evaluate_prd_fallback(prd_content, revision_count, human_notes or [])


def ceo_node(state: AgentState) -> Dict[str, Any]:
    """CEO Node executing evaluation and revision logic."""
    revision_count = state.get("revision_count", 0)
    human_notes = state.get("human_feedback_notes", [])

    # If looping back from request_changes, increment revision count
    if state.get("user_action") == "request_changes":
        revision_count += 1

    prd_text = state.get("prd_text", "")
    critique = evaluate_prd(prd_text, revision_count, human_notes)

    timestamp = datetime.datetime.utcnow().isoformat()
    log_entry = {
        "agent": "CEO",
        "stage": "ceo_review",
        "revision": revision_count,
        "message": f"CEO evaluation completed (Verdict: {critique.verdict.value}). Waiting at Human Approval Gate.",
        "timestamp": timestamp,
    }

    return {
        "ceo_critique": critique.model_dump(mode="json"),
        "revision_count": revision_count,
        "user_action": None,  # Reset for gate decision
        "current_stage": "ceo_reviewed",
        "logs": [log_entry],
    }


if __name__ == "__main__":
    sample_prd = """
    # Feature: One-Click Checkout
    Goal: Allow users to buy items without passing through the cart.
    Target Audience: Mobile shoppers.
    Requirements: Add a 'Buy Now' button on product pages.
    """

    critique: CEOCritique = evaluate_prd(sample_prd)

    print(f"Verdict: {critique.verdict}")
    print(f"Gaps: {critique.feature_gaps}")
    print(f"Flaws: {critique.structural_flaws}")
    print(f"Recommendation: {critique.recommendation}")

