"""``policy: {numerals: identifier-aware}`` (2.3.1): the digits of a name are not a number.

Study 20 had to pin a fake alias, ``gsm8k_name_numeral: 8``, because the numbers law
read the ``8`` of ``GSM8K`` as a quantity. The knob is opt-in, so every shipped
study is judged exactly as before.
"""

from __future__ import annotations

from kleinlib.claims import glued_to_a_name, text_numerals
from kleinlib.contract import _policy_problems, policy
from kleinlib.numbers import extract_literals


def test_the_literal_law_is_unchanged_by_default() -> None:
    assert text_numerals("GSM8K scored 0.97 on qwen2") == [8.0, 0.97, 2.0]
    assert [lit.value for lit in extract_literals("GSM8K scored 0.97 on qwen2\n")] == [8.0, 0.97, 2.0]


def test_identifier_aware_skips_digits_glued_to_letters_only() -> None:
    text = "GSM8K scored 0.97 on qwen2; depth-2 trees, 60k images, A003022 row"
    assert text_numerals(text, identifier_aware=True) == [0.97, 2.0, 60.0]
    values = [lit.value for lit in extract_literals(text + "\n", identifier_aware=True)]
    assert values == [0.97, 2.0, 60.0]
    assert glued_to_a_name("GSM8K", 3) and not glued_to_a_name("depth-2", 6)


def test_the_policy_key_validates_and_defaults_to_literal() -> None:
    assert policy({}, "numerals") == "literal"
    assert policy({"policy": {"numerals": "identifier-aware"}}, "numerals") == "identifier-aware"
    assert _policy_problems({"numerals": "identifier-aware"}) == []
    assert _policy_problems({"numerals": "loose"})


def test_claims_verify_honours_the_policy(tmp_path) -> None:
    """End to end on a lock: a claim naming GSM8K needs no alias for 8 once opted in."""
    from kleinlib.claims import _check_claim_sentences

    lock = {
        "schema": 2,
        "claims": {"C1": {"claim": "On GSM8K the gain was 0.01.", "numbers": ["gain"]}},
    }
    numbers = {"gain": {"value": 0.01}}
    literal = _check_claim_sentences(lock, 2, numbers)
    aware = _check_claim_sentences(lock, 2, numbers, identifier_aware=True)
    assert any("8" in str(problem) for problem in literal), literal
    assert not [problem for problem in aware if "quotes" in str(problem)], aware
