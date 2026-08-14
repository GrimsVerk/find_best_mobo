"""Fold auto-caption damage out of text so part numbers survive matching.

YouTube's automatic captions do not know that `X670E` is one token. They render
it as `x 670 e`, `X-670-E`, or `x 6 70 e`, and any of those spellings can appear
twice in the same video. Matching raw caption text against a table of model
names therefore misses most of the mentions the corpus is selected on, which is
the recall risk `docs/DESIGN.md` R3 exists to contain.

`normalize` maps every one of those spellings onto a single string, so the alias
table and the transcript meet in the same space. Surface forms from the table
are normalized too — the caller never compares raw text with raw text.

The one rule worth stating twice: a hyphen is KEPT as a character, because it is
load-bearing in real board names (`x670e-plus`), but it never blocks the joining
rule, because a caption is just as likely to write `x-670-e` as `x 670 e`.
"""

from __future__ import annotations

import re

# The punctuation auto-captions scatter through speech, including the curly
# forms YouTube emits. Deleted rather than replaced with a space: `x670e.` and
# `don't` should become `x670e` and `dont`, not `x670e ` and `don t`.
_PUNCTUATION = str.maketrans(dict.fromkeys(".,!?:;\"'()[]‘’“”"))

_ALNUM = re.compile(r"[a-z0-9]+")

# Separators a mangled part number can be broken on. Anything else — a slash, an
# em dash, two spaces that survived collapsing — means the two sides are
# genuinely separate words.
_SEPARATORS = frozenset({" ", "-"})

# A purely alphabetic fragment joins to a number only when it is a single
# letter. This is what keeps `ryzen 9` and `in 2023` intact while still folding
# `x 670 e`: caption damage produces one-letter fragments, English produces
# words. Digit-to-digit joins (`x 6 70 e`) are capped at three digits a side so
# that ordinary adjacent numbers — `2023 2024` — are never welded together.
_MAX_SOFT_DIGITS = 3

# The two single letters that are ordinary English words. Without this, "a
# 7800X3D" folds into "a7800x3d" and then matches nothing at all, because the
# match is bounded on alphanumerics — the article silently costs a mention. The
# chipset spelled `a 620` is not lost by excluding them: surface forms are
# normalized by this same function, so `a 620` in the alias table and `a 620` in
# a caption still meet, they just meet unjoined.
_STANDALONE_WORDS = frozenset({"a", "i"})


def normalize(text: str) -> str:
    """Return `text` in the single space the matcher and the alias table share.

    Pure and total: it never raises, and `normalize("")` is `""`. Lowercases,
    drops scattered punctuation, collapses whitespace, and then joins up the
    letter/digit fragments a caption broke a part number into.
    """
    cleaned = " ".join(text.lower().translate(_PUNCTUATION).split())
    return _collapse_spacing(cleaned)


def _collapse_spacing(text: str) -> str:
    """Join runs of fragments that spell one alphanumeric token between them.

    Works on the whole string in one pass over its alphanumeric tokens: each gap
    between two tokens is classified once, runs of joinable gaps are then
    checked for at least one letter/digit transition, and the string is rebuilt.
    A run with no such transition is left alone — `1 2 3` is a list of numbers,
    not a mangled model name.
    """
    tokens = list(_ALNUM.finditer(text))
    if len(tokens) < 2:
        return text

    joined = [False] * (len(tokens) - 1)
    crosses_classes = [False] * (len(tokens) - 1)
    for i in range(len(tokens) - 1):
        left, right = tokens[i].group(), tokens[i + 1].group()
        gap = text[tokens[i].end() : tokens[i + 1].start()]
        if gap not in _SEPARATORS or not (_is_fragment(left) and _is_fragment(right)):
            continue
        if left[-1].isdigit() != right[0].isdigit():
            joined[i] = crosses_classes[i] = True
        elif _is_short_number(left) and _is_short_number(right):
            joined[i] = True

    _drop_runs_without_a_transition(joined, crosses_classes)

    parts = [text[: tokens[0].start()]]
    for i, token in enumerate(tokens):
        parts.append(token.group())
        if i + 1 < len(tokens):
            gap = text[token.end() : tokens[i + 1].start()]
            parts.append("" if joined[i] else gap)
    parts.append(text[tokens[-1].end() :])
    return "".join(parts)


def _drop_runs_without_a_transition(joined: list[bool], crosses_classes: list[bool]) -> None:
    """Un-join every maximal run of gaps that never changes letter/digit class.

    A run only spells a part number if letters and digits meet somewhere inside
    it. Without this, `9 7950x` — two separate numbers a sentence happened to
    put side by side — would weld into one.
    """
    start = 0
    while start < len(joined):
        if not joined[start]:
            start += 1
            continue
        end = start
        while end < len(joined) and joined[end]:
            end += 1
        if not any(crosses_classes[start:end]):
            for i in range(start, end):
                joined[i] = False
        start = end


def _is_fragment(token: str) -> bool:
    """Could this token be a piece of a broken-up part number?

    A single letter, a run of digits, or something already mixing the two. A
    multi-letter word never qualifies, which is the guard that keeps ordinary
    English — `ryzen 9`, `in 2023`, `8 gb` — out of the joining rule entirely.
    """
    if token.isdigit():
        return True
    if token.isalpha():
        return len(token) == 1 and token not in _STANDALONE_WORDS
    return True


def _is_short_number(token: str) -> bool:
    """A digit run small enough to be a caption fragment rather than a number."""
    return token.isdigit() and len(token) <= _MAX_SOFT_DIGITS
