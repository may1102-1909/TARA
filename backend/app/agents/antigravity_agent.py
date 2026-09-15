"""Antigravity SDK Agent Adapter for Reading and Writing Code.

Utilizes google-antigravity SDK to spawn autonomous agents equipped with
builtin file tools (CREATE_FILE, VIEW_FILE, EDIT_FILE, LIST_DIR) for direct
codebase inspection and modification.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

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


def create_antigravity_agent_config(
    system_instructions: Optional[str] = None,
    workspace_path: Optional[str] = None,
    model_name: Optional[str] = None,
    enabled_tools: Optional[List[Any]] = None,
) -> Any:
    """Builds a LocalAgentConfig for code generation, inspection, and editing."""
    if not ANTIGRAVITY_AVAILABLE:
        raise RuntimeError("google-antigravity is not installed. Run: pip install google-antigravity")

    instructions = system_instructions or (
        "You are TARA's Antigravity Autonomous Software Engineer. "
        "You inspect, read, write, and refactor codebases using your built-in file tools."
    )

    workspace = workspace_path or str(settings.storage_dir)

    tools = enabled_tools or [
        BuiltinTools.VIEW_FILE,
        BuiltinTools.CREATE_FILE,
        BuiltinTools.EDIT_FILE,
        BuiltinTools.LIST_DIR,
        BuiltinTools.FIND_FILE,
    ]

    capabilities = CapabilitiesConfig(
        enabled_tools=tools,
    )

    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY", "")

    config_kwargs: Dict[str, Any] = {
        "system_instructions": instructions,
        "capabilities": capabilities,
        "workspaces": [workspace],
    }

    if api_key:
        config_kwargs["api_key"] = api_key

    return LocalAgentConfig(**config_kwargs)
