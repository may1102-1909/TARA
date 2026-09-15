"""Pytest configuration and compatibility shims for TARA backend tests."""

import sys
import types
import uuid

# Provide fallback for uuid_utils if OS policy blocks compiled C-extension .pyd
try:
    import uuid_utils
except ImportError:
    m = types.ModuleType("uuid_utils")
    m.UUID = uuid.UUID
    m.uuid4 = uuid.uuid4
    m.uuid7 = lambda: uuid.uuid4()

    m_compat = types.ModuleType("uuid_utils.compat")
    m_compat.uuid7 = lambda: uuid.uuid4()
    m_compat.UUID = uuid.UUID

    m.compat = m_compat
    sys.modules["uuid_utils"] = m
    sys.modules["uuid_utils.compat"] = m_compat
