"""Exception types shared by the Klein workflow modules.

Extracted from :mod:`kleinlib.workflow` so every workflow module can raise the
same error without importing the coordinator (and without a cycle).
"""

from __future__ import annotations


class WorkflowError(RuntimeError):
    """A user-correctable workflow contract violation."""
