"""The model boundary: the only module in this project that invokes one.

One bundle goes in, one claims file comes out on disk, and the four token counts
the call reported come back with it. Everything that spends money in this
pipeline happens inside `extract_bundle`, which is what makes the rest of the
tree testable offline — the same reason `ytdlp.py` is the only module that
touches the network, and this module is deliberately built to the same shape.

**The subscription pays, through `claude -p`** (`docs/DECISIONS.md`,
2026-08-25). The Anthropic API on a card was rejected for a specific reason
rather than on cost: R26 caps spend at 10% of the WEEKLY SUBSCRIPTION limits,
and an API call never moves that meter, so the guard slice 3 builds would read
the same healthy percentage before, during and after every batch. That ruling is
also why this module shells out at all, against the repository's usual
preference for libraries: the subscription is reachable only through the CLI.

**The four token components never become one number.** R8 as amended requires
fresh input, output, cache creation and cache read recorded separately, because
on the owner's machine cache reads outnumber fresh input by more than four
orders of magnitude — a summed total is dominated by the cheapest tokens in it
and says nothing about what a batch cost.

**The model's output is written to disk before it is parsed, always** (R27),
including when parsing then fails. The spend has already happened by then, and a
file that fails validation is the only record of what the model actually said.
Deleting it would destroy evidence of money that was spent.

**The prompt is a file** — `prompts/extract-claims.md`, tracked in git — and
`prompt_text` is the only way to reach it. R23's determinism claim needs the
prompt to be a versioned artifact: "the same bundle produces a comparable file
twice" stops being true the moment the prompt can change without a diff.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from find_best_mobo.artifacts import require_file
from find_best_mobo.claims import parse_claims
from find_best_mobo.config import Config

# The prompt lives beside the code it is used by, in the repository, not inside
# the package: it is a tracked artifact the owner reads and edits, and R23's
# comparability claim rests on it being diffable. Located from this file rather
# than from the working directory, because a prompt that changed depending on
# where the command was run from would make two batches incomparable without
# either of them recording why.
_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "extract-claims.md"

# Fixed by owner ruling (`docs/DESIGN.md` §6, and §7's "low effort, because this
# is reading comprehension, not reasoning"). A constant rather than a lever,
# unlike the model: the ruling settles it, and a config key would invite a
# silent change that the calibration record could not account for.
_EFFORT = "low"

# A bundle is at most `bundle_token_cap` of reading, so a call that has not
# answered in fifteen minutes is not slow, it is stuck. Without a timeout one
# wedged process strands the whole batch — including the eleven bundles already
# paid for, which is the waste R27 exists to prevent.
_TIMEOUT_SECONDS = 900


class ExtractionFailed(RuntimeError):
    """The call did not come back with something this stage can use.

    Distinct from `InvalidClaims`, and the distinction is load-bearing: an
    `InvalidClaims` file EXISTS on disk and can be read to see what the model
    said, while this says the call itself produced no such file. R9's "reported
    and retried or set aside" reads differently for the two, and slice 3 decides
    between them.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(self.message())

    def message(self) -> str:
        lines = [f"Extraction failed: {self.reason}"]
        if self.detail:
            lines.append(f"  {self.detail}")
        return "\n".join(lines)


@dataclass(frozen=True)
class ExtractionResult:
    """What one bundle's extraction produced, and what it cost.

    Four token counts, never a total. They are what slice 4's calibration record
    compares against the projection, and a summed figure could not be corrected
    back apart afterwards.
    """

    bundle_id: str
    claims_path: Path
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int


def prompt_text() -> str:
    """The extraction prompt, read from the repository.

    The only way to reach the prompt. Nothing else in the tree holds prompt text
    in a string literal, so a change to what the agent is asked shows up as a
    diff on one tracked file.

    Read on every call rather than cached at import: the cost is a few
    kilobytes, and a module-level read would run on `import find_best_mobo.extract`
    in a checkout that has no prompt, turning a missing artifact into a
    collection error rather than a message.
    """
    if not _PROMPT_PATH.is_file():
        raise FileNotFoundError(
            f"No extraction prompt at {_PROMPT_PATH}. It is a committed artifact, not a "
            "generated one: restore it from version control rather than writing a new one. "
            "A batch extracted with a different prompt is not comparable with the batches "
            "before it, and nothing on disk would record the difference (R23)."
        )
    return _PROMPT_PATH.read_text(encoding="utf-8")


