from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_generated_tutorial_network.py"


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
