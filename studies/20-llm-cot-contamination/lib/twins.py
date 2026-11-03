"""GSM-Symbolic-style templates of GSM8K test problems, and their fresh twins.

Library code, NOT the mutable surface. A *template* is one GSM8K test question
with its numbers lifted into slots; a *twin* is the same question re-instantiated
with new numbers, solved exactly by the template's own rule. A model that has
memorized the original item (contamination) gains nothing on its twins, so the
original-vs-twin gap on the same templates is the contamination probe
(Mirzadeh et al. 2024, GSM-Symbolic).

Selection is auditable. Candidates are the indices of
``numpy.random.default_rng(SELECTION_SEED).permutation(1319)``, taken IN ORDER;
each is either templated (`TEMPLATES`) or skipped with a one-line reason
(`SKIPPED`), until `N_TEMPLATES` templates exist. :func:`validate` checks that
every candidate up to the last template source is accounted for exactly once.

Each template carries

* ``source_index`` — the 0-based line of `datasets/gsm8k-test/test.jsonl`;
* ``text``         — the ORIGINAL question as a format string; names stay fixed,
                     numbers become ``{slot}`` fields. Besides Python's own format
                     specs (``{x:,}``) two are added: ``{x:w}`` writes the number as
                     a word ("four") and ``{x:W}`` capitalizes it ("Twenty");
* ``original``     — the slot values of the original question;
* ``rule``         — the gold solution, computed with ``fractions.Fraction`` on the
                     slots. The helpers :func:`whole`, :func:`pos`, :func:`nonneg`
                     and :func:`need` raise :class:`IllPosed` when an intermediate
                     quantity stops making sense (a fractional count of boxes, a
                     negative remainder, a part larger than its whole);
* ``ranges``       — per slot ``(lo, hi, step)``, inside 0.5x-2x of the original;
                     the default is ``ceil(v/2) .. 2v`` on a grid one decade finer
                     than the original's trailing zeros (400 -> step 10), never
                     reaching 1 when the original is 2 or more.

A twin's slot values are drawn LOG-uniformly from the ranges (:func:`log_grid`:
on a full ``v/2 .. 2v`` range the median draw is the original value, so a twin's
numbers are not systematically larger than its original's; an answer built from
a small difference can still land above the original's more often than below,
because the rule must stay positive) and REJECTED unless the rule solves them to a positive
integer, they differ from the original's values, they are not degenerate
(:func:`degeneracies`: no slot falls to 0 or 1 where the original's was >= 2, no
two slots that differ in the original become equal — a 1/1 share, a 1x
multiplier, an answer printed in the question), and the answer differs from the
original's answer (a model that memorized "18" must not score on a twin whose
answer is also 18). Steps a rule could still trivialize through a derived
quantity (a 60-minute visit billed per hour, an empty third class, a one-day
doubling) are excluded by the template's own range or ``need``.

Nothing here calls a model, reads a run, or reads `program.md`.
"""

from __future__ import annotations

import bisect
import functools
import itertools
import json
import math
import os
import re
import string
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np

# --------------------------------------------------------------------------
# Declared seeds and sizes (the data card cites these; nothing else sets them)
# --------------------------------------------------------------------------

#: Number of GSM8K test items — the permutation's length.
GSM8K_TEST_N: int = 1319

#: The candidate order: ``default_rng(SELECTION_SEED).permutation(GSM8K_TEST_N)``.
SELECTION_SEED: int = 20261103

#: Templates wanted; selection stops at the candidate that completes this many.
N_TEMPLATES: int = 50

#: The development twin block (id prefix ``twA-``) and the SEALED one (``twC-``).
TWIN_DEV_SEED: int = 20261104
TWIN_SEALED_SEED: int = 20261105
TWINS_PER_TEMPLATE: int = 4

#: The validator's own sampling stream (never used for a block).
VALIDATE_SEED: int = 20261199
VALIDATE_SAMPLES: int = 200

#: Instances per template the validator's degeneracy scan draws (its own stream).
DEGENERACY_SAMPLES: int = 2000

#: A template must offer at least this many distinct well-posed twins inside its
#: ranges, so the two blocks (4 + 4) never nearly exhaust its instance space.
MIN_INSTANCES: int = 12

#: Rejection-sampling budget per twin before the sampler gives up loudly.
MAX_ATTEMPTS: int = 200_000


class IllPosed(ValueError):
    """These slot values do not make a well-posed problem (or a whole answer)."""


# --------------------------------------------------------------------------
# Well-posedness helpers used inside the rules
# --------------------------------------------------------------------------


def whole(x: Fraction | int) -> Fraction:
    """``x`` itself, which must be a whole number (a count, a whole-dollar amount)."""
    value = Fraction(x)
    if value.denominator != 1:
        raise IllPosed(f"{value} is not a whole number")
    return value


def pos(x: Fraction | int) -> Fraction:
    """``x`` itself, which must be strictly positive."""
    value = Fraction(x)
    if value <= 0:
        raise IllPosed(f"{value} is not positive")
    return value


def nonneg(x: Fraction | int) -> Fraction:
    """``x`` itself, which must not be negative."""
    value = Fraction(x)
    if value < 0:
        raise IllPosed(f"{value} is negative")
    return value


def need(condition: bool, why: str = "constraint violated") -> None:
    """Raise :class:`IllPosed` unless ``condition`` holds."""
    if not condition:
        raise IllPosed(why)


class Slots:
    """Read-only attribute access to slot values as exact ``Fraction``s."""

    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str, int]) -> None:
        self._values = {name: Fraction(int(value)) for name, value in values.items()}

    def __getattr__(self, name: str) -> Fraction:
        try:
            return self._values[name]
        except KeyError:
            raise AttributeError(f"no slot {name!r}") from None


# --------------------------------------------------------------------------
# Rendering: Python's format mini-language plus number words
# --------------------------------------------------------------------------

_SMALL = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
_TENS = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty", 6: "sixty", 7: "seventy",
         8: "eighty", 9: "ninety"}


def number_word(n: int) -> str:
    """0..99 as an English word, hyphenated the usual way ("twenty-four")."""
    n = int(n)
    if not 0 <= n < 100:
        raise ValueError(f"number_word covers 0..99, got {n}")
    if n < 20:
        return _SMALL[n]
    tens, ones = divmod(n, 10)
    return _TENS[tens] + ("" if ones == 0 else "-" + _SMALL[ones])


class _SlotFormatter(string.Formatter):
    """``str.format`` semantics, plus ``:w`` (word) and ``:W`` (capitalized word)."""

    def format_field(self, value: Any, format_spec: str) -> str:
        if format_spec == "w":
            return number_word(value)
        if format_spec == "W":
            word = number_word(value)
            return word[0].upper() + word[1:]
        return super().format_field(value, format_spec)


_FORMATTER = _SlotFormatter()


def slot_names(text: str) -> list[str]:
    """The ``{slot}`` names a template text uses, in order of first appearance."""
    names: list[str] = []
    for _literal, field, _spec, _conversion in string.Formatter().parse(text):
        if field and field not in names:
            names.append(field)
    return names


