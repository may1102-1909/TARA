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
from app.core.llm import call_gemini_with_fallback

logger = logging.getLogger(__name__)

# Initialize GenAI client only if valid standard AIza key is present
try:
    _key = os.getenv("GEMINI_API_KEY", "")
    if _key and _key.startswith("AIzaSy"):
        client = genai.Client(api_key=_key)
    else:
        client = None
except Exception:
    client = None


class Verdict(str, Enum):
    APPROVED = "APPROVED"
    NEEDS_REVISION = "NEEDS_REVISION"
    REJECTED = "REJECTED"


class PRDChecklistItemModel(BaseModel):
    id: str = Field(description="Unique requirement identifier like REQ-1, REQ-2")
    title: str = Field(description="Short human-readable requirement title")
    category: str = Field(default="functional", description="Requirement category: functional, technical, ui, data, or security")
    description: str = Field(description="Concrete specification of what must be built")
    clarity: str = Field(default="clear", description="Clarity status: 'clear', 'unclear', or 'missing_detail'")
    flag_notes: Optional[str] = Field(default=None, description="Explanation when details are missing or unclear rather than silently guessing")


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
    checklist: list[PRDChecklistItemModel] = Field(
        default_factory=list,
        description="Extracted PRD requirements checklist with clear/unclear designations and flags."
    )
    unclear_details: list[str] = Field(
        default_factory=list,
        description="Flagged important missing or ambiguous details that should not be silently guessed."
    )


def extract_prd_checklist_heuristic(prd_text: str) -> tuple[list[PRDChecklistItemModel], list[str]]:
    """Heuristically extracts requirements into a structured checklist and flags unclear or missing details."""
    import re
    lines = (prd_text or "").splitlines()
    raw_items = []
    
    # 1. Parse lines for bullet points, numbered lists, or bold requirement lines
    for line in lines:
        cleaned = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", line).strip()
        cleaned = re.sub(r"^\s*#+\s*", "", cleaned).strip()
        if not cleaned:
            continue
        lower_l = cleaned.lower()
        if lower_l.startswith("goal:") or lower_l.startswith("target:") or lower_l.startswith("features:") or lower_l.startswith("requirements:"):
            content = re.sub(r"^[A-Za-z\s]+:\s*", "", cleaned).strip()
            if content:
                raw_items.append(content)
        elif re.match(r"^\s*[-*+]\s+", line) or re.match(r"^\s*\d+[.)]\s+", line):
            if len(cleaned) > 4:
                raw_items.append(cleaned)

    # If no list items were extracted, split into sentences
    if not raw_items:
        sentences = [s.strip() for s in re.split(r"[.\n]+", prd_text or "") if len(s.strip()) > 15]
        raw_items = sentences[:8]

    if not raw_items:
        raw_items = ["Implement primary application workflows as specified in PRD."]

    checklist: list[PRDChecklistItemModel] = []
    unclear_details: list[str] = []

    for idx, item in enumerate(raw_items, 1):
        req_id = f"REQ-{idx}"
        item_lower = item.lower()
        
        # Determine category
        if any(w in item_lower for w in ["ui", "button", "screen", "frontend", "html", "css", "view", "page", "modal"]):
            cat = "ui"
        elif any(w in item_lower for w in ["database", "storage", "cache", "persist", "store", "table"]):
            cat = "data"
        elif any(w in item_lower for w in ["auth", "jwt", "token", "security", "permission", "password"]):
            cat = "security"
        elif any(w in item_lower for w in ["api", "endpoint", "route", "http", "fastapi", "rest"]):
            cat = "technical"
        else:
            cat = "functional"

        # Check clarity and detail depth
        words = item.split()
        title = " ".join(words[:5]).rstrip(":,.")
        
        clarity = "clear"
        flag_notes = None

        if len(words) < 5:
            clarity = "missing_detail"
            flag_notes = f"Requirement '{item}' is terse; exact behavior, parameters, and edge cases are unspecified."
            unclear_details.append(flag_notes)
        elif any(ambig in item_lower for ambig in ["etc", "tbd", "as needed", "fast", "scalable", "user friendly"]):
            clarity = "unclear"
            flag_notes = f"Subjective or unspecified phrase detected in: '{item}'. Specific metrics or contracts needed."
            unclear_details.append(flag_notes)
        elif cat == "ui" and not any(action in item_lower for action in ["click", "display", "input", "submit", "select", "shows", "renders"]):
            clarity = "unclear"
            flag_notes = "UI component mentioned without interactive behavior or state expectations."
            unclear_details.append(flag_notes)

        checklist.append(PRDChecklistItemModel(
            id=req_id,
            title=title,
            category=cat,
            description=item,
            clarity=clarity,
            flag_notes=flag_notes
        ))

    # Overarching architectural omissions
    prd_lower = (prd_text or "").lower()
    if ("store" in prd_lower or "data" in prd_lower or "save" in prd_lower) and not any(w in prd_lower for w in ["sqlite", "postgres", "redis", "schema", "in-memory", "json", "file"]):
        flag = "Data storage is required, but persistence mechanism, schema, and retention rules are unspecified."
        if flag not in unclear_details:
            unclear_details.append(flag)
            checklist.append(PRDChecklistItemModel(
                id=f"REQ-{len(checklist) + 1}",
                title="Data Persistence Mechanics",
                category="data",
                description="Define data schema and storage mechanism.",
                clarity="missing_detail",
                flag_notes=flag
            ))

    if ("user" in prd_lower or "account" in prd_lower) and not any(w in prd_lower for w in ["auth", "token", "password", "jwt", "session"]):
        flag = "User concept present, but authentication and session authorization contracts are omitted."
        if flag not in unclear_details:
            unclear_details.append(flag)
            checklist.append(PRDChecklistItemModel(
                id=f"REQ-{len(checklist) + 1}",
                title="Authentication & Authorization",
                category="security",
                description="Specify authentication protocol and permissions.",
                clarity="missing_detail",
                flag_notes=flag
            ))

    return checklist, unclear_details


