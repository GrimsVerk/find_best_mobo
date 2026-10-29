"""Tests for `scripts/drop-gpu-claims.py` — the one-way door out of the claim store.

Written blind from the specification and the owner's ruling of 2026-08-25 while
the script is authored in parallel, so a failing import is the expected state
until assembly. Nothing here executes the script as a script and nothing here
writes to `data/claims.jsonl`: the two names under test are a pure predicate and
a pure guard, and both are exercised with claims built in memory.

**Why the file exists at all.** ESC-29: the extraction prompt never told the model
to skip graphics cards, so a GPU review was bundled, extracted, and produced
perfectly well-formed claims — right schema, real timestamps, quotable snippets —
about a product this project is not about. The claims are not malformed, which is
precisely why `claims.parse_claims` waved them through and why a script rather
than a schema is what removes them.

**Why the tests lean so hard one way.** The owner ruled in chat on 2026-08-25, and
stated it twice, that it is far more important to KEEP motherboard claims than to
remove graphics-card ones. The two errors are not symmetric and must not be tested
as though they were:

- A graphics-card claim left in the store is a row a human reader recognises as
  off-topic the moment they read it, in a store that is evidence and is read by
  hand. It costs a raised eyebrow.
- A motherboard claim removed from the store is gone. The store is append-only
  (`docs/DESIGN.md` §9), the excerpt it came from has been consumed, and
  re-extracting it costs another model call against the R26 ceiling. Nothing
  downstream can tell the difference between a claim that was deleted and a claim
  the model never made, so over-deletion does not fail — it looks like success.

So the bulk of this file feeds the predicate claims that a careless implementation
would drop and asserts that it keeps them. The handful of cases in the other
direction use unambiguous graphics-card vocabulary only — no VRM talk, no board
brand, nothing the specification's keep-rules name — because a marginal case that
this file demanded be DROPPED would push the implementation in exactly the
direction the ruling forbids.

**What this file deliberately does NOT pin.** How the three signals are computed
(a word list, a regex, a score) or in which order they are consulted — only that
all three must agree before a claim is removed, and that any one of them
disagreeing keeps it. Nor does it test malformed claims: the store is validated
upstream by `claims.parse_claims`, every claim reaching this script carries all
nine keys, and a predicate hardened against absent keys would be hardened against
something that cannot happen while staying soft on the thing that can.
"""

from __future__ import annotations

import builtins
import inspect
import os
from collections.abc import Callable, Mapping, Sequence
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "drop-gpu-claims.py"

# Loaded by path, because it is a script and not a package module: it lives under
# `scripts/` beside `run.sh`, its filename is hyphenated and therefore not a legal
# import name, and `src/find_best_mobo/` is for things the pipeline imports. A
# one-way door over the claim store is not one of those.
_module = SourceFileLoader("drop_gpu_claims", str(SCRIPT)).load_module()

# Bound with explicit annotations rather than used through the module object, so
# that the signatures the specification declares are asserted by mypy on every run
# and not merely by the tests below when they happen to execute.
MAX_DROPPED_FRACTION: float = _module.MAX_DROPPED_FRACTION
RefusedToDrop: type[RuntimeError] = _module.RefusedToDrop
is_about_a_graphics_card: Callable[[Mapping[str, Any]], bool] = _module.is_about_a_graphics_card
refuse_if_too_much_is_dropped: Callable[[Sequence[Mapping[str, Any]], int], None] = (
    _module.refuse_if_too_much_is_dropped
)

# The nine keys of a claim (`src/find_best_mobo/claims.py`). Asserted against every
# fixture in this file, so a fixture that quietly lost a key cannot make a keep
# look like a pass for the wrong reason.
CLAIM_KEYS: frozenset[str] = frozenset(
    {
        "board",
        "video_id",
        "video_title",
        "timestamp_seconds",
        "snippet",
        "category",
        "subject",
        "polarity",
        "batch",
    }
)


# --- the claim this file starts from ------------------------------------------

# A claim ESC-29 actually produced, in the sense that matters: the video is a
# graphics-card review, the text is about the card, and nothing anywhere in it
# names a chipset, a socket, firmware or a board family. All three signals agree,
# so this is the shape the script exists to remove — and every fixture below is
# this claim with ONE thing changed, so a failure names the change rather than the
# fixture.
GRAPHICS_CARD_CLAIM: dict[str, Any] = {
    "board": "RTX 4090 Founders Edition",
    "video_id": "gpu0000001a",
    "video_title": "RTX 4090 review — the coolest graphics card you can buy",
    "timestamp_seconds": 128.5,
    "snippet": "this card runs cool because the cooler on it is genuinely enormous",
    "category": "tested",
    "subject": "features",
    "polarity": "positive",
    "batch": 3,
}


