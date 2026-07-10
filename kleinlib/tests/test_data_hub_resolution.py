"""load_data_hub resolution chain: $DATA_HUB → repo-bundled datasets/ → error.

Why there is deliberately NO implicit home-directory default: on any machine that
happens to have a hub at the default location, every "DATA_HUB unset" check would
silently test that hub instead of the bundled copy. The chain therefore has exactly
two live branches and a loud failure, and each branch announces itself on stdout
("data source: ...") so run logs record their data provenance.
"""

from __future__ import annotations

import textwrap

import pandas as pd
import pytest

from kleinlib import data as klein_data


def test_bundled_branch_loads_repo_dataset(monkeypatch, capsys):
    """DATA_HUB unset → the repo-bundled insurance-claims csv.gz feeds the frame."""
    monkeypatch.delenv("DATA_HUB", raising=False)
    frame = klein_data.load_data_hub("insurance-claims")
    assert isinstance(frame, pd.DataFrame)
    assert len(frame) == 58592
    assert "claim_status" in frame.columns
    out = capsys.readouterr().out
    assert "data source: bundled" in out
    assert "insurance_claims.csv.gz" in out


def test_missing_everywhere_raises_actionable_error(monkeypatch):
    """No $DATA_HUB and no bundled dir → error names every recovery option."""
    monkeypatch.delenv("DATA_HUB", raising=False)
    with pytest.raises(FileNotFoundError) as excinfo:
        klein_data.load_data_hub("no-such-dataset")
    message = str(excinfo.value)
    assert "DATA_HUB" in message
    assert "datasets/" in message
    assert "csv:" in message  # the load_prepared escape hatch is offered


def test_hub_branch_wins_when_env_set(monkeypatch, tmp_path, capsys):
    """$DATA_HUB set → the hub loader is used even when a bundled copy exists."""
    hub = tmp_path / "hub"
    loader_pkg = hub / "loaders" / "python"
    loader_pkg.mkdir(parents=True)
    (hub / "loaders" / "__init__.py").write_text("")
    (loader_pkg / "__init__.py").write_text("")
    (loader_pkg / "hub.py").write_text(
        textwrap.dedent(
            """
            import pandas as pd

            def load_dataset(name):
                return pd.DataFrame({"from_hub": [name]})
            """
        )
    )
    monkeypatch.setenv("DATA_HUB", str(hub))
    frame = klein_data.load_data_hub("insurance-claims")
    assert list(frame.columns) == ["from_hub"]
    assert "data source: hub" in capsys.readouterr().out


def test_bundled_dir_is_anchored_on_kleinlib_not_cwd(monkeypatch, tmp_path):
    """cwd must not matter — CI runs prepare.py from $RUNNER_TEMP copies."""
    monkeypatch.delenv("DATA_HUB", raising=False)
    monkeypatch.chdir(tmp_path)
    frame = klein_data.load_data_hub("insurance-claims")
    assert len(frame) == 58592
