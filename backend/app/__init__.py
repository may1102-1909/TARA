import sys
import types
import uuid

# Safe fallback shim if uuid_utils compiled C-extension is blocked by OS policy
try:
    import uuid_utils  # noqa: F401
except (ImportError, OSError):
    _m = types.ModuleType("uuid_utils")
    _m.UUID = uuid.UUID
    _m.uuid4 = uuid.uuid4
    _m.uuid7 = lambda: uuid.uuid4()
    _compat = types.ModuleType("uuid_utils.compat")
    _compat.uuid7 = _m.uuid7
    sys.modules["uuid_utils"] = _m
    sys.modules["uuid_utils.compat"] = _compat

__version__ = "0.1.0"