def claim(**overrides: Any) -> dict[str, Any]:
    """The graphics-card claim with `overrides` applied."""
    return dict(GRAPHICS_CARD_CLAIM) | overrides


def describe(candidate: Mapping[str, Any]) -> str:
    """The three fields any of the signals could have read, named in one line."""
    return (
        f"board={candidate['board']!r} video_title={candidate['video_title']!r} "
        f"snippet={candidate['snippet']!r}"
    )


def assert_kept(candidate: Mapping[str, Any], because: str) -> None:
    """The claim survives. This is the assertion the owner's ruling is about."""
    assert not is_about_a_graphics_card(candidate), (
        f"a claim that must be KEPT was flagged for removal: {describe(candidate)}. "
        f"{because} The store is append-only and the excerpt behind this claim is "
        "already consumed, so a wrong removal here is permanent and silent — "
        "over-deletion is the unacceptable error (owner's ruling, 2026-08-25)."
    )


def assert_dropped(candidate: Mapping[str, Any], because: str) -> None:
    """The claim goes. Used only where all three signals are beyond argument."""
    assert is_about_a_graphics_card(candidate), (
        f"a claim that must be DROPPED was kept: {describe(candidate)}. {because} "
        "Nothing in it names a chipset, a socket, firmware or a board family, so "
        "there is nothing here for the keep-rules to have caught."
    )


# --- the vocabularies the keep-rules are built from ---------------------------

# The three words that make a video title say "motherboard" out loud. Case is not
# part of the word: a title is written by a channel, not by a schema.
MOTHERBOARD_WORDS = ("mobo", "motherboard", "mainboard")

# Chipsets, a socket and firmware. Any one of these anywhere in a claim means the
# claim is discussing the thing a motherboard IS, whatever else it mentions.
CHIPSETS_AND_PLATFORM = ("B650", "X670E", "Z790", "AM5", "LGA1700")

# Board families. Every one of these is a product line that exists only as a
# motherboard, which is what makes them safe keep-signals rather than guesses.
BOARD_FAMILIES = (
    "Taichi",
    "Tomahawk",
    "Aorus",
    "Crosshair",
    "Maximus",
    "Apex",
    "Godlike",
    "Krait",
    "Designare",
)

# Brands that sell both kinds of product under the same badge, and in the case of
# ROG Strix the same SUB-badge: there is an ROG Strix B650-E motherboard and an ROG
# Strix RTX 4090 graphics card. A brand is evidence of a manufacturer and of
# nothing else.
AMBIGUOUS_BRANDS = ("MSI", "ASUS", "ROG Strix")


def all_fixture_claims() -> tuple[dict[str, Any], ...]:
    """Every claim this file feeds the predicate, gathered for the schema guard."""
    return (
        claim(),
        *MOTHERBOARD_TITLE_CLAIMS,
        *PLATFORM_CLAIMS,
        *FAMILY_CLAIMS,
        *KRAIT_CLAIMS,
        *BRAND_ONLY_CLAIMS,
        *MOTHERBOARD_VIDEO_CLAIMS,
        *SIGNAL_DISAGREEMENT_CLAIMS,
        *UNAMBIGUOUS_GRAPHICS_CARD_CLAIMS,
    )


# --- fixtures: a motherboard video, whatever the text looks like ---------------

# Each of these carries the most card-like body this file can write — a Founders
# Edition board name, VRAM, a GPU die, the word "card" twice — and a title that
# says motherboard. The title wins. That is the absolute rule, and these exist to
# prove it cannot be defeated by piling card vocabulary into the other fields.
_LOUD_CARD_BODY: dict[str, Any] = {
    "board": "RTX 4090 Founders Edition",
    "snippet": "this graphics card's VRAM sits right against the GPU die, so the card cooks",
}

MOTHERBOARD_TITLE_CLAIMS: tuple[dict[str, Any], ...] = (
    claim(video_title="B650 mobo VRM breakdown", **_LOUD_CARD_BODY),
    claim(video_title="Cheap motherboard roundup", **_LOUD_CARD_BODY),
    claim(video_title="Mainboard power delivery, explained slowly", **_LOUD_CARD_BODY),
    claim(video_title="MOTHERBOARD VRM TIER LIST (again)", **_LOUD_CARD_BODY),
    claim(video_title="Which Mobo Should You Actually Buy", **_LOUD_CARD_BODY),
    # The hardest shape: the title names BOTH products. A title that says
    # motherboard is a motherboard video even when a card is mentioned in it,
    # because the alternative is dropping every claim from every video that ever
    # compared a board against a card.
    claim(video_title="Does your motherboard bottleneck an RTX 4090?", **_LOUD_CARD_BODY),
    claim(video_title="RTX 4090 vs the PCIe slot on this motherboard", **_LOUD_CARD_BODY),
    claim(video_title="GPU sag and what your mobo can do about it", **_LOUD_CARD_BODY),
)


