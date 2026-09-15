"""Convenience test runner that sets PYTEST_DISABLE_PLUGIN_AUTOLOAD to avoid Windows DLL blocks."""

import os
import sys
import pytest

if __name__ == "__main__":
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    args = sys.argv[1:] if len(sys.argv) > 1 else ["backend/tests", "-v"]
    sys.exit(pytest.main(args))
