"""The model-call ledger (Klein 2.3): expensive, nondeterministic calls made replayable.

A study whose entrypoint queries a language model (or any HTTP model endpoint, or a
slow stochastic simulator) cannot be re-verified from its run log alone: the
endpoint changes, the model is re-served under the same name, sampling is
nondeterministic, and every call costs money.  The ledger makes those calls
evidence:

* every call is keyed by the sha256 of its CANONICAL request (endpoint, model,
  parameters, sample index, namespace) and recorded — request (never the
  credentials), response, model id, token usage, latency — in gzip JSONL shards
  under the study's ``calls/`` directory, written deterministically so their
  hashes are stable;
* a later call with the same key is answered from the ledger (``calls_cached``);
  under ``KLEIN_OFFLINE=1`` ONLY the ledger answers, so a stranger re-runs a
  finished LLM study with no credentials and no network (``klein replicate
  --replay``);
* a budget guard (calls, tokens, dollars) raises :class:`BudgetExceeded` — the run
  crashes honestly and ``klein run-one`` still records what was spent;
* usage is merged into ``$KLEIN_RUN_DIR/usage.json`` for every exit status, and
  each shard is printed as an ``artifact:`` line so the notary pins it.

No Klein VERB ever imports this module (a test proves it): Klein's own commands
never call a model.  A study's entrypoint does, through here, by its own choice.
Standard library only (plus PyYAML, a core dependency, for :meth:`CallLedger.from_contract`).
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

__all__ = [
    "BudgetExceeded",
    "CacheMiss",
    "CallLedger",
    "canonical_json",
    "openai_chat",
    "request_key",
]

#: Shards rotate below this many UNCOMPRESSED bytes, so each compressed shard stays
#: far under the 10 MB per-file commit limit of the evidence transaction.
SHARD_LIMIT_BYTES = 8 * 1024 * 1024

#: Request fields never written to a shard.
_SECRET_FIELDS = frozenset({"api_key", "authorization", "headers"})


class BudgetExceeded(RuntimeError):
    """The run hit its declared call / token / dollar budget."""


class CacheMiss(RuntimeError):
    """``KLEIN_OFFLINE=1`` (or replay mode) and the ledger holds no answer for this request."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def request_key(endpoint: str, payload: Mapping[str, Any], *, sample: int = 0, namespace: str = "study") -> str:
    """The content address of one request: identical requests share one answer."""
    body = {
        "endpoint": endpoint,
        "payload": {k: v for k, v in payload.items() if k.lower() not in _SECRET_FIELDS},
        "sample": int(sample),
        "namespace": namespace,
    }
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def _api_key() -> str:
    for name in ("KLEIN_LLM_API_KEY", "DASHSCOPE_API_KEY", "OPENAI_API_KEY"):
        value = os.environ.get(name)
        if value:
            return value
    # A credential-injecting proxy replaces this placeholder; a real endpoint refuses it.
    return "sk-placeholder"


def openai_chat(base_url: str, payload: Mapping[str, Any], *, timeout: float = 180.0) -> dict[str, Any]:
    """POST an OpenAI-compatible ``/chat/completions`` request (urllib, no SDK)."""
    url = base_url.rstrip("/") + "/chat/completions"
    request = urllib.request.Request(
        url,
        data=canonical_json(dict(payload)).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_api_key()}",
            "User-Agent": "klein-auto-research/calls.py",
        },
        method="POST",
    )
    # A rate limit is a property of the provider's minute, not of the request: three
    # retries over 14 s let one 429 crash a 2,400-call run (study 24, E0002). Back off
    # exponentially to a 60 s cap over RETRY_ATTEMPTS tries (about three minutes in
    # all), honouring a numeric Retry-After header when the server sends one.
    delay = RETRY_BASE_SECONDS
    for attempt in range(RETRY_ATTEMPTS):
        last = attempt == RETRY_ATTEMPTS - 1
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and not last:
                time.sleep(_retry_after(exc, delay))
                delay = min(delay * 2, RETRY_CAP_SECONDS)
                continue
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"model endpoint returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            if not last:
                time.sleep(delay)
                delay = min(delay * 2, RETRY_CAP_SECONDS)
                continue
            raise RuntimeError(f"model endpoint unreachable: {exc.reason}") from exc
    raise RuntimeError("model endpoint: retries exhausted")  # pragma: no cover


#: Transport retry schedule (see :func:`openai_chat`).
RETRY_ATTEMPTS = 8
RETRY_BASE_SECONDS = 2.0
RETRY_CAP_SECONDS = 60.0


def _retry_after(exc: urllib.error.HTTPError, fallback: float) -> float:
    """Seconds to wait before the next attempt: a numeric Retry-After (capped), else *fallback*."""
    header = exc.headers.get("Retry-After") if exc.headers is not None else None
    try:
        return min(max(float(header), 0.0), 2 * RETRY_CAP_SECONDS) if header is not None else fallback
    except ValueError:
        return fallback


