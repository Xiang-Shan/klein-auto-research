"""Repository-wide pytest configuration.

The suites build thousands of throwaway git repositories and commit in each. Under
a global ``commit.gpgsign = true`` every one of those commits would call the signer:
a prompt per commit on a laptop, and enough load to exhaust a signing agent on a
managed machine (it happened — the 3.0 release notes say how). Test repositories are
never evidence, so their commits are never signed. Set at import, before any test
or xdist worker starts a child process.
"""

from kleinlib.transaction import unsigned_git_environment

unsigned_git_environment()