# --------------------------------------------------------------------------
# The template object
# --------------------------------------------------------------------------

Range = tuple[int, int, int]


def default_range(value: int) -> Range:
    """``ceil(v/2) .. 2v`` on a grid one decade finer than ``v``'s trailing zeros.

    The floor is 2 when ``v >= 2``: a slot of 1 would turn the original's
    multiplier, divisor or count into a no-op (``1/1``, "1 bag ... each").
    """
    v = int(value)
    if v <= 0:
        raise ValueError("default_range needs a positive original value")
    zeros = len(str(v)) - len(str(v).rstrip("0"))
    step = 10 ** max(0, zeros - 1)
    lo = max(min(v, 2), math.ceil(v / 2))
    lo = math.ceil(lo / step) * step
    return lo, 2 * v, step


@functools.cache
def log_grid(value: int, lo: int, hi: int, step: int) -> tuple[tuple[int, ...], tuple[float, ...]]:
    """The grid ``lo, lo+step, .., hi`` and its cumulative LOG-uniform probabilities.

    The continuous log-uniform law on ``[L, H]`` — the range widened by half a
    step on each side and clipped to ``[v/2, 2v]`` of the original value ``v`` —
    rounded to the nearest grid point: point ``x`` gets the log-length of its
    cell ``[x - step/2, x + step/2]`` inside ``[L, H]``. On a full ``v/2 .. 2v``
    range the median draw is ``v`` itself (the geometric mean of the bounds), so a
    twin's slot is as often below the original's as above; away from the bounds the
    mass is ``log(1 + step/x) ~ step/x``, the ``1/x`` law.
    """
    grid = [int(x) for x in range(int(lo), int(hi) + 1, int(step))]
    if not grid:
        raise ValueError(f"empty range {lo}..{hi} step {step}")
    low = max(lo - step / 2, value / 2)
    high = min(hi + step / 2, 2 * value)
    mass = [max(0.0, math.log(min(x + step / 2, high) / max(x - step / 2, low))) for x in grid]
    total = sum(mass)
    if total <= 0:
        raise ValueError(f"range {lo}..{hi} lies outside 0.5x-2x of {value}")
    cdf = list(itertools.accumulate(m / total for m in mass))
    cdf[-1] = 1.0
    return tuple(grid), tuple(cdf)


def log_uniform(rng: np.random.Generator, value: int, lo: int, hi: int, step: int = 1) -> int:
    """One draw from :func:`log_grid` (``value`` is the original the range is around)."""
    grid, cdf = log_grid(int(value), int(lo), int(hi), int(step))
    return grid[min(bisect.bisect_right(cdf, float(rng.random())), len(grid) - 1)]


def degeneracies(original: Mapping[str, int], values: Mapping[str, int]) -> list[str]:
    """Why ``values`` would make a step of ``original`` trivial (empty when they don't).

    A slot at 0 or 1 where the original's is 2 or more (a ``1/1`` share, a 1x
    multiplier, an empty quantity), or two slots equal where the original's differ
    (a ``d/d`` share, "4 times as many ... 4 times the number", an answer printed
    in the question).
    """
    found = [f"{name}={int(values[name])}" for name, v in original.items()
             if int(v) >= 2 and int(values[name]) <= 1]
    found += [f"{a}=={b}" for a, b in itertools.combinations(original, 2)
              if int(original[a]) != int(original[b]) and int(values[a]) == int(values[b])]
    return found


@dataclass(frozen=True)
class Template:
    """One GSM8K test question with its numbers lifted into slots."""

    tid: str
    source_index: int
    text: str
    original: Mapping[str, int]
    rule: Callable[[Slots], Fraction | int]
    ranges: Mapping[str, Range]
    drawer: Callable[[np.random.Generator], dict[str, int]] | None = None

    def render(self, values: Mapping[str, int]) -> str:
        """The question for these slot values (``text.format`` plus number words)."""
        return _FORMATTER.format(self.text, **{k: int(v) for k, v in values.items()})

    def solve(self, values: Mapping[str, int]) -> int:
        """The exact answer; raises :class:`IllPosed` unless it is a positive integer."""
        missing = set(self.original) - set(values)
        if missing:
            raise KeyError(f"{self.tid}: missing slots {sorted(missing)}")
        result = Fraction(self.rule(Slots(values)))
        if result.denominator != 1:
            raise IllPosed(f"{self.tid}: the answer {result} is not an integer")
        if result <= 0:
            raise IllPosed(f"{self.tid}: the answer {result} is not positive")
        return int(result)

    def draw(self, rng: np.random.Generator) -> dict[str, int]:
        """One raw LOG-uniform draw from the ranges (or the template's own drawer), unchecked."""
        if self.drawer is not None:
            return {name: int(value) for name, value in self.drawer(rng).items()}
        return {
            name: log_uniform(rng, int(value), *self.ranges[name])
            for name, value in self.original.items()
        }

    def sample(self, rng: np.random.Generator) -> dict[str, int]:
        """New slot values: well-posed, non-degenerate, integer answer, unlike the original."""
        original = {name: int(value) for name, value in self.original.items()}
        original_answer = self.solve(original)
        for _attempt in range(MAX_ATTEMPTS):
            values = self.draw(rng)
            if values == original or degeneracies(original, values):
                continue
            try:
                answer = self.solve(values)
            except IllPosed:
                continue
            if answer != original_answer:
                return values
        raise RuntimeError(f"{self.tid}: no well-posed twin in {MAX_ATTEMPTS} attempts")


TEMPLATES: list[Template] = []


def _template(
    source_index: int,
    text: str,
    original: Mapping[str, int],
    *,
    ranges: Mapping[str, tuple[int, int] | Range] | None = None,
    drawer: Callable[[np.random.Generator], dict[str, int]] | None = None,
) -> Callable[[Callable[[Slots], Fraction | int]], Callable[[Slots], Fraction | int]]:
    """Register the decorated rule as the template of GSM8K test line ``source_index``."""

    def register(rule: Callable[[Slots], Fraction | int]) -> Callable[[Slots], Fraction | int]:
        resolved: dict[str, Range] = {}
        for name, value in original.items():
            spec = (ranges or {}).get(name)
            if spec is None:
                resolved[name] = default_range(value)
            elif len(spec) == 2:
                resolved[name] = (int(spec[0]), int(spec[1]), 1)
            else:
                resolved[name] = (int(spec[0]), int(spec[1]), int(spec[2]))
        TEMPLATES.append(
            Template(
                tid=f"t{source_index:04d}",
                source_index=source_index,
                text=text,
                original=dict(original),
                rule=rule,
                ranges=resolved,
                drawer=drawer,
            )
        )
        return rule

    return register


# --------------------------------------------------------------------------
# The audited selection: candidates in permutation order, skipped with a reason
# --------------------------------------------------------------------------

