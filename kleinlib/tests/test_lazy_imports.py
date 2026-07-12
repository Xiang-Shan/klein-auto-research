"""Public package imports remain compatible without eagerly loading heavy stacks."""

from __future__ import annotations

import json
import subprocess
import sys


def test_bare_import_is_lazy_and_public_submodule_access_still_works():
    code = """
import json
import sys
import kleinlib
before = {name: name in sys.modules for name in ('matplotlib', 'sklearn', 'torch')}
schema_name = kleinlib.schema.__name__
after = {name: name in sys.modules for name in ('matplotlib', 'sklearn', 'torch')}
print(json.dumps({'before': before, 'after': after, 'schema': schema_name,
                  'version': kleinlib.__version__}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    assert result["before"] == {"matplotlib": False, "sklearn": False, "torch": False}
    assert result["after"] == {"matplotlib": False, "sklearn": False, "torch": False}
    assert result["schema"] == "kleinlib.schema"
    assert result["version"] == "0.2.0"