def extract_bundle(bundle_path: Path, batch: int, config: Config) -> ExtractionResult:
    """Hand one bundle to the model and return the claims file it produced.

    The order of what follows is the whole point of the function. The output is
    written to disk the moment it exists, BEFORE anything is allowed to reject
    it (R27) — so a bundle that comes back malformed still leaves behind what
    the model said, and the spend is not lost twice over.

    Validation happens here rather than being left to `ingest`, because R9's
    choice — retry or set aside — is made where the spend happened and where the
    bundle is still identified. A result this function returns is a file
    `ingest` will accept; `InvalidClaims` is how it says otherwise, and the file
    named in that error is on disk to be looked at.
    """
    bundle = require_file(bundle_path, "bundle", "estimate").read_text(encoding="utf-8")
    payload = _invoke(prompt_text(), bundle, config.extraction_model)

    text = _model_text(payload)
    claims_path = _claims_path(bundle_path, batch, config)
    _write(claims_path, text)

    _refuse_on_error(payload, claims_path)
    usage = _token_counts(payload, claims_path)
    # The parsed claims are deliberately discarded: `ingest` re-reads the file,
    # so the store's evidence always comes from what is on disk rather than from
    # something held in memory here that nobody could inspect afterwards.
    parse_claims(text, claims_path, batch)
    return ExtractionResult(
        bundle_id=bundle_path.stem,
        claims_path=claims_path,
        input_tokens=usage[0],
        output_tokens=usage[1],
        cache_creation_tokens=usage[2],
        cache_read_tokens=usage[3],
    )


def _invoke(prompt: str, bundle: str, model: str) -> Mapping[str, Any]:
    """Run one `claude -p` call and return the envelope it printed.

    The prompt goes in as the argument and the bundle on standard input — the
    plain `cat thing | claude -p "instructions"` shape — so that a bundle
    approaching the token cap never has to fit in an argument list.

    `--output-format json` is what makes R8 possible at all: it is the only
    output mode that reports the four token counts alongside the answer.
    `--json-schema` is deliberately NOT used, although the CLI offers it: BL-23
    rules that Python validates and the agent is never trusted to self-check,
    and a schema enforced inside the call would turn a misunderstood contract
    into a silent internal retry that this project pays for and cannot see.
    """
    if not model.strip():
        # Refused before the call, not after: this is the one failure that costs
        # nothing to prevent and a whole batch to discover late.
        raise ExtractionFailed(
            "no extraction model is configured",
            "Set `extraction_model` in config.toml. There is no default in code on purpose: a "
            "chars-per-token factor measured against one model does not transfer to another, so "
            "a calibration record that cannot name its model is not evidence.",
        )
    command = [
        "claude",
        "-p",
        "--output-format",
        "json",
        "--model",
        model,
        "--effort",
        _EFFORT,
        prompt,
    ]
    raw = _stdout_of(_extraction_client().run(command, bundle))
    try:
        payload: Any = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ExtractionFailed(
            f"`claude -p --output-format json` did not print JSON: {error}", _excerpt(raw)
        ) from error
    if not isinstance(payload, dict):
        raise ExtractionFailed(
            f"`claude -p` printed {type(payload).__name__}, expected the result envelope",
            _excerpt(raw),
        )
    return payload


def _model_text(payload: Mapping[str, Any]) -> str:
    """The model's own output, out of the CLI's envelope.

    The envelope is the tool's and the `result` is the model's, and only the
    second is worth keeping. An envelope with no `result` means the call never
    reached a model, so there is nothing to write down and nothing was said.
    """
    text = payload.get("result")
    if not isinstance(text, str):
        raise ExtractionFailed(
            "the call came back with no result text",
            f"subtype {payload.get('subtype', 'unknown')!r}; nothing was written, because "
            "there is no model output to record.",
        )
    return text


def _refuse_on_error(payload: Mapping[str, Any], claims_path: Path) -> None:
    """A turn the CLI marked as an error, checked only after its text is safe.

    Deliberately after the write: an errored turn still spent tokens and still
    produced text, and that text is the evidence of what went wrong.
    """
    if payload.get("is_error"):
        raise ExtractionFailed(
            f"the model's turn ended in an error ({payload.get('subtype', 'unknown')})",
            f"What it did say was written to {claims_path} and is not deleted (R27).",
        )


# The four components, each under every name the CLI is known to report it by.
# Claude Code mirrors the API's `cache_creation_input_tokens` naming; reading
# only one spelling would record a real cache read as zero, which is precisely
# the number R8 was amended to protect. Because every known name is looked
# under, an absent key really does mean a counter that never moved, and reads as
# nought rather than as a failure.
_INPUT_NAMES = ("input_tokens",)
_OUTPUT_NAMES = ("output_tokens",)
_CACHE_CREATION_NAMES = ("cache_creation_input_tokens", "cache_creation_tokens")
_CACHE_READ_NAMES = ("cache_read_input_tokens", "cache_read_tokens")


def _token_counts(payload: Mapping[str, Any], claims_path: Path) -> tuple[int, int, int, int]:
    """Fresh input, output, cache creation and cache read — four, never summed."""
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        raise ExtractionFailed(
            "the call reported no token usage",
            f"The output is at {claims_path}, but a spend nobody can measure cannot be "
            "calibrated against the projection (R8), and the batch total would understate it.",
        )
    return (
        _count(usage, _INPUT_NAMES),
        _count(usage, _OUTPUT_NAMES),
        _count(usage, _CACHE_CREATION_NAMES),
        _count(usage, _CACHE_READ_NAMES),
    )