# --- fixtures: a chipset, a socket or firmware anywhere in the claim ------------


def _platform_claim(token: str, where: str) -> dict[str, Any]:
    """The graphics-card claim with `token` planted in `where`, and nothing else."""
    if where == "board":
        return claim(board=f"ASRock {token} Pro RS")
    return claim(snippet=f"the {token} implementation here is what makes the difference")


PLATFORM_CLAIMS: tuple[dict[str, Any], ...] = (
    *(_platform_claim(token, "snippet") for token in CHIPSETS_AND_PLATFORM),
    *(_platform_claim(token, "board") for token in CHIPSETS_AND_PLATFORM),
    claim(snippet="you have to reseat it in the socket before the training completes"),
    claim(snippet="the BIOS shipped with a memory training bug and they fixed it in 1.24"),
    claim(board="Socket AM5 reference design"),
)


# --- fixtures: a board family named in a graphics-card video -------------------


def _family_claim(family: str) -> dict[str, Any]:
    """A family named in the board field, with the GPU video title left in place."""
    return claim(board=f"ASRock {family}")


FAMILY_CLAIMS: tuple[dict[str, Any], ...] = tuple(_family_claim(f) for f in BOARD_FAMILIES)


# --- fixtures: the Krait trap --------------------------------------------------

# `MSI 970 Gaming Krait` is an AM3+ motherboard. The number reads like a GPU model
# (there is a GeForce GTX 970, and Buildzoid has talked about both), the brand
# reads like either, and the only thing in the string that settles it is the word
# Krait. An implementation that scores numbers, or that stops at the brand, deletes
# a motherboard claim here.
KRAIT_CLAIMS: tuple[dict[str, Any], ...] = (
    claim(board="MSI 970 Gaming Krait"),
    claim(snippet="the MSI 970 Gaming Krait is the one with the four-phase doubler mess"),
    claim(board="MSI 970 Gaming Krait", video_title="GTX 970 vs RTX 4090, ten years apart"),
)


# --- fixtures: a brand and nothing else ----------------------------------------


def _brand_only_claim(brand: str) -> dict[str, Any]:
    """A claim whose ONLY product signal is a brand that sells both kinds."""
    return claim(
        board=brand,
        video_title=f"{brand} hardware, a long ramble",
        snippet="the power stages are rated far above anything anyone will actually pull",
    )


BRAND_ONLY_CLAIMS: tuple[dict[str, Any], ...] = tuple(
    _brand_only_claim(brand) for brand in AMBIGUOUS_BRANDS
)


# --- fixtures: whole motherboard videos ----------------------------------------

# Six claims of the kind this project exists to collect, across the four
# categories, the five subjects and the three polarities. None of their titles
# contains "mobo", "motherboard" or "mainboard" — these are kept because the video
# is about a board, not because a keyword rescued them.
MOTHERBOARD_VIDEO_CLAIMS: tuple[dict[str, Any], ...] = (
    claim(
        board="ASRock X670E Taichi",
        video_id="mobo000001a",
        video_title="X670E VRM breakdown — which boards are actually overbuilt",
        snippet="the Taichi's VRM is genuinely overbuilt for anything you can socket",
        category="tested",
        subject="vrm_capacity",
        polarity="positive",
    ),
    claim(
        board="MSI MAG B650 Tomahawk",
        video_id="mobo000002b",
        video_title="B650 boards, ranked by what the VRM can actually do",
        snippet="for the money the Tomahawk is the one I would buy",
        category="reasoned",
        subject="value",
        polarity="positive",
    ),
    claim(
        board="Gigabyte Z790 Aorus Master",
        video_id="mobo000003c",
        video_title="Z790 power delivery, phase by phase",
        snippet="the BIOS lets it run a load-line that will cook the socket",
        category="warning",
        subject="voltage_firmware_safety",
        polarity="negative",
    ),
    claim(
        board="ASUS ROG Crosshair X670E Hero",
        video_id="mobo000004d",
        video_title="AM5 memory training is still a mess",
        snippet="people tell me the Hero trains 6000 first try and I have not seen it",
        category="secondhand",
        subject="memory",
        polarity="mixed",
    ),
    claim(
        board="MSI MEG Z790 Godlike",
        video_id="mobo000005e",
        video_title="LGA1700 flagship teardown",
        snippet="you are paying for the feature list and not for the power stages",
        category="reasoned",
        subject="features",
        polarity="mixed",
    ),
    claim(
        board="ASRock B650M Pro RS",
        video_id="mobo000006f",
        video_title="Cheap AM5 boards that are not garbage",
        snippet="this thing has no business being this good at the price",
        category="tested",
        subject="value",
        polarity="positive",
    ),
)


# --- fixtures: exactly one signal disagreeing ----------------------------------

