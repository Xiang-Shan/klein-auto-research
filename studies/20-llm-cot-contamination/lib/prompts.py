"""The FIXED instrument: two prompt arms, the decoding parameters, the scorer.

Library code, outside `entrypoint.mutable`: a cell chooses WHICH items to
measure, never how they are asked or how answers are graded. Changing anything
here changes the instrument for every registered prediction at once, so it is
written before the predictions are registered and then left alone.

The two arms differ in the instruction only:

* ``direct`` — "Answer with the final number only." — the model must do the
  arithmetic without writing it down;
* ``cot``    — "Solve the problem step by step, then give the final number after
  'Answer:'." — chain-of-thought (Wei et al. 2022).

Decoding is greedy (``temperature: 0``) with the provider's thinking mode OFF, so
the only reasoning a CoT response contains is the reasoning it prints.

The scorer: the number after the LAST ``Answer:`` / ``####`` marker; failing that,
the last number in the response. Thousands commas and an all-zero decimal tail
(``18.0``, ``45.00``) are normalized; anything else with a fractional part is not
an integer and scores 0. The comparison is integer equality with the gold.
"""

from __future__ import annotations

import re

#: The two arms. ``{question}`` is the item text, verbatim.
ARMS: dict[str, str] = {
    "direct": "Answer with the final number only.\n\nQuestion: {question}\nAnswer:",
    "cot": (
        "Solve the problem step by step, then give the final number after 'Answer:'."
        "\n\nQuestion: {question}"
    ),
}

#: Decoding parameters, identical for both arms. ``enable_thinking`` is the
#: DashScope (OpenAI-compatible) switch for Qwen's hidden reasoning mode.
PARAMS: dict[str, object] = {"temperature": 0.0, "max_tokens": 1024, "enable_thinking": False}


def messages(arm: str, question: str) -> list[dict[str, str]]:
    """The single-turn chat for one item under one arm."""
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}; choose one of {sorted(ARMS)}")
    return [{"role": "user", "content": ARMS[arm].format(question=question)}]


# --------------------------------------------------------------------------
# The scorer
# --------------------------------------------------------------------------

#: An answer marker: "Answer:" / "answer =" (any case) or GSM8K's "####".
_MARKER = re.compile(r"answer\s*[:=]|####", re.IGNORECASE)

#: A number: optional sign, thousands groups or plain digits, optional decimals.
#: Not preceded by a digit or a point (so "10-3" yields 10 and 3, never -3), and a
#: comma group only counts when exactly three digits follow it ("1,2345" is 1 and 2345).
_NUMBER = re.compile(r"(?<![\d.])-?(?:\d{1,3}(?:,\d{3})+(?!\d)|\d+)(?:\.\d+)?")


def _to_int(token: str) -> int | None:
    """``"1,210"`` -> 1210, ``"18.00"`` -> 18, ``"2.5"`` -> None (not an integer)."""
    text = token.replace(",", "")
    whole, _, fraction = text.partition(".")
    if fraction and fraction.strip("0"):
        return None
    return int(whole)


def extract(response: str | None) -> int | None:
    """The integer a response commits to, or None when it commits to none."""
    text = response or ""
    markers = list(_MARKER.finditer(text))
    if markers:
        after = _NUMBER.search(text, markers[-1].end())
        if after:
            return _to_int(after.group())
    numbers = _NUMBER.findall(text)
    return _to_int(numbers[-1]) if numbers else None


def exact_match(response: str | None, answer: int | str) -> int:
    """1 when the extracted integer equals the gold answer, else 0."""
    got = extract(response)
    return int(got is not None and got == int(str(answer).replace(",", "").strip()))
