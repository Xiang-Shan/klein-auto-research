# tinyshakespeare — bundled dataset

The "tiny Shakespeare" character-level text corpus — a concatenation of
Shakespeare's plays used as the canonical toy dataset for
`karpathy/char-rnn`'s character-level RNN examples, and later reused
verbatim as the `shakespeare_char` example in `karpathy/nanoGPT`.

| Fact | Value |
|---|---|
| File | `tinyshakespeare.txt.gz` (435,071 bytes gzip; 1,115,394 bytes decompressed) |
| Characters | 1,115,394 (pure ASCII; 1 byte = 1 character) |
| Vocabulary | 65 distinct characters (listed below) |
| Source | `karpathy/char-rnn`, `data/tinyshakespeare/input.txt` |
| Licence | Underlying text (the plays) is public domain; the char-rnn repository that packages this file is MIT — see [`DATA_LICENSE`](DATA_LICENSE) |
| Integrity | sha256 decompressed `86c4e6aa9db7c042ec79f339dcb96d42b0075e16b8fc2e86bf0ca57e2dc565ed`; sha256 gzip `d8b29e6338cb306019db992131ab249b4c5079dcfb9b5ad38be7b76121482ec9` |

- Origin: `https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt`,
  fetched 2026-09-02. Downloaded byte length matched the expected ~1,115,394
  bytes exactly — no truncation, no line-ending rewriting.
- What it is: a concatenation of Shakespeare plays, bundled by Andrej
  Karpathy as the example dataset for `char-rnn` (Lua/Torch char-RNN, 2015).
  `karpathy/nanoGPT`'s `data/shakespeare_char/prepare.py` downloads this
  exact same URL rather than re-hosting a copy; its own baked-in output
  comment reports `length of dataset in characters: 1115394` and
  `vocab size: 65` with the character set
  `` !$&',-.3:;?ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz`` (plus
  a leading newline) — identical to the values computed independently here,
  which cross-checks this bundled copy against nanoGPT's own numbers.
- Full character set (65), as produced by `sorted(set(text))` on the UTF-8
  decode: `\n`, ` `, `!`, `$`, `&`, `'`, `,`, `-`, `.`, `3`, `:`, `;`, `?`,
  `A`–`Z` (26), `a`–`z` (26). (Only the digit `3` appears anywhere in the
  corpus — e.g. in an act/scene reference — no other digits occur.)
- Produced by: `gzip -n` (deterministic — strips the original filename and
  mtime from the gzip header) applied to the raw, unmodified download;
  `gunzip -c tinyshakespeare.txt.gz | sha256` round-trips to the same
  decompressed hash as the original download, confirming byte-identical
  recovery.
- Character count and vocabulary size were computed by decoding the file as
  UTF-8 (the file is pure ASCII, so this equals the byte count) and taking
  `len(text)` and `len(set(text))`.
- Convention this bundle assumes downstream: a **contiguous-block** 90%
  development / 10% sealed final-test split (`data[:int(0.9*n)]` /
  `data[int(0.9*n):]`, not a random shuffle, since this is ordered
  natural-language text) — matching the same split nanoGPT's own
  `prepare.py` uses (1,003,854 train chars / 111,540 val chars).

## Provenance / licensing note

The underlying text — the plays of William Shakespeare (d. 1616) — is
centuries out of copyright and in the public domain worldwide. The specific
concatenation and packaging of this file is distributed by the
`karpathy/char-rnn` GitHub repository, whose `Readme.md` declares, in its
closing "License" section, the single word "MIT" (there is no separate
`LICENSE` file in that repository — GitHub's repository-metadata API
reports no auto-detected license for exactly that reason; the declaration
lives in the README text itself, confirmed here by fetching it directly).
No additional rights are asserted here; if you reuse this file, attribute
Andrej Karpathy's `char-rnn` (https://github.com/karpathy/char-rnn) for the
packaging, per its MIT license, and Shakespeare's public-domain plays for
the underlying text.