# The specification says three signals must AGREE. Each of these switches off
# exactly one of them and leaves the other two shouting "graphics card", so a
# predicate that treats any two as sufficient fails here and nowhere else.
SIGNAL_DISAGREEMENT_CLAIMS: tuple[dict[str, Any], ...] = (
    # Signal 1 off: the video is not about a card. The text still is.
    claim(video_title="Rambling about power delivery for forty minutes"),
    # Signal 2 off: the claim's own text is not about a card. The video still is.
    claim(
        board="MSI",
        snippet="the power stages are rated far above anything anyone will actually pull",
    ),
    # Signal 3 off: something in the claim names a platform. The rest still shouts card.
    claim(board="ASRock X670E Taichi", snippet="this card's cooler is enormous, as is the board"),
)


# --- fixtures: the other direction, and only where it is beyond argument -------

UNAMBIGUOUS_GRAPHICS_CARD_CLAIMS: tuple[dict[str, Any], ...] = (
    claim(),
    claim(
        board="RX 7900 XTX",
        video_id="gpu0000002b",
        video_title="RX 7900 XTX review — three graphics cards compared",
        snippet="of the three cards this one has by far the quietest cooler",
        category="tested",
        subject="features",
        polarity="positive",
    ),
    claim(
        board="RTX 4080 Super",
        video_id="gpu0000003c",
        video_title="RTX 4080 Super teardown — inside the graphics card",
        snippet="the VRAM on the back of the card has no thermal pad at all",
        category="warning",
        subject="features",
        polarity="negative",
    ),
)


def claim_id(candidate: Mapping[str, Any]) -> str:
    """A parametrize id a person can read in a failure line."""
    return f"{candidate['board']}|{candidate['video_title']}"[:70]


# --- the module's surface ------------------------------------------------------


class TestTheModuleSurface:
    """The four public names, before anything is asserted about behaviour.

    A blind test file that guessed a name wrong produces a wall of attribute
    errors and no information. These four assertions turn that into one line
    naming the missing piece.
    """

    def test_the_script_exists_where_the_pipeline_keeps_its_scripts(self) -> None:
        """Beside `run.sh`, not inside `src/`: nothing in the pipeline imports it."""
        assert SCRIPT.is_file(), (
            f"no script at {SCRIPT}. The claim store's repair tool is not part of the "
            "package — it is a one-off run by hand — so it belongs under `scripts/`."
        )

    def test_the_ceiling_is_one_claim_in_twenty(self) -> None:
        """5% is a ceiling on a REPAIR, not a budget to spend up to.

        ESC-29 is one video's worth of claims in a store built from a whole
        channel. A run proposing to remove more than a twentieth of everything has
        stopped being a repair and become a rewrite, and the number is pinned here
        so that widening it is a visible edit rather than a tuning knob.
        """
        assert MAX_DROPPED_FRACTION == 0.05, (
            f"the drop ceiling is {MAX_DROPPED_FRACTION}, not 0.05. Raising it makes a "
            "larger silent deletion look like a successful run."
        )
        assert isinstance(MAX_DROPPED_FRACTION, float), (
            f"the drop ceiling is {type(MAX_DROPPED_FRACTION).__name__}, not a float"
        )

    def test_the_refusal_is_a_runtime_error(self) -> None:
        """So an unhandled refusal aborts the script instead of being caught as a ValueError."""
        assert issubclass(RefusedToDrop, RuntimeError), (
            f"RefusedToDrop derives from {RefusedToDrop.__mro__[1].__name__}, not RuntimeError"
        )

    def test_the_predicate_takes_one_claim_and_nothing_else(self) -> None:
        """A predicate reaching for a config, a path or a flag is not a predicate."""
        parameters = list(inspect.signature(is_about_a_graphics_card).parameters)
        assert len(parameters) == 1, (
            f"`is_about_a_graphics_card` takes {parameters}, but a claim is the whole "
            "input: anything else it consults is state a caller cannot see."
        )


class TestTheFixturesAreCompleteClaims:
    """Every fixture carries all nine keys, because the store is validated upstream.

    `claims.parse_claims` refuses a file with a missing key, a null, or a field the
    prompt never asked for, and the append-only store is written only through it.
    So a claim reaching this script always has all nine. This guard exists to keep
    THIS FILE honest rather than to test the script: a fixture that lost `snippet`
    to a typo would sail through every keep-assertion below for a reason that has
    nothing to do with the rules under test.
    """

    @pytest.mark.parametrize("candidate", all_fixture_claims(), ids=claim_id)
    def test_a_fixture_claim_carries_every_key(self, candidate: Mapping[str, Any]) -> None:
        assert set(candidate) == CLAIM_KEYS, (
            f"fixture claim is not a whole claim: {describe(candidate)} — missing "
            f"{sorted(CLAIM_KEYS - set(candidate))}, unexpected "
            f"{sorted(set(candidate) - CLAIM_KEYS)}"
        )


