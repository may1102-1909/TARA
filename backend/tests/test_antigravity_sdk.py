"""Unit tests for google-antigravity SDK integration in TARA."""

import pytest
from app.agents.antigravity_agent import (
    is_antigravity_installed,
    create_antigravity_agent_config,
)


def test_antigravity_sdk_installed():
    """Verify google-antigravity SDK is installed and accessible."""
    assert is_antigravity_installed() is True


def test_antigravity_agent_configuration():
    """Verify Antigravity Agent configuration is properly assembled with file tools."""
    from google.antigravity import BuiltinTools
    
    config = create_antigravity_agent_config(
        system_instructions="You are a code generator.",
        workspace_path="test_workspace",
    )
    assert config is not None
    assert config.system_instructions == "You are a code generator."
    assert any("test_workspace" in w for w in config.workspaces)
    
    # Check that file tools are enabled
    tools = config.capabilities.enabled_tools
    assert BuiltinTools.CREATE_FILE in tools
    assert BuiltinTools.VIEW_FILE in tools
    assert BuiltinTools.EDIT_FILE in tools
    assert BuiltinTools.LIST_DIR in tools
