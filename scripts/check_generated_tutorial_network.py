#!/usr/bin/env python3
"""Build a fresh tutorial and prove Chrome starts zero HTTP(S) requests.

This check deliberately generates a temporary artifact.  It never treats the
shipped v0.1 reports as evidence for the v0.2 CSP contract.  Chrome's netlog is
read at the ``URL_REQUEST_START_JOB`` boundary, so a blocked or failed DNS lookup
cannot be mistaken for zero attempted network requests.
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from kleinlib.scaffold import scaffold_study
from kleinlib.workflow import load_contract, validate_contract

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILDER = REPO_ROOT / ".claude" / "skills" / "klein" / "scripts" / "build_tutorial.py"
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)
SECTION_NAMES = (
    "01-question.html",
    "02-method.html",
    "03-data.html",
    "04-journey.html",
    "05-findings.html",
    "06-coding-advice.html",
    "07-next-steps.html",
)


def find_chrome(explicit: str | None = None) -> str:
    candidates = [
        explicit,
        shutil.which("google-chrome"),
        shutil.which("google-chrome-stable"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise FileNotFoundError("Chrome/Chromium not found; pass --chrome /path/to/browser")


def build_fresh_tutorial(root: Path) -> Path:
    """Generate the minimal complete v2 tutorial fixture under *root*."""
    study = scaffold_study(
        root,
        "99-csp-browser-fixture",
        goal="Prove a generated tutorial needs no network",
        domain="test",
        target="y",
        task_type="classification",
        method_depth="brief",
        family="linear",
        metric_name="val_auc",
        metric_goal="higher",
        data_source="csv:fixture.csv",
        data_path="data/prepared.csv",
        max_run_seconds=30,
    )
    for filename in ("study.yaml", "program.md", "research_plan.md"):
        path = study / filename
        text = path.read_text(encoding="utf-8")
        replacements = {
            "{{RQ1_QUESTION}}": "Can an offline tutorial render without a request?",
            "{{RQ1_PRIOR}}": "yes",
            "{{LEVER_1}}": "restrictive CSP",
            "{{DELTA_1}}": "zero HTTP(S) requests",
        }
        for placeholder, value in replacements.items():
            text = text.replace(placeholder, value)
        path.write_text(text, encoding="utf-8")
    (study / "data").mkdir()
    (study / "data" / "prepared.csv").write_text("x,y\n0,0\n1,1\n", encoding="utf-8")
    contract_problems = validate_contract(load_contract(study), study)
    if contract_problems:
        raise RuntimeError("generated v2 fixture is invalid: " + "; ".join(contract_problems))
    sections = study / "report" / "sections"
    sections.mkdir()
    for index, name in enumerate(SECTION_NAMES, start=1):
        marker = "\n<!--LEDGER-->" if index == 4 else ""
        figure = (
            '\n<img data-fig="figures/one-pixel.png" alt="one pixel fixture">'
            if index == 3
            else ""
        )
        (sections / name).write_text(
            f"<h2>Section {index}</h2><p>Generated browser-isolation fixture.</p>{marker}{figure}",
            encoding="utf-8",
        )
    (study / "figures" / "one-pixel.png").write_bytes(PNG_1PX)
    (study / "results.tsv").write_text(
        "experiment\ttrack\tprimary_metric\tstatus\tcommit\tdescription\n"
        "E0001\tprimary\t1.0\tkeep\tabcdef0\tbrowser fixture\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(BUILDER), str(study), "--title", "CSP browser fixture"],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"tutorial builder failed ({result.returncode}):\n{result.stdout}{result.stderr}"
        )
    page = study / "report" / "index.html"
    if not page.is_file():
        raise RuntimeError("tutorial builder reported success without report/index.html")
    return page


def _event_type_id(payload: dict[str, Any], name: str) -> int | str:
    event_types = payload.get("constants", {}).get("logEventTypes", {})
    if name not in event_types:
        raise ValueError(f"Chrome netlog does not define {name}")
    return event_types[name]


def started_http_urls(payload: dict[str, Any]) -> list[str]:
    """Return HTTP(S) URLs that crossed Chrome's request-start boundary."""
    request_start = _event_type_id(payload, "URL_REQUEST_START_JOB")
    urls: list[str] = []
    for event in payload.get("events", []):
        if event.get("type") != request_start:
            continue
        url = event.get("params", {}).get("url")
        if isinstance(url, str) and url.lower().startswith(("http://", "https://")):
            urls.append(url)
    return urls


def check_in_chrome(chrome: str, page: Path, work_dir: Path) -> None:
    netlog = work_dir / "chrome-netlog.json"
    profile = work_dir / "chrome-profile"
    command = [
        chrome,
        "--headless=new",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-default-apps",
        "--disable-dev-shm-usage",
        "--disable-domain-reliability",
        "--disable-gpu",
        "--disable-sync",
        "--metrics-recording-only",
        "--no-default-browser-check",
        "--no-first-run",
        "--safebrowsing-disable-auto-update",
        "--disable-features=AutofillServerCommunication,CertificateTransparencyComponentUpdater,MediaRouter,OptimizationHints",
        f"--user-data-dir={profile}",
        f"--log-net-log={netlog}",
        "--net-log-capture-mode=Everything",
        "--dump-dom",
        page.resolve().as_uri(),
    ]
    result = subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Chrome failed ({result.returncode}):\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
        )
    if 'id="next-steps"' not in result.stdout:
        raise RuntimeError("Chrome did not render the generated tutorial's final section")
    if not netlog.is_file():
        raise RuntimeError("Chrome exited without writing its requested netlog")
    payload = json.loads(netlog.read_text(encoding="utf-8"))
    urls = started_http_urls(payload)
    if urls:
        rendered = "\n".join(f"  - {url}" for url in urls)
        raise RuntimeError(f"generated tutorial started HTTP(S) requests:\n{rendered}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chrome", help="Chrome/Chromium executable (auto-detected by default)")
    parser.add_argument(
        "--evidence",
        type=Path,
        help="optional JSON path for the zero-request CI evidence record",
    )
    args = parser.parse_args(argv)
    try:
        chrome = find_chrome(args.chrome)
        with tempfile.TemporaryDirectory(prefix="klein-tutorial-browser-") as temp:
            root = Path(temp)
            page = build_fresh_tutorial(root)
            check_in_chrome(chrome, page, root)
    except (FileNotFoundError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"[tutorial-browser] FAIL: {exc}", file=sys.stderr)
        return 1
    if args.evidence:
        args.evidence.write_text(
            json.dumps(
                {
                    "artifact_kind": "fresh-generated-v2-tutorial",
                    "browser": chrome,
                    "http_requests_started": 0,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    print("[tutorial-browser] PASS: fresh generated tutorial started 0 HTTP(S) requests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