# --- the over-deletion direction, which is most of this file -------------------


class TestAMotherboardInTheTitleIsAbsolute:
    """A video that says motherboard produces motherboard claims. No exceptions.

    This is the strongest of the keep-rules and the only one stated as an
    absolute: if `video_title` contains "mobo", "motherboard" or "mainboard", the
    claim is never dropped, whatever its text looks like. The reason is the shape
    of Buildzoid's channel — a motherboard video discusses graphics cards
    constantly, for GPU sag, for PCIe lanes, for transient load on the same 12V
    rail — and every one of those sentences is a claim about a BOARD made while
    talking about a card.

    The bodies below are deliberately the most card-like text in this file. If any
    of them defeats the title, the rule is not absolute and the ruling is not
    implemented.
    """

    @pytest.mark.parametrize("candidate", MOTHERBOARD_TITLE_CLAIMS, ids=claim_id)
    def test_a_motherboard_title_survives_the_loudest_card_text(
        self, candidate: Mapping[str, Any]
    ) -> None:
        assert_kept(
            candidate,
            "Its video_title names a motherboard, which is an absolute keep whatever "
            "the board field and the snippet say.",
        )

    @pytest.mark.parametrize("word", MOTHERBOARD_WORDS, ids=MOTHERBOARD_WORDS)
    @pytest.mark.parametrize("case", ("lower", "upper", "title"), ids=("lower", "upper", "title"))
    def test_the_title_word_is_matched_whatever_its_case(self, word: str, case: str) -> None:
        """Titles are written by a channel, so capitalisation carries no meaning.

        A rule that matched "motherboard" and not "Motherboard" would delete the
        claims of every video whose title was typed in title case — which is most
        of them.
        """
        rendered = {"lower": word.lower(), "upper": word.upper(), "title": word.title()}[case]
        candidate = claim(video_title=f"RTX 4090 and your {rendered} — what actually matters")

        assert_kept(
            candidate,
            f"Its video_title contains {rendered!r}, and case is not part of the word.",
        )


class TestAPlatformNameKeepsAClaim:
    """A chipset, a socket or firmware anywhere in a claim means it is about a board.

    These names have no graphics-card reading at all: nothing sold as a card is a
    B650, sits in LGA1700, or ships a BIOS. So the moment one appears — in the
    board field or inside the snippet — the third signal disagrees and the claim
    stays, even though the video it came from really is a graphics-card review.

    That case is not hypothetical, and it is the reason the rule is written this
    way round: a GPU review that spends thirty seconds on what the card does to
    the board's PCIe slot produces claims this project wants.
    """

    @pytest.mark.parametrize("candidate", PLATFORM_CLAIMS, ids=claim_id)
    def test_a_claim_naming_a_platform_is_kept(self, candidate: Mapping[str, Any]) -> None:
        assert_kept(
            candidate,
            "It names a chipset, a socket or a BIOS — none of which a graphics card has "
            "— so the claim is about a board however card-like the video was.",
        )


class TestABoardFamilyKeepsAClaim:
    """Taichi, Tomahawk, Aorus, Crosshair, Maximus, Apex, Godlike, Krait, Designare.

    Each is a product line that exists only as a motherboard, which is what makes
    it a safe keep-signal: a false keep costs an off-topic row, and there is no
    false-drop to trade against because no graphics card carries these names.

    Every fixture here keeps the graphics-card VIDEO TITLE from the baseline claim,
    so the family name is doing all the work. A predicate that consulted only the
    video would drop all nine.
    """

    @pytest.mark.parametrize("candidate", FAMILY_CLAIMS, ids=claim_id)
    def test_a_board_family_is_kept_even_from_a_graphics_card_video(
        self, candidate: Mapping[str, Any]
    ) -> None:
        assert_kept(
            candidate,
            "Its board field names a motherboard product line, and no graphics card is "
            "sold under any of these names.",
        )


class TestTheKraitTrap:
    """`MSI 970 Gaming Krait` is a motherboard, and everything about it says GPU.

    The specification calls this one out by name and it is the single best test of
    whether an implementation reasons about product KINDS or pattern-matches model
    numbers. The string contains a brand that sells both, a three-digit number that
    is also a famous GeForce model, and the word "Gaming". Only "Krait" settles it.

    The third fixture is the trap fully loaded: the same board named in a video
    whose title really is about graphics cards. Two of the three signals point at a
    card and the claim must still be kept, because the cost of being wrong is a
    permanently deleted motherboard claim.
    """

    @pytest.mark.parametrize("candidate", KRAIT_CLAIMS, ids=claim_id)
    def test_the_krait_is_a_motherboard(self, candidate: Mapping[str, Any]) -> None:
        assert_kept(
            candidate,
            "`MSI 970 Gaming Krait` is an AM3+ motherboard; the 970 is its chipset and "
            "not a GeForce model, and matching the number deletes a board claim.",
        )


