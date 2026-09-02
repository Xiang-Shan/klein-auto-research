# Canonical diagrams

Three drawings that ARE the doctrine, rendered:

| File | Shows | Source |
|---|---|---|
| `lifecycle.png` | the seven-stage study lifecycle with its four gates (REFEREE is Gate 3) | `src/lifecycle.py` |
| `loop-transaction.png` | one candidate transaction under the loop contract (judgment / notary / receipts; keep / discard / measured / crash) | `src/loop_transaction.py` |
| `klein-bottle.png` | why "Klein" — the loop whose output feeds its own input | `src/klein_bottle.py` |

Regenerate with core deps only (matplotlib; DejaVu Sans fallback is built in):

```bash
uv run --no-sync python docs/diagrams/src/lifecycle.py en docs/diagrams/lifecycle.png
uv run --no-sync python docs/diagrams/src/loop_transaction.py en docs/diagrams/loop-transaction.png
uv run --no-sync python docs/diagrams/src/klein_bottle.py docs/diagrams/klein-bottle.png
```

`loop_transaction.py` derives its labels from AGENTS.md "The experiment loop
contract" and the SKILL.md Hard Rules — regenerate whenever the loop contract
changes, or the drawing lies. Colors come from `src/klein_palette.py` (a pinned
instance of the dataviz reference palette); do not hand-pick new ones.
