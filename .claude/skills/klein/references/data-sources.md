# Data sources — what `data.source` may name, and how a universal install resolves it

Klein runs from a fresh clone on any machine. Every dataset a study reads is therefore
named by a **source tag** the engine resolves the same way everywhere, pinned by a
hash when the bytes could change, and refused when the machine is offline and the tag
needs the network.

Role: the consultant at CONSULT, the data auditor at DATA, `klein doctor` any time.

## The tags

| tag | resolves to | offline | pin required | cache |
|---|---|---|---|---|
| `csv:<path>` / `parquet:<path>` | a file inside the study or repo (relative, POSIX) | yes | no — the DATA gate fingerprints the prepared artifact | — |
| `synthetic:<script>` | the named study-local script generates the prepared artifact; its sha256 joins the data fingerprint | yes | no | — |
| `bundled:<name>` | `datasets/<name>/` in this repository, and ONLY that; fails loudly if `$DATA_HUB` would have shadowed it | yes | no | — |
| `hub:<name>` | `$DATA_HUB`: a loader module (`loaders.python.hub.load_dataset`) or a plain directory `<root>/<name>/*.csv`; then the bundled copy; then an error | yes if present | `data.sha256` recommended | — |
| `sklearn:<loader>` | a `load_*` function shipped inside scikit-learn (an offline allowlist; `fetch_*` is refused) | yes | no | — |
| `openml:<id>` | an OpenML dataset by numeric id | **no** | `data.sha256` **mandatory**; an unpinned tag is refused and the digest printed | `data/raw/openml/<id>/<id>.csv` |
| `url:<https://…>` | an https download, streamed, digest verified before use | **no** | `data.sha256` **mandatory** | `data/raw/url/<sha256[:12]>/` |

Every resolution prints a `data source:` provenance line naming the path it used; the
line is in the run log and therefore in the evidence.

## The pinning rule

Anything that can change under you is pinned: OpenML and URL sources always, hub
sources when the hub is not this repository. The pin protects `prepare.py`'s input;
the DATA gate's fingerprint protects `prepare.py`'s output. Both exist because a
number computed on data nobody can re-obtain is not evidence.

## Offline and doctor

`KLEIN_OFFLINE=1` (set in CI) makes the network tags refuse before any request.
`klein doctor [--study <dir>] [--json]` reports, without fetching anything: python, uv
and git versions; which extras are installed; the tutorial renderer dependencies; the
device `pick_device` would choose; whether `$DATA_HUB` is set and importable; and,
with `--study`, whether that study's source tag resolves on this machine and what the
pin says.

## Bundling and licensing

A bundled dataset is a directory `datasets/<name>/` with the data file, a `README.md`
(origin, citation, transcription notes, how to regenerate) and a `DATA_LICENSE` (the
hurricane and insurance datasets are the pattern). Bundle only what may be
redistributed; for everything else use `openml:` or `url:` with a pin and document the
licence in the study's data card. Studies never write into `datasets/`.

## Reproducing a hub-era study elsewhere

Studies 05–09 name `hub:` sources; study 05's freMTPL2 is on OpenML (ids 41214 and
41215). To reproduce off-hub, replace the tag with `openml:41214` plus its digest — a
gate re-record with a reason, so the substitution is on the record.