class TestABrandAloneNeverDecides:
    """MSI, ASUS and ROG Strix name both product kinds, so they settle nothing.

    ROG Strix is the sharpest of the three: there is an ROG Strix B650-E motherboard
    and an ROG Strix RTX 4090 graphics card, and the badge is identical. Any weight
    put on a brand is weight put on a coin flip — and the coin flip is being used to
    decide whether to permanently delete evidence.

    The second test is the stronger statement: a brand may not FLIP a verdict. Each
    board claim that is kept is kept just as firmly with a brand bolted onto the
    front of it.
    """

    @pytest.mark.parametrize("candidate", BRAND_ONLY_CLAIMS, ids=claim_id)
    def test_a_brand_is_not_enough_to_drop_a_claim(self, candidate: Mapping[str, Any]) -> None:
        assert_kept(
            candidate,
            "A brand names a manufacturer and not a product kind; this claim's only "
            "product signal is that brand.",
        )

    @pytest.mark.parametrize("brand", AMBIGUOUS_BRANDS, ids=AMBIGUOUS_BRANDS)
    def test_prefixing_a_brand_does_not_flip_a_kept_claim(self, brand: str) -> None:
        for kept in MOTHERBOARD_VIDEO_CLAIMS:
            branded = dict(kept) | {"board": f"{brand} {kept['board']}"}
            assert_kept(
                branded,
                f"Prefixing {brand!r} onto a board that was already kept changed the "
                "verdict, so the brand is deciding rather than describing.",
            )


class TestMotherboardVideosAreKeptEnMasse:
    """The ordinary case: the store is motherboard claims, and it stays that way.

    Nothing exotic here — six claims of the kind the pipeline is built to collect,
    spread across the categories, subjects and polarities of `docs/DESIGN.md` §9.
    They are the population, and the graphics-card claims are the anomaly. A
    predicate that removed even one of these would be removing evidence at scale,
    quietly, from an append-only file.
    """

    @pytest.mark.parametrize("candidate", MOTHERBOARD_VIDEO_CLAIMS, ids=claim_id)
    def test_an_ordinary_motherboard_claim_is_kept(self, candidate: Mapping[str, Any]) -> None:
        assert_kept(candidate, "It is an ordinary motherboard claim from a motherboard video.")

    def test_not_one_motherboard_claim_in_the_whole_set_is_dropped(self) -> None:
        """Stated over the set as well as per claim, because the fraction is what bites.

        `refuse_if_too_much_is_dropped` only notices deletion above 5%. A predicate
        that dropped one board claim in every twenty would pass the guard and pass
        a per-claim test that happened to miss that one, so the set is asserted as
        a set.
        """
        dropped = [c for c in MOTHERBOARD_VIDEO_CLAIMS if is_about_a_graphics_card(c)]
        named = "; ".join(describe(c) for c in dropped)

        assert not dropped, (
            f"{len(dropped)} of {len(MOTHERBOARD_VIDEO_CLAIMS)} motherboard claims were "
            f"flagged for removal: {named}"
        )


class TestAllThreeSignalsMustAgree:
    """Any one signal disagreeing keeps the claim. Two out of three is not a majority.

    This is the specification's rule stated as a test rather than as a sentence.
    Each fixture below is the baseline graphics-card claim with exactly ONE signal
    switched off, so an implementation that scores the signals, or that requires
    only two, fails here precisely.

    The asymmetry is the whole design: agreement is required for the destructive
    answer and a single dissent is enough for the safe one, because the two answers
    do not cost the same.
    """

    @pytest.mark.parametrize("candidate", SIGNAL_DISAGREEMENT_CLAIMS, ids=claim_id)
    def test_one_dissenting_signal_is_enough_to_keep(self, candidate: Mapping[str, Any]) -> None:
        assert_kept(
            candidate,
            "Exactly one of the three signals disagrees, and one is enough: a claim "
            "removed on a two-out-of-three vote is a claim removed on a guess.",
        )

    def test_a_claim_with_no_signal_at_all_is_kept(self) -> None:
        """Silence is not agreement. A claim naming nothing recognisable stays.

        This is the default the whole file rests on: unsure means keep. A predicate
        whose signals are absent rather than negative — an empty board, a title
        naming neither kind, a snippet about a number — must still answer False.
        """
        candidate = claim(
            board="the one on the left",
            video_title="Answering questions from the last stream",
            snippet="it was about four hundred at the time and it is not any more",
        )

        assert_kept(candidate, "Nothing in it names either product kind, and unsure means keep.")


# --- the under-deletion direction, kept small and kept unambiguous -------------