def _read_shard(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _write_shard(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    """Deterministic gzip (mtime 0, no filename) so a shard's hash depends on its records only."""
    payload = "".join(canonical_json(record) + "\n" for record in records).encode("utf-8")
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0, compresslevel=9) as handle:
        handle.write(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(buffer.getvalue())
    os.replace(tmp, path)


class CallLedger:
    """Record-and-replay for model calls; use as a context manager inside one run."""

    def __init__(
        self,
        directory: str | Path,
        *,
        run_id: str,
        base_url: str | None = None,
        model: str | None = None,
        budget_usd: float | None = None,
        budget_calls: int | None = None,
        budget_tokens: int | None = None,
        price_in_per_mtok: float | None = None,
        price_out_per_mtok: float | None = None,
        namespace: str = "study",
        offline: bool | None = None,
        smoke_response: str | None = None,
        max_workers: int = 8,
        transport: Callable[[str, Mapping[str, Any]], dict[str, Any]] = openai_chat,
    ) -> None:
        self.directory = Path(directory)
        self.run_id = run_id
        self.base_url = base_url
        self.model = model
        self.budget_usd = budget_usd
        self.budget_calls = budget_calls
        self.budget_tokens = budget_tokens
        self.price_in = price_in_per_mtok
        self.price_out = price_out_per_mtok
        self.namespace = os.environ.get("KLEIN_CALLS_NAMESPACE") or namespace
        self.offline = (os.environ.get("KLEIN_OFFLINE") == "1") if offline is None else offline
        self.smoke = os.environ.get("KLEIN_SMOKE") == "1"
        self.smoke_response = smoke_response
        self.max_workers = max(1, int(max_workers))
        self.transport = transport
        self._lock = threading.Lock()
        self._known: dict[str, dict[str, Any]] = {}
        self._new: list[dict[str, Any]] = []
        self._counts = {"calls": 0, "calls_cached": 0, "tokens_in": 0, "tokens_out": 0, "usd": 0.0}
        self._closed = False
        if self.directory.is_dir():
            for shard in sorted(self.directory.glob("*.jsonl.gz")):
                for record in _read_shard(shard):
                    self._known.setdefault(record["key"], record)

    # -- construction -----------------------------------------------------------

    @classmethod
    def from_contract(
        cls,
        study_dir: str | Path = ".",
        *,
        smoke_response: str | None = None,
        **overrides: Any,
    ) -> CallLedger:
        """Build the ledger the study's ``calls:`` block declares."""
        import yaml

        study = Path(study_dir)
        contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8")) or {}
        block = contract.get("calls") if isinstance(contract.get("calls"), Mapping) else {}
        price = block.get("price") if isinstance(block.get("price"), Mapping) else {}
        options: dict[str, Any] = {
            "run_id": os.environ.get("KLEIN_EXPERIMENT_ID") or "SMOKE",
            "base_url": block.get("base_url"),
            "model": block.get("model"),
            "budget_usd": block.get("budget_usd"),
            "budget_calls": block.get("budget_calls"),
            "budget_tokens": block.get("budget_tokens"),
            "price_in_per_mtok": price.get("input_per_mtok"),
            "price_out_per_mtok": price.get("output_per_mtok"),
            "namespace": str(block.get("namespace") or "study"),
            "max_workers": int(block.get("max_workers") or 8),
            "smoke_response": smoke_response,
        }
        options.update(overrides)
        return cls(study / str(block.get("dir") or "calls"), **options)

    # -- calling ----------------------------------------------------------------

    def chat(self, messages: Sequence[Mapping[str, Any]], *, model: str | None = None, sample: int = 0, **params: Any) -> str:
        """One chat completion's text (from the ledger when this exact request was made)."""
        payload = {"model": model or self.model, "messages": list(messages), **params}
        if payload["model"] is None:
            raise ValueError("no model: pass model= or declare calls.model in study.yaml")
        response = self.request("chat.completions", payload, sample=sample)
        try:
            return str(response["choices"][0]["message"]["content"] or "")
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"unexpected chat response shape: {str(response)[:300]}") from exc

    def chat_many(
        self,
        conversations: Sequence[Sequence[Mapping[str, Any]]],
        *,
        model: str | None = None,
        sample: int = 0,
        **params: Any,
    ) -> list[str]:
        """Many chats, ``max_workers`` at a time; results in input order."""
        if self.smoke or len(conversations) < 2 or self.max_workers == 1:
            return [self.chat(c, model=model, sample=sample, **params) for c in conversations]
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = [pool.submit(self.chat, c, model=model, sample=sample, **params) for c in conversations]
            return [future.result() for future in futures]

    def request(self, endpoint: str, payload: Mapping[str, Any], *, sample: int = 0) -> dict[str, Any]:
        """The generic call: any JSON request to ``endpoint`` (chat, embeddings, a model server)."""
        if self.smoke:
            if self.smoke_response is None:
                raise RuntimeError("KLEIN_SMOKE=1: no model is called; pass smoke_response= to the ledger")
            return {"choices": [{"message": {"content": self.smoke_response}}], "usage": {}}
        key = request_key(endpoint, payload, sample=sample, namespace=self.namespace)
        with self._lock:
            known = self._known.get(key)
            if known is not None:
                self._counts["calls_cached"] += 1
                return known["response"]
            if self.offline:
                raise CacheMiss(
                    f"KLEIN_OFFLINE=1 and the ledger holds no answer for request {key[:12]} "
                    f"({endpoint}, model={payload.get('model')!r}, sample={sample})"
                )
            self._check_budget()
        if self.base_url is None and self.transport is openai_chat:
            raise ValueError("no endpoint: declare calls.base_url in study.yaml")
        started = time.time()
        response = self.transport(self.base_url or "", payload)
        latency = time.time() - started
        usage = response.get("usage") if isinstance(response, Mapping) else None
        tokens_in = int((usage or {}).get("prompt_tokens") or 0)
        tokens_out = int((usage or {}).get("completion_tokens") or 0)
        cost = self._cost(tokens_in, tokens_out)
        record = {
            "key": key,
            "endpoint": endpoint,
            "base_url": self.base_url,
            "request": {k: v for k, v in payload.items() if k.lower() not in _SECRET_FIELDS},
            "sample": int(sample),
            "namespace": self.namespace,
            "response": response,
            "model_served": (response or {}).get("model") if isinstance(response, Mapping) else None,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "usd": cost,
            "latency_seconds": round(latency, 3),
            "run": self.run_id,
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with self._lock:
            self._known[key] = record
            self._new.append(record)
            self._counts["calls"] += 1
            self._counts["tokens_in"] += tokens_in
            self._counts["tokens_out"] += tokens_out
            self._counts["usd"] += cost
        return response

    # -- accounting ---------------------------------------------------------------

    def _cost(self, tokens_in: int, tokens_out: int) -> float:
        if self.price_in is None or self.price_out is None:
            return 0.0
        return tokens_in / 1e6 * float(self.price_in) + tokens_out / 1e6 * float(self.price_out)

    def _check_budget(self) -> None:
        counts = self._counts
        if self.budget_calls is not None and counts["calls"] >= int(self.budget_calls):
            raise BudgetExceeded(f"call budget reached: {counts['calls']} of {self.budget_calls}")
        tokens = counts["tokens_in"] + counts["tokens_out"]
        if self.budget_tokens is not None and tokens >= int(self.budget_tokens):
            raise BudgetExceeded(f"token budget reached: {tokens} of {self.budget_tokens}")
        if self.budget_usd is not None and counts["usd"] >= float(self.budget_usd):
            raise BudgetExceeded(f"dollar budget reached: {counts['usd']:.4f} of {self.budget_usd}")

    def summary(self) -> dict[str, float]:
        """The run's call accounting, for an evaluator's ``extra=``."""
        counts = dict(self._counts)
        return {
            "calls_total": float(counts["calls"] + counts["calls_cached"]),
            "calls_cached": float(counts["calls_cached"]),
            "tokens_in": float(counts["tokens_in"]),
            "tokens_out": float(counts["tokens_out"]),
            "cost_usd": round(float(counts["usd"]), 6),
        }

    # -- closing --------------------------------------------------------------------

    def close(self) -> list[Path]:
        """Write this run's new records as shards, merge usage, print artifact lines."""
        if self._closed or self.smoke:
            self._closed = True
            return []
        self._closed = True
        shards: list[Path] = []
        batch: list[dict[str, Any]] = []
        size = 0
        for record in sorted(self._new, key=lambda r: r["key"]):
            line = len(canonical_json(record)) + 1
            if batch and size + line > SHARD_LIMIT_BYTES:
                shards.append(self._flush(batch, len(shards)))
                batch, size = [], 0
            batch.append(record)
            size += line
        if batch:
            shards.append(self._flush(batch, len(shards)))
        self._merge_usage()
        study = Path.cwd()
        for shard in shards:
            try:
                rel = shard.resolve().relative_to(study.resolve()).as_posix()
            except ValueError:
                rel = shard.as_posix()
            print(f"artifact: {rel}")
        return shards

    def _flush(self, batch: Sequence[Mapping[str, Any]], index: int) -> Path:
        path = self.directory / f"{self.run_id}-{index:03d}.jsonl.gz"
        _write_shard(path, batch)
        return path

    def _merge_usage(self) -> None:
        run_dir = os.environ.get("KLEIN_RUN_DIR")
        if not run_dir:
            return
        path = Path(run_dir) / "usage.json"
        record: dict[str, Any] = {}
        if path.is_file():
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                record = {}
        for key, value in self._counts.items():
            record[key] = float(record.get(key, 0.0)) + float(value)
        record["tokens"] = float(record.get("tokens_in", 0.0)) + float(record.get("tokens_out", 0.0))
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, path)

    def __enter__(self) -> CallLedger:
        return self

    def __exit__(self, *exc: object) -> None:
        # Shards and usage are written even when the run is failing: the calls
        # were made and paid for, and they are evidence of what was asked.
        self.close()