#: Every candidate before the last template source that was NOT templated, and why.
SKIPPED: dict[int, str] = {
    365: "one slot (girls) with 9 well-posed values in 0.5x-2x: fewer than MIN_INSTANCES twins",
    1170: "total pints must be a multiple of 6 within 6..24: only 3 alternative instances",
    288: "gold treats 75-lb flagstones as divisible (26 fit per 2000-lb truck, so 80 need 4 "
         "trucks, not 3): ambiguous gold, no faithful well-posed twin",
    96: "a proper num/den with num >= 2 and hours a multiple of den other than den itself "
        "(1/den and den/den shares are degenerate): 6 instances with hours 5..12, 11 even over "
        "the full 5..18: fewer than MIN_INSTANCES twins",
    426: "whole-dollar soup and cake prices allow only 5 alternatives within 0.5x-2x",
    1149: "fish 2..6 x $1..2 of food a day gives 9 alternatives: fewer than MIN_INSTANCES twins",
    1: "blue bolts must be even within 1..4: a single alternative instance (4)",
}


@_template(
    906,
    "Tim has a box with {blue} blue shoe boxes and {red} red shoe boxes. If he uses {used} blue "
    "shoeboxes and 1/{den} red of his shoeboxes to go fishing, how many red and blue shoe boxes "
    "are left in Tim's box?",
    {"blue": 7, "red": 9, "used": 3, "den": 3},
)
def _t0906(v: Slots) -> Fraction:
    blue_left = pos(v.blue - v.used)
    red_used = whole(v.red / v.den)  # a 1/den share of the red boxes is whole boxes
    return blue_left + v.red - red_used


@_template(
    171,
    "Jake is walking through the Museum of Entomology. He sees {spiders} spiders with 8 legs each, "
    "{insects} insects with 6 legs each, and {mutants} rare mutant invertebrates with {mlegs} legs "
    "each. How many legs does Jake see total?",
    {"spiders": 80, "insects": 90, "mutants": 3, "mlegs": 10},
)
def _t0171(v: Slots) -> Fraction:
    # Spider and insect leg counts are facts, so they stay fixed; the mutants' are free.
    return 8 * v.spiders + 6 * v.insects + v.mutants * v.mlegs


@_template(
    585,
    "Tabitha agreed to pay John and Jill ${rate} an hour to help clean out her attic and "
    "basement.  Jill worked {sat} hours on Saturday and 1 hour on Sunday.  John worked twice as "
    "long as Jill on Saturday and {mult:w} times as long as Jill on Sunday.  How much more money "
    "did John earn compared to Jill?",
    {"rate": 10, "sat": 2, "mult": 3},
    ranges={"sat": (2, 4)},  # "1 hours" would not read; Sunday's single hour stays fixed
)
def _t0585(v: Slots) -> Fraction:
    jill = v.sat + 1
    john = 2 * v.sat + v.mult * 1
    return v.rate * pos(john - jill)


@_template(
    811,
    "Felix notices that kids in the neighborhood are always getting things stuck in trees. Since "
    "he is an expert tree climber, he decided to start charging kids to get their stuff out. He "
    "charges based on how high he has to climb. Every branch he has to climb up costs $.{cents}. "
    "During the week he made ${total}. On average, how many branches did he climb per day?",
    {"cents": 25, "total": 105},
    ranges={"cents": (15, 50, 5)},  # two-digit cents keep the "$.25" spelling
)
def _t0811(v: Slots) -> Fraction:
    branches = whole(v.total * 100 / v.cents)
    return whole(branches / 7)  # a week has 7 days


@_template(
    254,
    "Shelly's 3 kids spent all day at the water park.  Mitchel went down the water slide "
    "{mitchel} times.  Anne went down the slide {pct}% less than Mitchel and Robert went down "
    "{mult} times as much as Anne.  How many times did Robert go down the water slide?",
    {"mitchel": 30, "pct": 30, "mult": 4},
)
def _t0254(v: Slots) -> Fraction:
    need(v.pct < 100, "a reduction of 100% or more")
    anne = whole(v.mitchel * (100 - v.pct) / 100)
    return v.mult * anne


@_template(
    1126,
    "Alfie, the albatross, flies {daily} kilometers every day.  If the circumference of the earth "
    "is {circ:,} kilometers, how many days will it take Alfie to fly a distance equal to half of "
    "the way around the earth?",
    {"daily": 400, "circ": 40000},
    # The circumference is a stated premise ("If ..."), so it is a slot like any other.
)
def _t1126(v: Slots) -> Fraction:
    half = whole(v.circ / 2)
    return whole(half / v.daily)


@_template(
    1069,
    "Mr Hezekiah had {trucks} trucks from his store supplying fertiliser to different farmers in "
    "his hometown dispatched for delivery on a particular day. Each truck was carrying {tons} tons "
    "of fertiliser packed in bags. Two hours after the trucks had departed for delivery, Mr "
    "Hezekiah got the news that a quarter of the number of lorries dispatched for delivery had "
    "mechanical failures on the road and could not deliver the fertilisers to the farmers. "
    "Calculate the total number of tons of fertiliser that reached the farmers that day?",
    {"trucks": 20, "tons": 20},
)
def _t1069(v: Slots) -> Fraction:
    failed = whole(v.trucks / 4)
    return (v.trucks - failed) * v.tons


@_template(
    938,
    "John earned {rate} dollars an hour and worked {hours} hours in the week.  If he spends {gas} "
    "dollars on gas and wants to deposit {bank} dollars in the bank, how many {pen} dollar pens "
    "can he buy after he buys {pencils} pencils that cost {pcost} dollars each?",
    {"rate": 50, "hours": 6, "gas": 50, "bank": 100, "pen": 25, "pencils": 5, "pcost": 10},
)
def _t0938(v: Slots) -> Fraction:
    left = pos(v.rate * v.hours - v.bank - v.gas - v.pencils * v.pcost)
    return whole(left / v.pen)  # the money left buys a whole number of pens exactly


@_template(
    1290,
    "A small sunflower has {doz} dozen seeds and a large sunflower has {pct}% more seeds than a "
    "small sunflower.  How many sunflower seeds are there altogether?",
    {"doz": 3, "pct": 50},
    ranges={"pct": (25, 99)},  # "100% more" is plain doubling: the percent step is gone
)
def _t1290(v: Slots) -> Fraction:
    small = 12 * v.doz
    more = whole(small * v.pct / 100)
    return small + (small + more)


@_template(
    487,
    "Uncle Ben has {horses:w} horses. Each horse can consume {lbs:w} pounds of oats per meal. He "
    "feeds his horses twice a day. If one bag contains {bag}-pounds of oats,  how many bags of "
    "oats does he need to fed his horses for {days:w} days?",
    {"horses": 4, "lbs": 5, "bag": 50, "days": 5},
)
def _t0487(v: Slots) -> Fraction:
    pounds = v.horses * v.lbs * 2 * v.days
    return whole(pounds / v.bag)