class TestAnUnambiguousGraphicsCardClaimIsDropped:
    """The script does have to work. Three claims where all three signals agree.

    Deliberately the smallest section in this file, and deliberately built from
    graphics-card vocabulary only — cards, coolers, VRAM, a GPU die. There is no
    chipset, no socket, no BIOS, no board family and no motherboard word anywhere in
    them, so none of the keep-rules has anything to catch.

    Nothing marginal is asserted in this direction on purpose. A test demanding that
    a borderline claim be DROPPED is pressure on the implementation to widen its
    match, and widening the match is exactly the failure the owner ruled against.
    """

    @pytest.mark.parametrize("candidate", UNAMBIGUOUS_GRAPHICS_CARD_CLAIMS, ids=claim_id)
    def test_a_graphics_card_claim_is_flagged(self, candidate: Mapping[str, Any]) -> None:
        assert_dropped(candidate, "All three signals agree that it is about a graphics card.")

    def test_the_predicate_answers_with_a_bool(self) -> None:
        """Both answers, and both of them an actual `bool`.

        The caller filters a list with this, and a truthy string or a match object
        would filter identically today and stop doing so the moment anyone wrote
        `verdict is True`. The declared return type is `bool`; this is the run-time
        half of that.
        """
        for candidate in (claim(), MOTHERBOARD_VIDEO_CLAIMS[0]):
            verdict = is_about_a_graphics_card(candidate)
            assert isinstance(verdict, bool), (
                f"the predicate answered {verdict!r} ({type(verdict).__name__}) for "
                f"{describe(candidate)}, not a bool"
            )


# --- purity --------------------------------------------------------------------


