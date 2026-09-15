"""Antigravity SDK Agent Adapter for Reading, Writing, and Modifying Code.

Utilizes google-antigravity SDK (or antigravity-sdk-python) to spawn autonomous agents
equipped with built-in workspace file-system tools (READ_FILE, WRITE_FILE, LIST_DIR)
for direct codebase inspection and modification.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

try:
    from google.antigravity import (
        Agent,
        BuiltinTools,
        CapabilitiesConfig,
        LocalAgentConfig,
    )
    ANTIGRAVITY_AVAILABLE = True
except ImportError:
    ANTIGRAVITY_AVAILABLE = False
    Agent = None
    LocalAgentConfig = None
    CapabilitiesConfig = None
    BuiltinTools = None

from app.core.config import settings

logger = logging.getLogger(__name__)


def is_antigravity_installed() -> bool:
    """Checks whether google-antigravity is available in the current environment."""
    return ANTIGRAVITY_AVAILABLE


# Mapping from standard workspace capability names to BuiltinTools enums
WORKSPACE_TOOLS_MAP: Dict[str, List[Any]] = {}
if ANTIGRAVITY_AVAILABLE and BuiltinTools is not None:
    WORKSPACE_TOOLS_MAP = {
        "READ_FILE": [BuiltinTools.VIEW_FILE],
        "WRITE_FILE": [BuiltinTools.EDIT_FILE, BuiltinTools.CREATE_FILE],
        "LIST_DIR": [BuiltinTools.LIST_DIR],
        "VIEW_FILE": [BuiltinTools.VIEW_FILE],
        "CREATE_FILE": [BuiltinTools.CREATE_FILE],
        "EDIT_FILE": [BuiltinTools.EDIT_FILE],
        "FIND_FILE": [BuiltinTools.FIND_FILE],
        "SEARCH_DIR": [BuiltinTools.SEARCH_DIR],
    }


def resolve_workspace_tools(
    capabilities: Optional[Sequence[Union[str, Any]]] = None,
) -> List[Any]:
    """Resolves requested workspace capability identifiers into BuiltinTools enum instances."""
    if not ANTIGRAVITY_AVAILABLE or BuiltinTools is None:
        return []

    if capabilities is None:
        return [
            BuiltinTools.VIEW_FILE,
            BuiltinTools.CREATE_FILE,
            BuiltinTools.EDIT_FILE,
            BuiltinTools.LIST_DIR,
            BuiltinTools.FIND_FILE,
            BuiltinTools.SEARCH_DIR,
        ]

    resolved: List[Any] = []
    for cap in capabilities:
        if isinstance(cap, str):
            key = cap.upper().strip()
            if key in WORKSPACE_TOOLS_MAP:
                for t in WORKSPACE_TOOLS_MAP[key]:
                    if t not in resolved:
                        resolved.append(t)
            elif hasattr(BuiltinTools, key):
                t = getattr(BuiltinTools, key)
                if t not in resolved:
                    resolved.append(t)
        elif cap not in resolved:
            resolved.append(cap)

    return resolved


def create_antigravity_agent_config(
    system_instructions: Optional[str] = None,
    workspace_path: Optional[str] = None,
    capabilities: Optional[Sequence[Union[str, Any]]] = None,
    enabled_tools: Optional[List[Any]] = None,
) -> Any:
    """Builds a LocalAgentConfig for workspace code generation, inspection, and editing."""
    if not ANTIGRAVITY_AVAILABLE or LocalAgentConfig is None:
        raise RuntimeError("google-antigravity is not installed. Run: pip install google-antigravity")

    instructions = system_instructions or (
        "You are TARA's Antigravity Autonomous Software Engineer. "
        "You inspect, read, write, and refactor codebases using your built-in file tools."
    )

    workspace = workspace_path or str(settings.storage_dir)

    # Allow either enabled_tools (direct list) or capabilities (e.g. READ_FILE, WRITE_FILE, LIST_DIR)
    if enabled_tools is not None:
        tools = enabled_tools
    else:
        tools = resolve_workspace_tools(capabilities)

    capabilities_config = CapabilitiesConfig(
        enabled_tools=tools,
    )

    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY", "")

    config_kwargs: Dict[str, Any] = {
        "system_instructions": instructions,
        "capabilities": capabilities_config,
        "workspaces": [str(Path(workspace).resolve())],
    }

    if api_key:
        config_kwargs["api_key"] = api_key

    return LocalAgentConfig(**config_kwargs)