@_template(
    334,
    "Nick, Richard, Jason and DJ each have paintball guns. DJ has {dj} guns, Nick has {nick} guns, "
    "RJ has 1 gun and Richard has {rich} guns. If they were to share their guns equally, how many "
    "guns would each of them have?",
    {"dj": 8, "nick": 10, "rich": 5},
)
def _t0334(v: Slots) -> Fraction:
    # RJ's single gun stays fixed ("1 gun"); the gold shares among four people.
    return whole((v.dj + v.nick + 1 + v.rich) / 4)


@_template(
    704,
    "Gerald and Julia divided ${total} in the ratio {a}:{b}. If Gerald spent ${spent} on a book, "
    "how much money did he have left?",
    {"total": 100, "a": 3, "b": 2, "spent": 10},
)
def _t0704(v: Slots) -> Fraction:
    need(v.a != v.b and math.gcd(int(v.a), int(v.b)) == 1, "a ratio in lowest terms, unequal")
    share = whole(v.total * v.a / (v.a + v.b))
    return pos(share - v.spent)


@_template(
    976,
    "Sunny is selling gingerbread and apple pie for a fundraiser. On Saturday, he sold {g_sat} "
    "boxes of gingerbread and {fewer} fewer boxes of apple pie, than on Sunday. On Sunday, he sold "
    "{more} more boxes of gingerbread than on Saturday and {a_sun} boxes of apple pie. If the "
    "gingerbread cost ${pg} and the apple pie cost ${pa}, how much did Sunny earn for two days?",
    {"g_sat": 10, "fewer": 4, "more": 5, "a_sun": 15, "pg": 6, "pa": 15},
)
def _t0976(v: Slots) -> Fraction:
    gingerbread = v.g_sat + (v.g_sat + v.more)
    apple = v.a_sun + pos(v.a_sun - v.fewer)
    return gingerbread * v.pg + apple * v.pa


@_template(
    316,
    "Solomon bought {bought} marbles from his friend Johanna and added them to a store that had "
    "{store}. If his father also gave him {num}/{den} times as many marbles as he bought from "
    "Johanna, and each marble weighs {w}kgs, calculate the total weight of marbles Solomon has in "
    "the store.",
    {"bought": 20, "store": 50, "num": 2, "den": 5, "w": 2},
    ranges={"num": (2, 4), "den": (3, 10), "w": (2, 4)},  # "1/den times" drops the multiply
)
def _t0316(v: Slots) -> Fraction:
    need(v.num < v.den and math.gcd(int(v.num), int(v.den)) == 1, "a proper fraction")
    father = whole(v.bought * v.num / v.den)
    return (v.bought + v.store + father) * v.w


@_template(
    1088,
    "There are {periods} periods in the day for a normal student but John has to take {extra} "
    "extra classes.  Each class is {mins} minutes long.  He goes to class for 5 days a week.  He "
    "then spends 1/{den} of his weekly minutes each on Saturday and Sunday as extra learning "
    "time.  How many hours a week does he spend learning?",
    {"periods": 6, "extra": 2, "mins": 40, "den": 16},
    ranges={"periods": (4, 8), "extra": (2, 4), "mins": (20, 80, 5)},
)
def _t1088(v: Slots) -> Fraction:
    need((v.periods + v.extra) * v.mins <= 600, "more than ten hours of class a day")
    weekly = (v.periods + v.extra) * v.mins * 5
    weekend_day = whole(weekly / v.den)
    return whole((weekly + 2 * weekend_day) / 60)


@_template(
    596,
    "George needs to pay for dental work. He needs {n} implants. Each implant has a base price of "
    "${base}. For one of the implants, he wants a crown made of porcelain. That feature costs an "
    "extra ${extra}. He’s already put down a deposit of ${dep}. He makes ${rate} per hour at "
    "work. How many hours does he need to work before he has enough to pay for the dental work?",
    {"n": 2, "base": 2000, "extra": 500, "dep": 600, "rate": 15},
    ranges={"n": (2, 4), "base": (1000, 4000, 100)},
)
def _t0596(v: Slots) -> Fraction:
    owed = pos(v.n * v.base + v.extra - v.dep)
    return whole(owed / v.rate)


@_template(
    1260,
    "Jade bought a new cell phone with an incredible camera, so she spent all week taking "
    "pictures of her daily life. At the end of the week, she had taken {photos} photos. She wants "
    "to upload all her photos on her Instagram. If she uploads {per} photos in one batch and she "
    "uploads {batches} batches each day, how many days will she need to upload all of her photos?",
    {"photos": 210, "per": 7, "batches": 6},
)
def _t1260(v: Slots) -> Fraction:
    n_batches = whole(v.photos / v.per)
    return whole(n_batches / v.batches)


@_template(
    1086,
    "Marcel runs a bicycle store. His main products are three types of bikes: MTB, BMX, and "
    "Trekking. The price of one MTB is ${mtb}, BMX is half the price of an MTB, and a Trekking "
    "bike is ${trek}. In one month, Marcel sold a total of {total} bikes among the types listed. "
    "Half of them were Trekking bikes, and {pct}% were BMX bikes. The rest of the sold bikes were "
    "MTB type. How much did Marcel earn from selling bicycles during that month?",
    {"mtb": 500, "trek": 450, "total": 300, "pct": 15},
)
def _t1086(v: Slots) -> Fraction:
    bmx_price = whole(v.mtb / 2)
    n_trek = whole(v.total / 2)
    n_bmx = whole(v.total * v.pct / 100)
    n_mtb = pos(v.total - n_trek - n_bmx)
    return n_trek * v.trek + n_bmx * bmx_price + n_mtb * v.mtb


@_template(
    702,
    "Gissela, Gordy, and Gary are truck drivers.  Gissela has a truck large enough to haul {a:,} "
    "pounds of gravel. Gordy's truck can haul {more:,} pounds more than Gissela's truck.  And "
    "when Gary brings his truck and joins Gissela and Gordy, the three trucks combined can haul a "
    "total of {total:,} pounds of gravel. How many pounds of gravel can Gary's truck carry?",
    {"a": 4000, "more": 800, "total": 11600},
    ranges={"more": (400, 1600, 100), "total": (5800, 23200, 100)},
)
def _t0702(v: Slots) -> Fraction:
    gordy = v.a + v.more
    return pos(v.total - v.a - gordy)


@_template(
    29,
    "Gloria is shoe shopping when she comes across a pair of boots that fit her shoe budget. "
    "However, she has to choose between the boots and two pairs of high heels that together cost "
    "{less:w} dollars less than the boots. If one pair of heels costs ${heel} and the other costs "
    "twice as much, how many dollars are the boots?",
    {"less": 5, "heel": 33},
)
def _t0029(v: Slots) -> Fraction:
    heels = v.heel + 2 * v.heel
    return heels + v.less


@_template(
    599,
    "A pet store currently has {dogs} dogs, {cats} cats, and {birds} birds. How many legs in total "
    "do the pets in the store have?",
    {"dogs": 5, "cats": 2, "birds": 10},
    ranges={"cats": (2, 4)},  # "1 cats" would not read
)
def _t0599(v: Slots) -> Fraction:
    return 4 * v.dogs + 4 * v.cats + 2 * v.birds