def evaluate_prd_fallback(
    prd_text: str,
    revision_count: int = 0,
    human_notes: Optional[List[str]] = None,
) -> CEOCritique:
    """Deterministic fallback evaluator when LLM API keys are not supplied or network fails."""
    notes = human_notes or []
    is_revision = revision_count > 0

    checklist, unclear_details = extract_prd_checklist_heuristic(prd_text)

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
            "The core value proposition is sound. Focus development on a modular architecture "
            "with clear separation of concerns, robust logging, and SAST-ready structure."
        )

    return CEOCritique(
        verdict=verdict,
        feature_gaps=feature_gaps if feature_gaps else ["No major feature gaps detected in current scope."],
        structural_flaws=structural_flaws if structural_flaws else ["No fatal structural flaws identified."],
        recommendation=recommendation,
        checklist=checklist,
        unclear_details=unclear_details,
    )


def evaluate_prd(
    prd_content: str,
    revision_count: int = 0,
    human_notes: Optional[List[str]] = None,
) -> CEOCritique:
    """Evaluates a PRD from a CEO perspective and returns a structured CEOCritique."""
    global client
    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
    if client is None and api_key and api_key.startswith("AIzaSy"):
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
                "Extract all discrete requirements into the structured 'checklist', marking clarity as 'clear', 'unclear', or 'missing_detail'. "
                "Explicitly flag all important missing, ambiguous, or unstated details in 'unclear_details' rather than silently guessing. "
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

            response = call_gemini_with_fallback(
                client=client,
                contents=prompt,
                config=config,
                preferred_model=settings.default_model or "gemini-3.5-flash",
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
    """CEO Node executing evaluation, requirement extraction, and revision logic."""
    revision_count = state.get("revision_count", 0)
    human_notes = state.get("human_feedback_notes", [])

    # If looping back from request_changes, increment revision count
    if state.get("user_action") == "request_changes":
        revision_count += 1

    prd_text = state.get("prd_text", "")
    critique = evaluate_prd(prd_text, revision_count, human_notes)

    checklist_dicts = [item.model_dump() for item in critique.checklist] if critique.checklist else []
    unclear_list = list(critique.unclear_details) if critique.unclear_details else []

    timestamp = datetime.datetime.utcnow().isoformat()
    log_entry = {
        "agent": "CEO",
        "stage": "ceo_review",
        "revision": revision_count,
        "message": f"CEO evaluation completed (Verdict: {critique.verdict.value}, {len(checklist_dicts)} requirements extracted, {len(unclear_list)} unclear details flagged). Waiting at Human Approval Gate.",
        "timestamp": timestamp,
        "checklist_count": len(checklist_dicts),
        "unclear_count": len(unclear_list),
    }

    return {
        "ceo_critique": critique.model_dump(mode="json"),
        "prd_checklist": checklist_dicts,
        "unclear_requirements": unclear_list,
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

