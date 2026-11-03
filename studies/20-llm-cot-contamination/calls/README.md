# AI-generated output — model call ledger

Every `*.jsonl.gz` file in this directory holds requests sent to a hosted language model and
the model's **raw, AI-generated replies**. The replies were produced by a machine, are not
written or edited by the study's authors, and may be wrong. They are kept as the evidence
the study's runs were judged on, so that the study re-verifies offline
(`klein replicate E#### --replay`, `references/model-calls-protocol.md`).

| Field | Value |
|---|---|
| Provider | Alibaba Cloud Model Studio (DashScope), OpenAI-compatible mode |
| Endpoint | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| Model | `qwen-flash-2025-07-28` (a dated snapshot) |
| Calls made | 2026-11-03 |
| Billing basis | a paid, pay-as-you-go API key; no free or trial quota was used |
| Format | gzip JSONL, one call per line: canonical request, reply, token usage; authorization headers scrubbed |
| Integrity | each shard's sha256 is pinned in the manifest of the run that wrote it (`runs/E####/manifest.json`) |

Use of these outputs is governed by the provider's terms
(<https://help.aliyun.com/en/model-studio/bailian-service-notes>), which require AI-generated
content to be clearly labelled — this file is that label. Do not remove it from a copy of
these shards.
