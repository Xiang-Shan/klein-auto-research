from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_generated_tutorial_network.py"


class _FakeClock:
    """Deterministic stand-in for the module's ``time`` — no real Chrome, no sleeping."""

    def __init__(self, values: list[float]) -> None:
        self._values = iter(values)

    def perf_counter(self) -> float:
        return next(self._values)


def _load_module():
    spec = importlib.util.spec_from_file_location("klein_tutorial_network", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["klein_tutorial_network"] = module
    spec.loader.exec_module(module)
    return module


def test_started_http_urls_uses_request_start_boundary() -> None:
    module = _load_module()
    payload = {
        "constants": {"logEventTypes": {"URL_REQUEST_START_JOB": 123}},
        "events": [
            {"type": 123, "params": {"url": "file:///tmp/report/index.html"}},
            {"type": 123, "params": {"url": "https://cdn.example.invalid/app.js"}},
            {"type": 999, "params": {"url": "https://not-a-request.example/"}},
            {"type": 123, "params": {"url": "HTTP://example.invalid/image.png"}},
        ],
    }
    assert module.started_http_urls(payload) == [
        "https://cdn.example.invalid/app.js",
        "HTTP://example.invalid/image.png",
    ]


def test_build_fresh_tutorial_has_csp_and_inline_figure(tmp_path: Path) -> None:
    module = _load_module()
    page = module.build_fresh_tutorial(tmp_path)
    text = page.read_text(encoding="utf-8")
    assert 'http-equiv="Content-Security-Policy"' in text
    assert "default-src 'none'" in text
    assert "connect-src 'none'" in text
    assert "data:image/png;base64," in text
    assert "metric: val_auc (primary)" in text
    assert "src=\"http" not in text
    assert "href=\"http" not in text


def test_check_in_chrome_times_the_page_load(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()

    def fake_run(command, **kwargs):
        (tmp_path / "chrome-netlog.json").write_text(
            json.dumps(
                {
                    "constants": {"logEventTypes": {"URL_REQUEST_START_JOB": 7}},
                    "events": [],
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout='<section id="next-steps">', stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module, "time", _FakeClock([100.0, 101.5]))
    load_seconds = module.check_in_chrome("/fake/chrome", tmp_path / "index.html", tmp_path)
    assert load_seconds == 1.5


def test_main_records_load_seconds_in_evidence(tmp_path: Path, monkeypatch, capsys) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "find_chrome", lambda explicit=None: "/fake/chrome")
    monkeypatch.setattr(module, "build_fresh_tutorial", lambda root: root / "report" / "index.html")
    monkeypatch.setattr(module, "check_in_chrome", lambda chrome, page, work_dir: 1.25)
    evidence = tmp_path / "evidence.json"
    assert module.main(["--evidence", str(evidence)]) == 0
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["http_requests_started"] == 0
    assert payload["load_seconds"] == 1.25
    out = capsys.readouterr().out
    assert "PASS" in out
    assert "1.25 s" in out


def test_main_fails_when_load_exceeds_budget(tmp_path: Path, monkeypatch, capsys) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "find_chrome", lambda explicit=None: "/fake/chrome")
    monkeypatch.setattr(module, "build_fresh_tutorial", lambda root: root / "report" / "index.html")
    monkeypatch.setattr(module, "check_in_chrome", lambda chrome, page, work_dir: 6.4)
    evidence = tmp_path / "evidence.json"
    assert module.main(["--evidence", str(evidence), "--max-load-seconds", "5.0"]) == 1
    err = capsys.readouterr().err
    assert "FAIL" in err
    assert "6.40 s" in err
    assert "--max-load-seconds budget of 5.00 s" in err
    assert not evidence.exists()