def _count(usage: Mapping[str, Any], names: Sequence[str]) -> int:
    """One counter's value, or zero if the call never moved it.

    `bool` is excluded explicitly because it is an `int` in Python, and `True`
    would otherwise be recorded as one token.
    """
    for name in names:
        if name in usage:
            value = usage[name]
            if isinstance(value, bool) or not isinstance(value, int):
                raise ExtractionFailed(
                    f"usage.{name} is {type(value).__name__}, expected a count of tokens"
                )
            return value
    return 0


def _claims_path(bundle_path: Path, batch: int, config: Config) -> Path:
    """`data/claims/batch-N/<bundle_id>.json`, mirroring where the bundle came from.

    A directory per batch, like `data/bundles/`, because the batch is the unit
    the owner acts on. The append-only store is `data/claims.jsonl` and these are
    not it: these are what the model said, unvalidated, one file per bundle, and
    they stay on disk whether or not the store ever accepted them.
    """
    return config.data_dir / "claims" / f"batch-{batch}" / f"{bundle_path.stem}.json"


def _write(path: Path, text: str) -> None:
    """Put the model's output on disk now, verbatim, and make sure it stays there.

    Verbatim: not stripped, not unfenced, not repaired. A file this stage tidied
    up would no longer be evidence of what the model said, and the fault that
    tidying hid is the fault the prompt needs to fix.

    Flushed and fsynced for the same reason `claimstore` does it — this run is
    one a spend guard may stop mid-batch (R26), and R27's promise is about work
    that survives the stop.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())


def _excerpt(raw: str, limit: int = 400) -> str:
    """As much of an unusable output as a person needs to recognise it.

    Whole would be a bundle-sized wall of text in a terminal; nothing is what
    made the failure unreadable in the first place.
    """
    text = raw.strip()
    return text if len(text) <= limit else f"{text[:limit]}... ({len(text)} characters)"


class ClaudeCli:
    """The `claude -p` process. The only thing in this project that spends money.

    A thin wrapper on one subprocess call, kept as a class so that the seam
    below has an object to hold — the same shape `ytdlp.py` gives `YoutubeDL`,
    and the shape a test fakes.

    A non-zero exit is raised rather than parsed: the CLI failing to run is a
    different fact from a model answering badly, and only the second leaves
    something on disk worth reading.
    """

    def run(self, command: Sequence[str], stdin_text: str) -> str:
        """Run `command` with `stdin_text` on standard input, returning stdout."""
        try:
            completed = subprocess.run(
                list(command),
                input=stdin_text,
                capture_output=True,
                text=True,
                timeout=_TIMEOUT_SECONDS,
                check=False,
            )
        except FileNotFoundError as error:
            raise ExtractionFailed(
                "`claude` is not on PATH",
                "The subscription is reached through the Claude Code CLI, and there is no "
                "API-key path to fall back to by design (docs/DECISIONS.md, 2026-08-25).",
            ) from error
        except subprocess.TimeoutExpired as error:
            raise ExtractionFailed(
                f"`claude` did not answer within {_TIMEOUT_SECONDS} seconds"
            ) from error
        if completed.returncode != 0:
            raise ExtractionFailed(
                f"`claude` exited {completed.returncode}", _excerpt(completed.stderr)
            )
        return completed.stdout


# One client for every extraction in a run, built on first use.
#
# THE seam, and the only one: no test in this slice invokes a model, and the
# suite must run offline, free, and identically on a machine with no
# subscription at all. A test replaces this object (or `ClaudeCli` itself, after
# clearing this back to None) and nothing else in the tree has to change.
#
# Built lazily rather than at import so that merely importing this module starts
# no process, which is what keeps an offline suite honest — the same reason
# `ytdlp._CAPTION_CLIENT` is built lazily.
def _stdout_of(reply: Any) -> str:
    """The seam's answer as text, whichever shape the client returned it in.

    `ClaudeCli.run` returns stdout already. The seam exists so a caller can
    substitute its own client, and the two obvious substitutes are a client
    that returns the completed process and one that returns its output — so
    both are read here rather than one being declared correct by annotation.
    Nothing is inferred beyond that: whatever comes back still has to parse as
    the result envelope, so a client answering some third way fails loudly at
    the parse rather than quietly here.
    """
    stdout = getattr(reply, "stdout", None)
    return stdout if isinstance(stdout, str) else str(reply)


_EXTRACTION_CLIENT: Any = None


def _extraction_client() -> Any:
    """The shared `claude -p` runner, created once per process."""
    global _EXTRACTION_CLIENT
    if _EXTRACTION_CLIENT is None:
        _EXTRACTION_CLIENT = ClaudeCli()
    return _EXTRACTION_CLIENT
