"""The model-call ledger (Klein 2.3): record, replay offline, budget, scrub, pin, replicate."""

from __future__ import annotations

import gzip
import json
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from test_workflow_v3 import _fill, commit_all, git

from kleinlib.calls import BudgetExceeded, CacheMiss, CallLedger, request_key
from kleinlib.contract import load_contract, validate_contract
from kleinlib.scaffold import scaffold_study
from kleinlib.state import record_gate
from kleinlib.workflow import run_one


class _Handler(BaseHTTPRequestHandler):
    calls = 0
    seen_auth: list[str] = []

    def do_POST(self) -> None:  # noqa: N802 — http.server API
        type(self).calls += 1
        type(self).seen_auth.append(self.headers.get("Authorization", ""))
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        question = body["messages"][-1]["content"]
        answer = f"Answer: {len(question) % 7}"
        payload = {
            "model": body["model"] + "-served",
            "choices": [{"message": {"role": "assistant", "content": answer}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args) -> None:
        return


@pytest.fixture
def server(monkeypatch):
    # The server is local, not the network: an ambient KLEIN_OFFLINE=1 (CI sets it for
    # the whole job) would make the ledger cache-only and crash the entrypoint before
    # its first call. Tests that mean offline set it themselves (replay does).
    monkeypatch.delenv("KLEIN_OFFLINE", raising=False)
    _Handler.calls = 0
    _Handler.seen_auth = []
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/v1"
    httpd.shutdown()


def _http_transport(base_url, payload):
    # The production transport refuses non-https; tests talk to a local http server.
    import urllib.request

    request = urllib.request.Request(
        base_url + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer sk-test-secret"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        return json.loads(response.read())


def _ledger(tmp_path: Path, base_url: str, **kwargs) -> CallLedger:
    return CallLedger(
        tmp_path / "calls", run_id="E0001", base_url=base_url, model="m",
        transport=_http_transport, offline=False, **kwargs,
    )


def test_record_then_hit_then_offline_replay(tmp_path: Path, server: str, monkeypatch) -> None:
    monkeypatch.setenv("KLEIN_RUN_DIR", str(tmp_path / "run"))
    with _ledger(tmp_path, server, price_in_per_mtok=1.0, price_out_per_mtok=2.0) as ledger:
        first = ledger.chat([{"role": "user", "content": "q1"}])
        again = ledger.chat([{"role": "user", "content": "q1"}])
        other = ledger.chat([{"role": "user", "content": "q1"}], sample=1)
        assert first == again == other
        summary = ledger.summary()
    assert _Handler.calls == 2  # q1 sample 0 and sample 1; the repeat was a hit
    assert summary["calls_total"] == 3 and summary["calls_cached"] == 1
    assert summary["cost_usd"] == pytest.approx(2 * (10 + 10) / 1e6)
    usage = json.loads((tmp_path / "run" / "usage.json").read_text())
    assert usage["calls"] == 2 and usage["tokens"] == 30
    shard = tmp_path / "calls" / "E0001-000.jsonl.gz"
    records = [json.loads(line) for line in gzip.open(shard, "rt")]
    assert {r["model_served"] for r in records} == {"m-served"}
    assert "sk-test-secret" not in shard.read_bytes().decode("latin-1")
    # Offline: the ledger alone answers; a new question is a CacheMiss, not a network call.
    offline = CallLedger(tmp_path / "calls", run_id="E0002", base_url=server, model="m",
                         transport=_http_transport, offline=True)
    assert offline.chat([{"role": "user", "content": "q1"}]) == first
    with pytest.raises(CacheMiss):
        offline.chat([{"role": "user", "content": "never asked"}])
    assert _Handler.calls == 2


def test_shards_are_deterministic_and_keys_ignore_secrets(tmp_path: Path, server: str) -> None:
    with _ledger(tmp_path, server) as ledger:
        ledger.chat([{"role": "user", "content": "a"}])
    first = (tmp_path / "calls" / "E0001-000.jsonl.gz").read_bytes()
    record = json.loads(gzip.decompress(first).decode().splitlines()[0])
    record_again = dict(record)
    assert request_key("x", {"a": 1, "api_key": "s1"}) == request_key("x", {"a": 1, "api_key": "s2"})
    assert request_key("x", {"a": 1}, namespace="rep:E1@t") != request_key("x", {"a": 1})
    assert record_again["request"]["messages"][0]["content"] == "a"


def test_budget_guard_crashes_honestly(tmp_path: Path, server: str) -> None:
    with pytest.raises(BudgetExceeded):
        with _ledger(tmp_path, server, budget_calls=2) as ledger:
            for i in range(5):
                ledger.chat([{"role": "user", "content": f"q{i}"}])
    # The calls that WERE made are still pinned when the run fails.
    shard = tmp_path / "calls" / "E0001-000.jsonl.gz"
    assert len(gzip.decompress(shard.read_bytes()).decode().splitlines()) == 2


def test_smoke_mode_calls_nothing(tmp_path: Path, server: str, monkeypatch) -> None:
    monkeypatch.setenv("KLEIN_SMOKE", "1")
    with _ledger(tmp_path, server, smoke_response="Answer: 0") as ledger:
        assert ledger.chat([{"role": "user", "content": "x"}]) == "Answer: 0"
    assert _Handler.calls == 0 and not (tmp_path / "calls").exists()


def test_chat_many_preserves_order(tmp_path: Path, server: str) -> None:
    with _ledger(tmp_path, server, max_workers=4) as ledger:
        conversations = [[{"role": "user", "content": "x" * i}] for i in range(1, 9)]
        answers = ledger.chat_many(conversations)
    assert answers == [f"Answer: {i % 7}" for i in range(1, 9)]


def test_no_klein_verb_imports_the_ledger() -> None:
    code = (
        "import sys, kleinlib.cli, kleinlib.workflow, kleinlib.checks, kleinlib.replicate; "
        "print('kleinlib.calls' in sys.modules)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


# ------------------------------------------------------------------ in a study


def _calls_study(tmp_path: Path, base_url: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    study = scaffold_study(
        repo / "studies", "03-llm", goal="g", domain="d", target="y", task_type="scalar",
        method_depth="brief", family="f", metric_name="exact_match", metric_goal="higher",
        data_source="csv:fixture.csv", data_path="data/prepared/fixture.csv", max_run_seconds=60,
        schema_version=3, kind="predict", modality="text", profile="llm", audience="tests",
        split_kind="random",
    )
    _fill(study)
    path = study / "study.yaml"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"(\n  mutable: [^\n]*\n)", r"\1  printed: block\n", text, count=1)
    text = text.replace(
        "\nmax_run_seconds:",
        '\ncalls:\n  dir: calls\n  base_url: "https://example.invalid/v1"\n  model: "m"\n\nmax_run_seconds:',
        1,
    )
    path.write_text(text, encoding="utf-8")
    data = study / "data" / "prepared"
    data.mkdir(parents=True)
    (data / "fixture.csv").write_text("x,y\n" + "".join(f"{i},{i % 2}\n" for i in range(20)), encoding="utf-8")
    (study / "data_card.md").write_text("# Data card\n\n> **Decision:** **GO**\n", encoding="utf-8")
    (study / "method_card.md").write_text("# Method card\n\nBrief.\n", encoding="utf-8")
    (study / "transport.py").write_text(
        "import json, os, urllib.request\n"
        "def http(base_url, payload):\n"
        "    url = os.environ['TEST_LLM_URL'] + '/chat/completions'\n"
        "    req = urllib.request.Request(url, data=json.dumps(payload).encode(),\n"
        "        headers={'Content-Type': 'application/json'}, method='POST')\n"
        "    return json.loads(urllib.request.urlopen(req, timeout=10).read())\n",
        encoding="utf-8",
    )
    for gate in ("consult", "data", "method"):
        record_gate(study, gate, acknowledged_by="tester")
    commit_all(repo, "ready")
    git(repo, "switch", "-q", "-c", "experiments/03-llm")
    return study


def _entrypoint(crash_after: int | None = None) -> list[str]:
    crash = f"    if i == {crash_after}: raise SystemExit(3)\n" if crash_after is not None else ""
    script = (
        "import transport\n"
        "from kleinlib.calls import CallLedger\n"
        "with CallLedger.from_contract('.', transport=transport.http) as ledger:\n"
        "  scores = []\n"
        "  for i in range(4):\n"
        + crash.replace("    ", "    ")
        + "    scores.append(int(ledger.chat([{'role':'user','content':'q'+str(i)}]).endswith(str(len('q'+str(i)) % 7))))\n"
        "print('---'); print('primary_metric: %f' % (sum(scores)/len(scores)))\n"
        "print('metric_name: exact_match'); print('metric_goal: higher')\n"
    )
    return [sys.executable, "-c", script]


def test_a_crashed_run_still_pins_its_calls_and_records_usage(tmp_path: Path, server: str, monkeypatch) -> None:
    monkeypatch.setenv("TEST_LLM_URL", server)
    study = _calls_study(tmp_path, server)
    assert validate_contract(load_contract(study), study) == []
    train = study / "train.py"
    train.write_text(train.read_text() + "\nC = 1\n", encoding="utf-8")
    manifest = run_one(study, command=_entrypoint(crash_after=2), echo=False)
    assert manifest["disposition"] == "crash"
    shards = [rel for rel in manifest["artifacts"] if rel.startswith("calls/")]
    assert shards == ["calls/E0001-000.jsonl.gz"]
    assert manifest["artifacts"][shards[0]]["committed"] is True
    assert manifest["usage"]["calls"] == 2


def test_replay_reproduces_offline_and_requery_salts(tmp_path: Path, server: str, monkeypatch) -> None:
    from kleinlib.replicate import replicate_run

    monkeypatch.setenv("TEST_LLM_URL", server)
    study = _calls_study(tmp_path, server)
    train = study / "train.py"
    train.write_text(train.read_text() + "\nC = 1\n", encoding="utf-8")
    manifest = run_one(study, command=_entrypoint(), echo=False)
    assert manifest["disposition"] == "keep", manifest["decision_reason"]
    calls_before = _Handler.calls
    record = replicate_run(study, "E0001", replay=True, echo=False)
    assert record["mode"] == "replay" and record["reproduced"] is True, record.get("failure_reason")
    assert record["evidence_id"].startswith("replay:E0001@")
    assert _Handler.calls == calls_before  # offline: no request reached the server
    requery = replicate_run(study, "E0001", echo=False)
    assert requery["mode"] == "replicate" and requery["reproduced"] is True
    assert _Handler.calls == calls_before + 4  # salted: every call made afresh
    assert requery["calls_kept"]


def test_a_rate_limit_is_waited_out_not_crashed(monkeypatch) -> None:
    """Study 24's E0002 crashed on one HTTP 429 after 613 calls: the transport now backs
    off long enough for a per-minute limit, and honours Retry-After."""
    from kleinlib import calls

    class _Limited(BaseHTTPRequestHandler):
        hits = 0

        def do_POST(self) -> None:  # noqa: N802
            type(self).hits += 1
            self.rfile.read(int(self.headers["Content-Length"]))
            if type(self).hits <= 3:
                self.send_response(429)
                self.send_header("Retry-After", "7")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            data = json.dumps({"model": "m", "choices": [{"message": {"content": "ok"}}], "usage": {}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args) -> None:
            return

    httpd = HTTPServer(("127.0.0.1", 0), _Limited)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    waits: list[float] = []
    monkeypatch.setattr(calls.time, "sleep", waits.append)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")
    for name in ("NO_PROXY", "no_proxy"):  # never route the local fixture through a proxy
        monkeypatch.setenv(name, "127.0.0.1,localhost")
    try:
        out = calls.openai_chat(f"http://127.0.0.1:{httpd.server_address[1]}/v1", {"model": "m", "messages": []})
    finally:
        httpd.shutdown()
    assert out["choices"][0]["message"]["content"] == "ok"
    assert waits == [7.0, 7.0, 7.0]  # Retry-After honoured; three limits, then success


def test_a_dropped_connection_is_retried(monkeypatch) -> None:
    """Study 24's E0003 crashed on a ConnectionResetError raised while the RESPONSE was
    read — urllib raises it bare, not as URLError, so it escaped the retry loop."""
    from kleinlib import calls

    class _Flaky(BaseHTTPRequestHandler):
        hits = 0

        def do_POST(self) -> None:  # noqa: N802
            type(self).hits += 1
            self.rfile.read(int(self.headers["Content-Length"]))
            if type(self).hits == 1:
                self.close_connection = True
                self.wfile.flush()
                self.connection.shutdown(2)  # drop it before any status line
                return
            data = json.dumps({"model": "m", "choices": [{"message": {"content": "ok"}}], "usage": {}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args) -> None:
            return

    httpd = HTTPServer(("127.0.0.1", 0), _Flaky)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    waits: list[float] = []
    monkeypatch.setattr(calls.time, "sleep", waits.append)
    for name in ("NO_PROXY", "no_proxy"):
        monkeypatch.setenv(name, "127.0.0.1,localhost")
    try:
        out = calls.openai_chat(f"http://127.0.0.1:{httpd.server_address[1]}/v1", {"model": "m", "messages": []})
    finally:
        httpd.shutdown()
    assert out["choices"][0]["message"]["content"] == "ok"
    assert len(waits) == 1