@_template(
    1183,
    "Two apples fell out of the tree, and one of them landed on Newton's head.  Newton picked up "
    "the two apples, put one in his pocket and threw the other apple into the tree, causing {m1} "
    "more apples to fall out of the tree.  Newton picked up these apples, put all but one in his "
    "pocket and threw the remaining one at the tree.  This caused another {m2} apples to fall out "
    "of the tree.  Newton picked up all of the remaining apples and went home to make a pie.  How "
    "many apples did he bring home?",
    {"m1": 5, "m2": 6},
)
def _t1183(v: Slots) -> Fraction:
    pocket = 1  # of the first two, one is kept and one thrown back
    pocket += pos(v.m1 - 1)  # all but one of the second fall
    return pocket + v.m2


@_template(
    610,
    "It costs ${cost} per meter to repave a street. Monica's street is {a} meters long. How much "
    "more does it cost to repave Lewis' street, which is {b} meters long?",
    {"cost": 194, "a": 150, "b": 490},
    ranges={"a": (80, 300, 10), "b": (250, 980, 10)},
)
def _t0610(v: Slots) -> Fraction:
    return v.cost * pos(v.b - v.a)


@_template(
    177,
    "Zaid spends 1/4 of his salary on rent, 1/3 on car fuel and donates half of the remaining "
    "amount to his favorite charity. He gives his daughter {daughter}$ to use for her weekly "
    "expenses and {wife}$ to his wife to budget for groceries and other household goods. If Zaid "
    "earns {salary}$ per month, how much money will he still have after all these expenses and "
    "donations?",
    {"daughter": 200, "wife": 700, "salary": 6000},
    ranges={"salary": (3000, 12000, 100)},
)
def _t0177(v: Slots) -> Fraction:
    rent = whole(v.salary / 4)
    fuel = whole(v.salary / 3)
    remaining = v.salary - rent - fuel
    donated = whole(remaining / 2)
    return pos(remaining - donated - v.daughter - v.wife)


@_template(
    1264,
    "Garrett is popping popcorn for a snack. As the pan of kernels heats up, the kernels start "
    "popping faster. {first:W} pop in the first 30 seconds of cooking, then {m2:w} times that "
    "amount in the next 30 seconds. The kernels increase to {m3:w} times the initial popping rate "
    "in the next thirty seconds, but in the final 30 seconds, the popping slows down to half the "
    "rate as the past 30 seconds. After Garrett takes the pan off the heat, a quarter of the "
    "number of kernels that popped in the final 30 seconds of cooking also pop from the residual "
    "heat. How many pieces of popcorn does Garrett have to eat?",
    {"first": 20, "m2": 3, "m3": 4},
)
def _t1264(v: Slots) -> Fraction:
    need(v.m3 > v.m2, "the rate must INCREASE in the third interval")
    second = v.m2 * v.first
    third = v.m3 * v.first
    final = whole(third / 2)
    residual = whole(final / 4)
    return v.first + second + third + final + residual


@_template(
    124,
    "Jennie is helping at her mom's office. She has a pile of {need} letters needing stamps, and a "
    "pile of letters already stamped. She puts stamps on one-third of the letters needing stamps. "
    "If there are now {now} letters in the pile of already-stamped letters, how many were in that "
    "pile when Jennie began?",
    {"need": 60, "now": 30},
)
def _t0124(v: Slots) -> Fraction:
    stamped = whole(v.need / 3)
    return pos(v.now - stamped)


@_template(
    514,
    "A house and a lot cost ${total:,}. If the house cost {m:w} times as much as the lot, how much "
    "did the house cost?",
    {"total": 120000, "m": 3},
    ranges={"total": (60000, 240000, 1000)},
)
def _t0514(v: Slots) -> Fraction:
    lot = whole(v.total / (v.m + 1))
    return v.m * lot


@_template(
    1046,
    "A team of {painters} painters worked on a mansion for {num}/{den}ths of a day every day for "
    "{weeks} weeks. How many hours of work did each painter put in?",
    {"painters": 4, "num": 3, "den": 8, "weeks": 3},
    ranges={"num": (2, 6), "den": (4, 16)},  # "1/8ths" would not read
)
def _t1046(v: Slots) -> Fraction:
    need(v.num < v.den and math.gcd(int(v.num), int(v.den)) == 1, "a proper fraction")
    hours_a_day = whole(24 * v.num / v.den)
    return hours_a_day * 7 * v.weeks


@_template(
    1062,
    "Hannah slips on a banana peel and breaks her arm. The doctor charges her ${cast} for the "
    "cast, ${rate}/hour for a {mins}-minute visit, ${pill}/pill for {pills} painkillers, and "
    "${park}/hour for a mandatory minimum of {hrs} hours of parking. How much does the doctor's "
    "visit cost total?",
    {"cast": 200, "rate": 300, "mins": 30, "pill": 4, "pills": 30, "park": 6, "hrs": 2},
    ranges={"mins": (15, 55, 5), "hrs": (2, 4)},  # a 60-minute visit bills rate x 1
)
def _t1062(v: Slots) -> Fraction:
    visit = whole(v.rate * v.mins / 60)
    return v.cast + visit + v.pill * v.pills + v.park * v.hrs


@_template(
    436,
    "Rory makes a cake that weighs {oz} ounces. She cuts into {pieces} pieces. Rory and her mom "
    "each have a piece. How much does the remaining cake weigh?",
    {"oz": 20, "pieces": 8},
)
def _t0436(v: Slots) -> Fraction:
    need(v.pieces >= 3, "two pieces are eaten")
    piece = v.oz / v.pieces  # a weight: fractional, as in the original (2.5 ounces)
    return v.oz - 2 * piece


@_template(
    1120,
    "John visits his parents twice a month.  It takes him {hours} hours to drive there at a speed "
    "of {speed} mph.  Considering the round trip, how many miles a month does he drive when "
    "visiting his parents?",
    {"hours": 2, "speed": 70},
    ranges={"hours": (2, 4), "speed": (35, 80, 5)},
)
def _t1120(v: Slots) -> Fraction:
    one_way = v.hours * v.speed
    return one_way * 2 * 2


@_template(
    250,
    "Each class in a school has {size} students. There are 3 classes. The school as a whole is 50% "
    "boys and 50% girls. The first class has {g1} girls. The second class has {g2} girls. How many "
    "boys are in the third class?",
    {"size": 20, "g1": 15, "g2": 12},
)
def _t0250(v: Slots) -> Fraction:
    need(v.g1 <= v.size and v.g2 <= v.size, "more girls than students in a class")
    girls = whole(3 * v.size / 2)
    third_girls = pos(girls - v.g1 - v.g2)  # no girls would make "boys" the class size
    return pos(v.size - third_girls)


def _beanstalk_days(start: Fraction, window: Fraction) -> int:
    height, days = start, 0
    while height <= window:
        need(height != window, "a height exactly at the window makes 'taller' a trap")
        height, days = height * 2, days + 1
    return days


