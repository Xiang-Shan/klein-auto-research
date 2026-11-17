"""The inquiry model as data: the three axes a study is typed on.

``references/inquiry-model.md`` types every study on three orthogonal axes.  This
module is the ONE place the engine keeps them; ``contract.py``, ``schema.py`` and
``scaffold.py`` read from here instead of each holding its own table.

* **kind** — the question's shape.  It fixes how a track is judged (the default
  track mode, what confirmation requires, whether a verifier is mandatory), so the
  set is closed: a new kind is a change to the kernel, never a plug-in.
* **modality** — the evidence source.  It selects the headings the Gate-1 data card
  must carry and nothing else, so a plug-in may add one.
* **profile** — the audience.  It changes headings, vocabulary and doctrine, never
  what the engine checks, so a plug-in may add one (:mod:`kleinlib.plugins`).

Adding a modality or a profile is one :func:`register_modality` /
:func:`register_profile` call; no ``if`` in the engine names one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "KINDS",
    "KindSpec",
    "ModalitySpec",
    "ProfileSpec",
    "kind_names",
    "kind_spec",
    "modality_names",
    "modality_spec",
    "profile_names",
    "profile_spec",
    "register_modality",
    "register_profile",
    "required_card_sections",
]


@dataclass(frozen=True)
class KindSpec:
    """One question shape and what it fixes about judging."""

    name: str
    #: Default mode of a track: ``frontier`` climbs (keep / discard), ``registered``
    #: measures pre-registered cells (measured).
    track_mode: str
    #: The mutable surface ``klein new`` scaffolds for this kind.
    entrypoint: str
    #: ``confirmation.require`` when the contract leaves it out.
    confirmation: tuple[str, ...]
    #: The objective is computed by a declared checker, never reported by the search.
    requires_verifier: bool = False
    summary: str = ""


@dataclass(frozen=True)
class ModalitySpec:
    """One evidence-source shape and the data-card headings it requires."""

    name: str
    card_sections: tuple[str, ...]
    #: Extra headings under ``policy.card_sections: enforce``.
    policy_sections: tuple[str, ...] = ()
    summary: str = ""


@dataclass(frozen=True)
class ProfileSpec:
    """One audience.  ``doc`` is its markdown profile when it does not ship with Klein."""

    name: str
    #: Extra data-card headings under ``policy.card_sections: enforce``.
    card_sections: tuple[str, ...] = ()
    doc: Path | None = None
    summary: str = ""


# --------------------------------------------------------------------------
# kind — closed
# --------------------------------------------------------------------------

#: The seven question shapes, in the order the docs list them.  ``discover``
#: closes nothing: a discovery is a hypothesis, and its promotion is a follow-up
#: ``test`` study.
KINDS: dict[str, KindSpec] = {
    spec.name: spec
    for spec in (
        KindSpec("predict", "frontier", "train.py", ("sealed",), summary="fit a model, score it out of sample"),
        KindSpec("estimate", "registered", "analyze.py", ("sealed",), summary="measure a quantity with its uncertainty"),
        KindSpec("test", "registered", "analyze.py", ("sealed",), summary="decide a registered hypothesis"),
        KindSpec("simulate", "registered", "simulate.py", ("sealed",), summary="recover a known truth from a declared DGP"),
        KindSpec("replicate", "registered", "analyze.py", ("sealed",), summary="reproduce a published result"),
        KindSpec("discover", "registered", "analyze.py", (), summary="explore for hypotheses; confirms nothing"),
        KindSpec("optimize", "frontier", "search.py", ("verify",), requires_verifier=True, summary="search for an object a checker scores"),
    )
}

#: The kind a contract that does not type itself is scaffolded as.
DEFAULT_KIND = "predict"


def kind_names() -> tuple[str, ...]:
    return tuple(KINDS)


def kind_spec(kind: str | None) -> KindSpec:
    """The spec of ``kind``; an absent or unknown kind reads as :data:`DEFAULT_KIND`."""
    return KINDS.get(str(kind), KINDS[DEFAULT_KIND])


# --------------------------------------------------------------------------
# modality — open
# --------------------------------------------------------------------------

_EVERY: tuple[str, ...] = ("Source & shape", "Ranked go / no-go issues", "Go / no-go")
_TABLE: tuple[str, ...] = ("Profile summary", "Clean-room leakage audit")
_NEAR_DUP: tuple[str, ...] = ("Near-duplicate audit",)

_MODALITIES: dict[str, ModalitySpec] = {}
_PROFILES: dict[str, ProfileSpec] = {}


def register_modality(spec: ModalitySpec) -> None:
    """Add an evidence-source shape.  Re-registering the same spec is a no-op."""
    existing = _MODALITIES.get(spec.name)
    if existing is not None and existing != spec:
        raise ValueError(f"modality {spec.name!r} is already registered with a different spec")
    _MODALITIES[spec.name] = spec


def register_profile(spec: ProfileSpec) -> None:
    """Add an audience profile.  Re-registering the same spec is a no-op."""
    existing = _PROFILES.get(spec.name)
    if existing is not None and existing != spec:
        raise ValueError(f"profile {spec.name!r} is already registered with a different spec")
    _PROFILES[spec.name] = spec


for _spec in (
    ModalitySpec("tabular", _EVERY + _TABLE, summary="a table of rows"),
    ModalitySpec("timeseries", _EVERY + _TABLE + ("Time policy",), summary="rows ordered in time"),
    ModalitySpec("image", _EVERY + _TABLE + ("Group policy",), _NEAR_DUP, summary="images"),
    ModalitySpec("sequence", _EVERY + _TABLE + ("Group policy",), _NEAR_DUP, summary="sequences"),
    ModalitySpec("graph", _EVERY + _TABLE + ("Group policy",), _NEAR_DUP, summary="graphs"),
    ModalitySpec("text", _EVERY + _TABLE + ("Group policy",), _NEAR_DUP, summary="text"),
    ModalitySpec("simulation", _EVERY + ("DGP card",), summary="a simulator with a declared truth"),
    ModalitySpec("none", _EVERY + ("Verifier card",), summary="no data: a verifier alone"),
):
    register_modality(_spec)

for _profile in (
    ProfileSpec("generic", summary="a general scientific reader"),
    ProfileSpec("ml-research", summary="an ML / deep-learning researcher"),
    ProfileSpec("math", summary="a mathematician"),
    ProfileSpec("insurance", summary="a pricing actuary"),
    ProfileSpec("llm", ("Contamination audit",), summary="an LLM evaluation researcher"),
    ProfileSpec("cv", summary="a computer-vision researcher"),
    ProfileSpec("data-science", summary="an applied data scientist"),
):
    register_profile(_profile)

#: What ships with Klein, before any plug-in registers more.
BUILTIN_MODALITIES: tuple[str, ...] = tuple(_MODALITIES)
BUILTIN_PROFILES: tuple[str, ...] = tuple(_PROFILES)


def _with_plugins() -> None:
    from .plugins import ensure_loaded

    ensure_loaded()


def modality_names() -> tuple[str, ...]:
    _with_plugins()
    return tuple(_MODALITIES)


def modality_spec(modality: str | None) -> ModalitySpec | None:
    _with_plugins()
    return _MODALITIES.get(str(modality))


def profile_names() -> tuple[str, ...]:
    _with_plugins()
    return tuple(_PROFILES)


def profile_spec(profile: str | None) -> ProfileSpec | None:
    _with_plugins()
    return _PROFILES.get(str(profile))


def required_card_sections(modality: str | None, profile: str | None) -> tuple[str, ...]:
    """Headings ``data_card.md`` must carry under ``policy.card_sections: enforce``."""
    m = modality_spec(modality)
    p = profile_spec(profile)
    return (
        *(m.card_sections if m else ()),
        *(m.policy_sections if m else ()),
        *(p.card_sections if p else ()),
    )


def _sections_view(names: Sequence[str], field: str) -> dict[str, tuple[str, ...]]:
    return {
        name: getattr(_MODALITIES[name], field)
        for name in names
        if getattr(_MODALITIES[name], field)
    }
