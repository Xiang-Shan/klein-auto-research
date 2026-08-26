"""Shared fixtures for kleinlib tests.

``ready_study`` lives in ``test_workflow_v2``; re-exporting it here makes it
injectable by name in sibling modules without imports that shadow fixture
parameters (ruff F811).
"""

from test_workflow_v2 import ready_study  # noqa: F401