@_template(
    593,
    "Mark plants a beanstalk below his second-story window, which is {window} feet off the ground. "
    "The beanstalk doubles its height every day. If the beanstalk starts out {start} feet tall, "
    "how many days will it take to be taller than Mark's window?",
    {"window": 20, "start": 4},
    ranges={"window": (12, 30)},
)
def _t0593(v: Slots) -> Fraction:
    need(v.start < v.window, "already taller than the window")
    days = _beanstalk_days(v.start, v.window)
    need(days >= 2, "a single doubling leaves no repeated step")
    return Fraction(days)


@_template(
    574,
    "A food truck only sells grilled cheeses.  They source their bread for ${bread}.00 a loaf and "
    "each loaf makes 10 sandwiches.  They spend ${cheese}.00 on different cheeses and condiments "
    "per 10 sandwiches.  If they sell 10 sandwiches for ${price}.00 each, what is their net "
    "profit?",
    {"bread": 3, "cheese": 30, "price": 7},
)
def _t0574(v: Slots) -> Fraction:
    return pos(10 * v.price - v.bread - v.cheese)


@_template(
    240,
    "James has {more} more candies than Robert. John has twice as many candies as Robert. If John "
    "has {john} candies, how many more candies does John have than James?",
    {"more": 6, "john": 54},
)
def _t0240(v: Slots) -> Fraction:
    robert = whole(v.john / 2)
    return pos(v.john - (robert + v.more))


@_template(
    1132,
    "Valerie earns ${val} per month, 1/{den} of what her brother earns. If their mother earns "
    "twice their combined salary, what's the total amount of money they all have together?",
    {"val": 5000, "den": 2},
    ranges={"val": (2500, 10000, 100)},
)
def _t1132(v: Slots) -> Fraction:
    combined = v.val + v.val * v.den
    return combined + 2 * combined


@_template(
    851,
    "James buys {pairs} pairs of shoes a month.  He spends ${spend} on shoes each year.  How much "
    "does he pay on average for each pair of shoes?",
    {"pairs": 2, "spend": 2640},
    ranges={"pairs": (2, 4)},
)
def _t0851(v: Slots) -> Fraction:
    return whole(v.spend / (12 * v.pairs))


@_template(
    1031,
    "Apple High School is holding graduation in their Fine Arts Center this year which has space "
    "for {cap} people.  After accounting for {grads} seats for graduates and {fac} seats for "
    "faculty attending, how many tickets would each graduate receive to give to their friends and "
    "family if the tickets are split equally?",
    {"cap": 6000, "grads": 950, "fac": 300},
    ranges={"grads": (480, 1900, 10)},
)
def _t1031(v: Slots) -> Fraction:
    rest = pos(v.cap - v.grads - v.fac)
    return whole(rest / v.grads)


@_template(
    772,
    "Tatiana is deciding how much of her weekend she wants to spend playing soccer. She has {sat} "
    "hours on Saturday and {sun} hours on Sunday. She is dividing her time between soccer, video "
    "games, and reading. If she reads for {read} hours and plays video games for 1/{den} of the "
    "remaining time, what percentage of her weekend does she spend playing soccer?",
    {"sat": 7, "sun": 5, "read": 3, "den": 3},
)
def _t0772(v: Slots) -> Fraction:
    weekend = v.sat + v.sun
    remaining = pos(weekend - v.read)
    games = whole(remaining / v.den)
    soccer = pos(remaining - games)
    return soccer * 100 / weekend


@_template(
    466,
    "Becky bought {nb} apples for {cb} cents each and received a ${db} discount. Kelly bought {nk} "
    "apples for {ck} cents each and received a {pk} percent discount. How much more did Kelly pay "
    "than Becky?",
    {"nb": 20, "cb": 45, "db": 1, "nk": 20, "ck": 50, "pk": 10},
    # Prices and the discount on a 5-step grid, like the original's 45c / 50c / 10%.
    ranges={"cb": (25, 90, 5), "ck": (25, 95, 5), "pk": (5, 20, 5)},  # never "100 cents"
)
def _t0466(v: Slots) -> Fraction:
    becky = pos(v.nb * v.cb / 100 - v.db)
    kelly = v.nk * v.ck / 100 * (100 - v.pk) / 100
    return pos(kelly - becky)


@_template(
    116,
    "Katy makes coffee using teaspoons of sugar and cups of water in the ratio of {a}:{b}. If she "
    "used a total of {total} teaspoons of sugar and cups of water, calculate the number of "
    "teaspoonfuls of sugar she used.",
    {"a": 7, "b": 13, "total": 120},
)
def _t0116(v: Slots) -> Fraction:
    need(v.a != v.b and math.gcd(int(v.a), int(v.b)) == 1, "a ratio in lowest terms, unequal")
    return whole(v.total * v.a / (v.a + v.b))


@_template(
    662,
    "Gus spent ${total}.00 at the grocery store.  He bought {bags} bag of chips for ${chips}.00 "
    "each, a bucket of fried chicken for ${chicken}.00 and a bottle of soda for ${soda}.00.  How "
    "much did the apple pie cost?",
    {"total": 20, "bags": 2, "chips": 2, "chicken": 8, "soda": 1},
)
def _t0662(v: Slots) -> Fraction:
    return pos(v.total - v.bags * v.chips - v.chicken - v.soda)


@_template(
    844,
    "Peter has twice as many socks as Jack and half times as many dishes as jack. Jack collected "
    "twice as many dishes as socks in the store. If jack collected {dishes} dishes, calculate the "
    "total number of socks and dishes they have together?",
    {"dishes": 60},
)
def _t0844(v: Slots) -> Fraction:
    jack_socks = whole(v.dishes / 2)
    peter_socks = 2 * jack_socks
    peter_dishes = whole(v.dishes / 2)
    return jack_socks + v.dishes + peter_socks + peter_dishes


def _draw_oven(rng: np.random.Generator) -> dict[str, int]:
    """Setting, integer percent error and answer first; the printed numbers follow.

    Independent draws of the three printed numbers would almost never be
    consistent with one percentage; drawing the latent percentage keeps the
    rejection loop short. Every printed number stays inside 0.5x-2x. The three
    latent values are drawn LOG-uniformly (:func:`log_uniform`) on their grids,
    around the original's 450, 4% and 500.
    """
    while True:
        setting = log_uniform(rng, 450, 300, 550, 25)  # 300 .. 550
        pct = log_uniform(rng, 4, 2, 8)  # the oven runs 2% .. 8% hot
        answer = log_uniform(rng, 500, 260, 560, 10)  # 260 .. 560
        if setting * (100 + pct) % 100 == 0 and answer * (100 + pct) % 100 == 0:
            return {
                "set": setting,
                "actual": setting * (100 + pct) // 100,
                "recipe": answer * (100 + pct) // 100,
            }


@_template(
    580,
    "Maggie's oven is malfunctioning. When she sets it to {set} the actual temperature is "
    "{actual}. If it's off by the same percentage for any recipe, what temperature should she set "
    "it at if her recipe calls for {recipe} degrees?",
    {"set": 450, "actual": 468, "recipe": 520},
    drawer=_draw_oven,
)
def _t0580(v: Slots) -> Fraction:
    need(v.actual != v.set, "the oven is not malfunctioning")
    return v.recipe * v.set / v.actual


