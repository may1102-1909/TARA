"""Safe loader for trusted TARA application engineering skills."""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Base directory for application skills
SKILLS_DIR = (Path(__file__).resolve().parent / "skills").resolve()

# Strict slug validation to prevent path traversal
_SAFE_SKILL_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def list_available_skills() -> List[str]:
    """Returns a list of all available skill names in the trusted skills directory."""
    if not SKILLS_DIR.is_dir():
        return []

    available = []
    for child in SKILLS_DIR.iterdir():
        if child.is_dir() and (child / "SKILL.md").is_file():
            available.append(child.name)
    return sorted(available)


def load_skill(skill_name: str) -> Optional[str]:
    """Safely loads the SKILL.md content for a given skill name.
    
    Validates the name and ensures resolution remains strictly inside SKILLS_DIR.
    Returns the file content as a string, or None if not found or invalid.
    """
    if not skill_name or not isinstance(skill_name, str):
        return None

    clean_name = skill_name.strip()
    if not _SAFE_SKILL_NAME_RE.match(clean_name):
        logger.warning("Rejected invalid skill name pattern: %s", skill_name)
        return None

    skill_file = (SKILLS_DIR / clean_name / "SKILL.md").resolve()

    # Security check: Enforce that the target file is strictly within SKILLS_DIR
    try:
        skill_file.relative_to(SKILLS_DIR)
    except ValueError:
        logger.error("Path traversal attempt detected for skill name: %s", skill_name)
        return None

    if not skill_file.is_file():
        logger.debug("Skill file not found: %s", skill_file)
        return None

    try:
        return skill_file.read_text(encoding="utf-8")
    except Exception as exc:
        logger.error("Failed to read skill %s: %s", skill_name, exc)
        return None


def load_skills(skill_names: List[str]) -> Dict[str, str]:
    """Loads multiple skills by name, returning a dictionary of {skill_name: content}."""
    loaded: Dict[str, str] = {}
    if not skill_names:
        return loaded

    for name in skill_names:
        content = load_skill(name)
        if content:
            loaded[name] = content
    return loaded


def format_skills_for_prompt(skills_dict: Dict[str, str]) -> str:
    """Formats loaded skills into a clean context block suitable for LLM injection."""
    if not skills_dict:
        return ""

    sections = ["### Active Engineering Skills & Best Practices:"]
    for skill_name, content in skills_dict.items():
        sections.append(f"\n--- Skill: {skill_name} ---")
        sections.append(content.strip())
    sections.append("\nStrictly adhere to the architectural patterns and standards defined in these skills.")
    return "\n".join(sections)