@pytest.fixture
def disk_access(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every file opened while this fixture is installed, recorded and allowed through.

    Recording rather than raising, on purpose: `builtins.open` is patched, and
    pytest renders a failing test's traceback through `linecache` before the
    monkeypatch is undone. A guard that raised would turn a real assertion failure
    into an unrelated explosion in the reporter.
    """
    touched: list[str] = []

    def record(name: str, real: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            touched.append(f"{name}{args[:1]!r}")
            return real(*args, **kwargs)

        return wrapper

    monkeypatch.setattr(builtins, "open", record("open", builtins.open))
    monkeypatch.setattr(os, "open", record("os.open", os.open))
    for method in ("open", "read_text", "read_bytes"):
        monkeypatch.setattr(Path, method, record(f"Path.{method}", getattr(Path, method)))
    return touched


class TestThePredicateIsPure:
    """One claim in, one bool out — no disk, no state, no mutation.

    A predicate that read a file would be a predicate whose answer depends on the
    machine it runs on, and the answer decides whether evidence is deleted. It
    would also make this whole file a test of a fixture directory rather than of a
    rule. `data/` is gitignored (R21) and empty on a clean checkout, so such a
    predicate would behave one way in CI and another on the owner's machine —
    which is precisely how ESC-29's claims got into the store unnoticed.
    """

    def test_deciding_a_claim_opens_no_files(self, disk_access: list[str]) -> None:
        candidate = claim()

        is_about_a_graphics_card(candidate)

        assert disk_access == [], (
            f"deciding {describe(candidate)} opened {disk_access}. The predicate's answer "
            "must depend on the claim alone; a file read makes the deletion depend on "
            "what happens to be on the machine."
        )

    @pytest.mark.parametrize(
        "candidate",
        (claim(), MOTHERBOARD_VIDEO_CLAIMS[0], KRAIT_CLAIMS[0]),
        ids=("graphics-card", "motherboard", "krait"),
    )
    def test_the_claim_is_not_modified(self, candidate: Mapping[str, Any]) -> None:
        """The caller keeps the claim it passed in — it is about to be rewritten to disk."""
        before = dict(candidate)

        is_about_a_graphics_card(candidate)

        assert dict(candidate) == before, (
            f"the predicate mutated the claim it was given: {describe(candidate)} — the "
            f"caller writes these rows back out, so a mutation here corrupts the store"
        )

    @pytest.mark.parametrize(
        "candidate",
        (claim(), MOTHERBOARD_VIDEO_CLAIMS[0], KRAIT_CLAIMS[0]),
        ids=("graphics-card", "motherboard", "krait"),
    )
    def test_the_same_claim_gets_the_same_answer_twice(self, candidate: Mapping[str, Any]) -> None:
        """No accumulated state: the tenth call and the first agree."""
        answers = {is_about_a_graphics_card(candidate) for _ in range(10)}

        assert len(answers) == 1, (
            f"the predicate gave more than one answer for the same claim: {answers} for "
            f"{describe(candidate)}, so something is being carried between calls"
        )


# --- the ceiling ---------------------------------------------------------------


def guard_returned(dropped: Sequence[Mapping[str, Any]], total: int) -> Any:
    """Whatever the guard hands back, read through the module object.

    The guard is bound at the top of this file as returning `None`, which is the
    contract mypy should enforce on every other caller — and which is exactly why
    mypy will not let its result be inspected. Going through the module here is how
    the run-time half of that contract gets asserted without weakening the declared
    type for everyone else.
    """
    unannotated: Any = _module.refuse_if_too_much_is_dropped
    return unannotated(dropped, total)


def dropped_claims(count: int) -> list[dict[str, Any]]:
    """`count` distinct claims, so the guard cannot be counting unique rows."""
    return [claim(video_id=f"drop{index:07d}") for index in range(count)]


# (number dropped, total, whether it must raise). The three fractions that matter
# are written out at two different totals, because 5/100 and 1/20 are the same
# fraction reached by different arithmetic and an off-by-one in a `>=` shows up at
# only one of them.
CEILING_CASES: tuple[tuple[int, int, bool], ...] = (
    (0, 100, False),
    (1, 100, False),
    (4, 100, False),
    (5, 100, False),
    (6, 100, True),
    (50, 1000, False),
    (51, 1000, True),
    (1, 20, False),
    (1, 19, True),
    (2, 20, True),
    (100, 100, True),
)

CEILING_IDS = tuple(
    f"{n}-of-{total}-{'refuses' if raises else 'passes'}" for n, total, raises in CEILING_CASES
)


class TestRefusingWhenTooMuchIsDropped:
    """Over-deletion has to fail LOUDLY, because otherwise it looks exactly like success.

    That is the entire point of this guard. A run that deleted half the store and a
    run that deleted the one GPU review print the same kind of line and exit the
    same way; the file is append-only, `data/` is gitignored, and there is no
    second copy to diff against. So the size of the deletion is checked before it is
    written, and a run that has gone wrong stops rather than reporting a number
    nobody reads.

    The boundary is `exceeds`, not `reaches`: 5 dropped out of 100 is exactly the
    ceiling and is allowed. That is asserted at 5/100, 50/1000 and 1/20 — the same
    fraction by three different divisions — because a guard written with `>=` is
    correct at none of them and a guard written with a rounded percentage is
    correct at some.
    """

    @pytest.mark.parametrize(("count", "total", "raises"), CEILING_CASES, ids=CEILING_IDS)
    def test_the_ceiling_is_exceeded_not_merely_reached(
        self, count: int, total: int, raises: bool
    ) -> None:
        dropped = dropped_claims(count)
        fraction = count / total

        if raises:
            with pytest.raises(RefusedToDrop):
                refuse_if_too_much_is_dropped(dropped, total)
        else:
            result = guard_returned(dropped, total)
            assert result is None, (
                f"the guard returned {result!r} for {count} of {total} ({fraction:.4f}), "
                f"but a guard that passes returns nothing"
            )

    def test_an_empty_store_does_not_divide_by_zero(self) -> None:
        """`total` of 0 is a store with nothing in it, not a deletion of everything.

        A first run against an empty `data/claims.jsonl` must report that there was
        nothing to do. A ZeroDivisionError here would be indistinguishable, from the
        outside, from the refusal this guard exists to raise.
        """
        assert guard_returned([], 0) is None, "the guard did not pass cleanly on an empty store"

    def test_a_zero_total_is_guarded_before_the_division_not_after(self) -> None:
        """The guard is on `total`, so a nonsensical pair still cannot divide by zero.

        Dropping three claims out of zero cannot happen, but "cannot happen" is what
        was said about a graphics-card review reaching the extractor. The guard's job
        is to be the thing that does not crash.
        """
        result = guard_returned(dropped_claims(3), 0)

        assert result is None, (
            f"the guard answered {result!r} for 3 dropped out of a total of 0; the zero "
            "check belongs before the division, whatever the numerator is"
        )

    def test_the_refusal_names_both_counts(self) -> None:
        """A refusal that says only "too many" leaves the reader to go and count.

        The message is the whole output of a failed run: the script has refused, so
        nothing was written and there is no report to read. It has to carry how many
        would have gone and out of how many, or the person deciding whether the run
        was right is guessing.
        """
        with pytest.raises(RefusedToDrop) as caught:
            refuse_if_too_much_is_dropped(dropped_claims(40), 100)

        message = str(caught.value)

        assert "40" in message, (
            f"the refusal does not say how many claims would have been dropped: {message!r}"
        )
        assert "100" in message, (
            f"the refusal does not say how many claims are in the store: {message!r}"
        )

    def test_the_refusal_is_raised_before_anything_is_written(self, disk_access: list[str]) -> None:
        """The guard decides; it does not clean up after a write.

        If it touched the store itself the refusal would be a rollback, and a
        rollback over an append-only file is a rewrite of evidence.
        """
        with pytest.raises(RefusedToDrop):
            refuse_if_too_much_is_dropped(dropped_claims(40), 100)

        assert disk_access == [], (
            f"the guard opened {disk_access} while deciding. It is asked BEFORE the store "
            "is rewritten, and a guard that writes has already done the thing it refuses."
        )