@_template(
    1281,
    "Dexter has {pigs:w} pigs. Each one eats {lbs} pounds of feed, twice a day. If Dexter ordered "
    "{order} pounds of feed, how many pounds of feed is left after a week?",
    {"pigs": 5, "lbs": 4, "order": 300},
    ranges={"lbs": (2, 8)},
)
def _t1281(v: Slots) -> Fraction:
    eaten = v.pigs * v.lbs * 2 * 7  # twice a day, for a 7-day week
    return pos(v.order - eaten)


@_template(
    181,
    "Sandra, the florist around the corner, is very unhappy with Fred's incomplete order delivery. "
    "Sandra had ordered {m1:w} times as many red roses as white carnations. She also ordered "
    "{lilies} pink calla lilies, which were {m2:w} times the number of white carnations. Sandra "
    "has threatened to switch suppliers if the missing red roses are not delivered by 5 pm. To "
    "keep Sandra's business, how many red roses must Fred deliver by 5 pm?",
    {"m1": 4, "lilies": 200, "m2": 5},
)
def _t0181(v: Slots) -> Fraction:
    carnations = whole(v.lilies / v.m2)
    return v.m1 * carnations


@_template(
    618,
    "The school auditorium has {rows} rows of seats. There are {seats} seats in each row. "
    "One-fourth of the seats were occupied by the administrators. One-third of the remaining "
    "seats were occupied by the parents and the rest were occupied by the students. How many "
    "students were there in the school auditorium?",
    {"rows": 4, "seats": 18},
)
def _t0618(v: Slots) -> Fraction:
    seats = v.rows * v.seats
    remaining = seats - whole(seats / 4)
    return remaining - whole(remaining / 3)


@_template(
    819,
    "{n:W} students are working together to raise money for a charity. Each earns the same "
    "amount. The charity raises a total of ${total:,}. ${org:,} comes from organizations and the "
    "rest from the students. How much did each student raise?",
    {"n": 20, "total": 175000, "org": 50000},
    ranges={"total": (88000, 350000, 1000), "org": (25000, 100000, 1000)},
)
def _t0819(v: Slots) -> Fraction:
    from_students = pos(v.total - v.org)
    return whole(from_students / v.n)


@_template(
    1179,
    "James has {teeth} teeth. His dentist drills {drill} of them and caps {more} more teeth than "
    "he drills. What percentage of James' teeth does the dentist fix?",
    {"teeth": 30, "drill": 4, "more": 7},
    ranges={"teeth": (20, 32)},  # an adult mouth holds at most 32 teeth
)
def _t1179(v: Slots) -> Fraction:
    capped = v.drill + v.more
    fixed = v.drill + capped
    need(fixed < v.teeth, "more teeth fixed than James has")
    return fixed * 100 / v.teeth


@_template(
    805,
    "James buys a ring for his bride-to-be.  The diamond cost ${diamond} and the gold cost "
    "${gold}.  He pays a {pct}% premium for it to be made.  How much did he pay?",
    {"diamond": 600, "gold": 300, "pct": 30},
)
def _t0805(v: Slots) -> Fraction:
    materials = v.diamond + v.gold
    premium = whole(materials * v.pct / 100)  # whole dollars, like the original's $270
    return materials + premium


# --------------------------------------------------------------------------
# GSM8K access, selection order, generation
# --------------------------------------------------------------------------


def study_dir() -> Path:
    """This study's directory — the parent of `lib/`."""
    return Path(__file__).resolve().parent.parent


def gold_answer(solution: str) -> int:
    """GSM8K's gold: the integer after the last ``#### `` (thousands commas dropped)."""
    _head, sep, tail = solution.rpartition("#### ")
    if not sep:
        raise ValueError("GSM8K solution without a '#### ' gold marker")
    return int(tail.strip().replace(",", ""))


def read_gsm8k(path: str | Path) -> list[dict[str, Any]]:
    """The GSM8K test lines as ``{"question", "answer", "gold"}`` dicts, in file order."""
    records: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                record["gold"] = gold_answer(record["answer"])
                records.append(record)
    if len(records) != GSM8K_TEST_N:
        raise ValueError(f"expected {GSM8K_TEST_N} GSM8K test lines, read {len(records)}")
    return records


def source_records() -> list[dict[str, Any]]:
    """GSM8K test, resolved from the CONTRACT's ``data.source`` (no hardcoded path)."""
    from kleinlib.contract import load_contract
    from kleinlib.sources import resolve

    tag = load_contract(study_dir())["data"]["source"]
    resolved = resolve(tag, study_dir=study_dir(), offline=os.environ.get("KLEIN_OFFLINE") == "1")
    if resolved.path is None:
        raise RuntimeError(f"{tag!r} did not resolve to a file")
    return read_gsm8k(resolved.path)


def candidate_order() -> list[int]:
    """The selection order: ``default_rng(SELECTION_SEED).permutation(GSM8K_TEST_N)``."""
    return [int(i) for i in np.random.default_rng(SELECTION_SEED).permutation(GSM8K_TEST_N)]


def by_tid() -> dict[str, Template]:
    return {template.tid: template for template in TEMPLATES}


def _instance_key(values: Mapping[str, int]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted((name, int(value)) for name, value in values.items()))


