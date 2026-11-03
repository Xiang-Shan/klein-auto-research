# GSM8K — test split (bundled)

The 1,319 grade-school math word problems of GSM8K's test split, byte-for-byte as
published at `openai/grade-school-math` (`grade_school_math/data/test.jsonl`,
fetched 2026-11-03 from the repository's `master` branch).

- sha256 `3730d312f6e3440559ace48831e51066acaca737f6eabec99bccb9e4b3c39d14`, 749,738 bytes
- Licence: MIT, Copyright (c) 2021 OpenAI — `DATA_LICENSE` is the upstream file
- Citation: Cobbe, K., Kosaraju, V., Bavarian, M., et al. (2021). *Training Verifiers
  to Solve Math Word Problems.* arXiv:2110.14168.

Each line is `{"question": ..., "answer": ...}`; the gold final answer follows the
last `#### ` in `answer`. Bundled so study 20 re-verifies offline; referenced as
`bundled:gsm8k-test/test.jsonl`.
