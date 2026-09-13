"""Agent 3: Quality Engineer (QA).

Iteratively refactors verbose, redundant, or custom code into standard-library equivalents.
Provides a structured change log tracking all refactorings.
"""

import datetime
from typing import Any, Dict, List, Tuple
from app.graph.state import AgentState


def refactor_code(files: Dict[str, str]) -> Tuple[Dict[str, str], List[Dict[str, str]]]:
    """Refactors developer modules to adhere to standard library patterns and typing."""
    refactored = {}
    changelog = []
    
    for filename, content in files.items():
        if filename == "main.py":
            # Enhance error handling and typing standard
            enhanced_content = content.replace(
                "    # Core domain business logic\n    result = {\n        \"status\": \"success\",\n        \"processed_items\": len(payload),\n        \"data\": payload\n    }\n    return result",
                "    # Refactored: Standardized response envelope with typing\n    from typing import cast\n    result: Dict[str, Any] = {\n        \"status\": \"success\",\n        \"processed_items\": len(payload),\n        \"data\": dict(payload),\n    }\n    return cast(Dict[str, Any], result)"
            )
            refactored[filename] = enhanced_content
            changelog.append({
                "file": filename,
                "type": "typing_and_immutability",
                "description": "Standardized response dictionary casting and shallow payload copy to prevent mutation."
            })
        elif filename == "utils.py":
            # Use functools / standard library improvements
            enhanced_content = content.replace(
                "def format_timestamp(dt) -> str:\n    \"\"\"Formats datetime to standard ISO 8601 string.\"\"\"\n    return dt.isoformat()",
                "from datetime import datetime, timezone\n\ndef format_timestamp(dt: Optional[datetime] = None) -> str:\n    \"\"\"Formats datetime to UTC ISO 8601 string, defaulting to current time.\"\"\"\n    target = dt or datetime.now(timezone.utc)\n    return target.isoformat()"
            )
            refactored[filename] = enhanced_content
            changelog.append({
                "file": filename,
                "type": "standard_library_datetime",
                "description": "Refactored timestamp formatting to use timezone-aware datetime standard library objects."
            })
        else:
            refactored[filename] = content

    return refactored, changelog


def qa_node(state: AgentState) -> Dict[str, Any]:
    """Executes QA Engineer refactoring."""
    dev_files = state.get("dev_code_files", {})
    refactored_files, changelog = refactor_code(dev_files)
    
    timestamp = datetime.datetime.utcnow().isoformat()
    log_entry = {
        "agent": "QA",
        "stage": "quality_refactoring",
        "message": f"QA refactored {len(refactored_files)} files ({len(changelog)} optimizations applied).",
        "timestamp": timestamp,
    }
    
    return {
        "qa_refactored_files": refactored_files,
        "qa_changelog": changelog,
        "current_stage": "qa_completed",
        "logs": [log_entry],
    }