def generate(
    seed: int,
    per_template: int,
    *,
    tag: str = "A",
    exclude: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Twin rows ``{id, template, question, answer}``, ``per_template`` per template.

    Each template draws from its own stream ``default_rng([seed, source_index])``,
    so editing one template never shifts another's twins. Ids are
    ``tw<tag>-<template>-<k>``. A draw equal to the original (refused inside
    :meth:`Template.sample`), to an earlier twin of this call, or to a row of
    ``exclude`` (another block's rows, matched on template and question) is
    re-sampled — that is how the sealed block is made disjoint from the
    development block by construction, not by luck.
    """
    if per_template < 1:
        raise ValueError("per_template must be >= 1")
    if not re.fullmatch(r"[A-Z]", tag):
        raise ValueError("tag must be one capital letter")
    excluded = {(str(row["template"]), str(row["question"])) for row in exclude}
    rows: list[dict[str, Any]] = []
    for template in TEMPLATES:
        rng = np.random.default_rng([int(seed), template.source_index])
        seen: set[tuple[tuple[str, int], ...]] = set()
        k = 0
        for _attempt in range(MAX_ATTEMPTS):
            if k == per_template:
                break
            values = template.sample(rng)
            question = template.render(values)
            key = _instance_key(values)
            if key in seen or (template.tid, question) in excluded:
                continue
            seen.add(key)
            rows.append(
                {
                    "id": f"tw{tag}-{template.tid}-{k}",
                    "template": template.tid,
                    "question": question,
                    "answer": template.solve(values),
                }
            )
            k += 1
        if k < per_template:
            raise RuntimeError(f"{template.tid}: only {k} distinct twins for seed {seed}")
    return rows


def declared_blocks() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """``(twin_dev, twin_sealed)`` exactly as `prepare.py` builds them."""
    dev = generate(TWIN_DEV_SEED, TWINS_PER_TEMPLATE, tag="A")
    sealed = generate(TWIN_SEALED_SEED, TWINS_PER_TEMPLATE, tag="C", exclude=dev)
    return dev, sealed


# --------------------------------------------------------------------------
# The validator
# --------------------------------------------------------------------------

_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})


def normalize(text: str) -> str:
    """Whitespace collapsed and typographic quotes straightened — check (b)'s only slack."""
    return " ".join(text.translate(_QUOTES).split())


def validate(records: Sequence[Mapping[str, Any]] | None = None) -> dict[str, int]:
    """Assert every template is faithful and every twin well-posed; fail loudly.

    For EVERY template: (a) ``solve(original)`` equals the GSM8K gold of
    ``source_index``; (b) ``render(original)`` equals the original question
    after :func:`normalize` (any other difference is a template bug); (c)
    ``VALIDATE_SAMPLES`` sampled instances all solve to positive integers, none
    equals the original values, none has the original's answer, every value
    stays inside 0.5x-2x of the original, and at least ``MIN_INSTANCES`` are
    distinct; (d) the degeneracy scan — no slot range reaches 0 or 1 where the
    original's value is 2 or more, and none of ``DEGENERACY_SAMPLES`` sampled
    instances (an own stream) has a slot at 0 or 1 where the original's is >= 2 or
    two slots equal that differ in the original (:func:`degeneracies`). Plus the
    selection audit (every candidate up to the last source is
    templated or skipped, exactly once) and the declared blocks (complete,
    mutually disjoint, never equal to any GSM8K test question).

    Returns a small summary; raises ``AssertionError`` listing every failure.
    """
    records = list(records) if records is not None else source_records()
    failures: list[str] = []

    # The audited selection.
    order = candidate_order()
    sources = [template.source_index for template in TEMPLATES]
    if len(sources) != N_TEMPLATES:
        failures.append(f"{len(sources)} templates, expected {N_TEMPLATES}")
    if len(set(sources)) != len(sources):
        failures.append("a GSM8K item is templated twice")
    if set(sources) & set(SKIPPED):
        failures.append(f"templated AND skipped: {sorted(set(sources) & set(SKIPPED))}")
    rank = {index: position for position, index in enumerate(order)}
    if [rank[s] for s in sources] != sorted(rank[s] for s in sources):
        failures.append("TEMPLATES are not in candidate (permutation) order")
    last = max(rank[s] for s in sources) if sources else -1
    consumed = set(order[: last + 1])
    if consumed != set(sources) | set(SKIPPED):
        unaccounted = sorted(consumed - set(sources) - set(SKIPPED))
        stray = sorted((set(sources) | set(SKIPPED)) - consumed)
        failures.append(f"selection audit: unaccounted {unaccounted}, beyond the stop {stray}")

    exact = 0
    scanned = 0
    for template in TEMPLATES:
        tid = template.tid
        record = records[template.source_index]
        original = {name: int(value) for name, value in template.original.items()}
        if slot_names(template.text) != list(original):
            failures.append(f"{tid}: text slots {slot_names(template.text)} != {list(original)}")
            continue
        # (a) the rule reproduces the gold.
        try:
            answer = template.solve(original)
        except (IllPosed, ArithmeticError) as exc:
            failures.append(f"{tid}: (a) the original is ill-posed under the rule: {exc}")
            continue
        if answer != record["gold"]:
            failures.append(f"{tid}: (a) solve(original)={answer} != gold {record['gold']}")
        # (b) the text reproduces the question.
        rendered = template.render(original)
        if rendered == record["question"]:
            exact += 1
        elif normalize(rendered) != normalize(record["question"]):
            failures.append(f"{tid}: (b) the text does not reproduce the question:\n"
                            f"  template: {normalize(rendered)}\n"
                            f"  original: {normalize(record['question'])}")
        # (c) sampled twins.
        rng = np.random.default_rng([VALIDATE_SEED, template.source_index])
        distinct: set[tuple[tuple[str, int], ...]] = set()
        for _ in range(VALIDATE_SAMPLES):
            try:
                values = template.sample(rng)
                twin_answer = template.solve(values)
            except (IllPosed, RuntimeError) as exc:
                failures.append(f"{tid}: (c) sampling failed: {exc}")
                break
            if values == original or twin_answer == answer:
                failures.append(f"{tid}: (c) a twin repeats the original ({values})")
                break
            outside = [n for n, x in values.items() if not original[n] // 2 <= x <= 2 * original[n]]
            if outside:
                failures.append(f"{tid}: (c) {outside} outside 0.5x-2x of the original ({values})")
                break
            distinct.add(_instance_key(values))
        if len(distinct) < MIN_INSTANCES:
            failures.append(f"{tid}: (c) only {len(distinct)} distinct twins (< {MIN_INSTANCES})")
        # (d) the degeneracy scan.
        if template.drawer is None:
            floor = [f"{n}: {template.ranges[n][0]}" for n, x in original.items()
                     if x >= 2 and template.ranges[n][0] <= 1]
            if floor:
                failures.append(f"{tid}: (d) ranges reach 0/1 under an original >= 2: {floor}")
        rng = np.random.default_rng([VALIDATE_SEED, template.source_index, 1])
        flagged: dict[str, int] = {}
        for _ in range(DEGENERACY_SAMPLES):
            try:
                values = template.sample(rng)
            except RuntimeError as exc:
                failures.append(f"{tid}: (d) sampling failed: {exc}")
                break
            scanned += 1
            for flag in degeneracies(original, values):
                flagged[flag] = flagged.get(flag, 0) + 1
        if flagged:
            failures.append(f"{tid}: (d) degenerate twins in {DEGENERACY_SAMPLES} draws: {flagged}")

    # The declared blocks, exactly as prepare.py builds them.
    if not failures:
        dev, sealed = declared_blocks()
        gsm8k_questions = {normalize(r["question"]) for r in records}
        for name, block in (("twin_dev", dev), ("twin_sealed", sealed)):
            if len(block) != TWINS_PER_TEMPLATE * len(TEMPLATES):
                failures.append(f"{name}: {len(block)} rows")
            clash = [row["id"] for row in block if normalize(row["question"]) in gsm8k_questions]
            if clash:
                failures.append(f"{name}: twins equal to a GSM8K test question: {clash[:5]}")
        overlap = {(r["template"], r["question"]) for r in dev} & {
            (r["template"], r["question"]) for r in sealed
        }
        if overlap:
            failures.append(f"twin_dev and twin_sealed share {len(overlap)} instances")

    if failures:
        raise AssertionError("twins.validate failed:\n- " + "\n- ".join(failures))
    return {
        "templates": len(TEMPLATES),
        "skipped": len(SKIPPED),
        "exact_text": exact,
        "candidates_consumed": last + 1,
        "degeneracy_scanned": scanned,
    }
