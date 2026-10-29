"""Stage B slice 2 — one bundle in, one claims file out, and what it cost.

Written blind from `docs/plans/oracle/stage-b-extraction.md` (slice 2) and its
Signatures block alone, while the implementation is authored in parallel, so
failing imports are the expected state until assembly — exactly as
`tests/test_transcripts.py` and `tests/test_claims.py` say of their own slices.

**Nothing here invokes a model, and nothing here can.** `conftest.py` already
fails any test that opens a socket; this file additionally replaces every route
out of the process that `claude -p` could take, so a test that reached a real
subscription would have to invent a new one. Two assumptions about the seam,
both taken from the plan's "Structured like ytdlp.py ... one seam":

- **A lazily built module-level client**, the shape `ytdlp._CAPTION_CLIENT` has
  and `tests/test_ytdlp_client_reuse.py` patches: a private, upper-case,
  `None`-at-import module attribute. Its NAME is not in the Signatures block, so
  `_seam_name` discovers it rather than guessing one spelling, and says what it
  looked for when it finds nothing.
- **`subprocess`**, because the owner's 2026-08-25 ruling is that the
  subscription pays through `claude -p` and there is no library behind that.

Both are faked at once, so the request is recorded whichever route it takes. The
fake's answer is deliberately promiscuous about shape — a dict of the envelope
`claude -p --output-format json` returns, whose keys are also attributes, whose
`stdout` is that envelope re-encoded, and whose `str()` is the model's text —
because the shape of the seam's RETURN is not in the contract either. The
usage numbers carry both spellings of the two cache fields for the same reason.

What is NOT assumed: that the model writes the claims file itself. The plan says
"the result is written to disk before it is parsed", which puts the writing in
Python, on this side of the seam, and the fake writes nothing at all so that a
test asserting the file exists is asserting something about the implementation.
"""

# ruff: noqa: I001
# Import sorting is switched off for this file on purpose, exactly as it is in
# tests/test_claims.py and tests/test_json3_captions.py: `find_best_mobo.extract`
# does not exist yet, so the isort rule classifies it as third-party and would
# demand a different grouping from the one it demands once it does. The block is
# written in its post-assembly order, which is the stable one.
from __future__ import annotations

import dataclasses
import inspect
import io
import json
import re
import subprocess
from collections.abc import Callable, Iterator, Mapping
from dataclasses import FrozenInstanceError, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from find_best_mobo import claims as claims_module
from find_best_mobo import extract
from find_best_mobo.bundle import Bundle, render_bundle
from find_best_mobo.claims import CATEGORIES, POLARITIES, SUBJECTS, Claim, InvalidClaims
from find_best_mobo.config import Config, load_config
from find_best_mobo.excerpt import Excerpt
from find_best_mobo.extract import (
    ExtractionFailed,
    ExtractionResult,
    extract_bundle,
    prompt_text,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = REPO_ROOT / "prompts" / "extract-claims.md"

# The six fields the plan's Signatures block declares, in its order. Pinned as a
# literal rather than derived, because deriving them from the class under test
# would let a seventh field — `total_tokens`, say — arrive unnoticed, and a
# single total is the one thing R8 as amended forbids.
RESULT_FIELDS: tuple[str, ...] = (
    "bundle_id",
    "claims_path",
    "input_tokens",
    "output_tokens",
    "cache_creation_tokens",
    "cache_read_tokens",
)

# The eight fields a claims FILE carries, derived from slice 1's dataclass so
# the prompt is checked against the schema that actually validates it rather
# than against a copy of it here. `batch` is the ninth field of `Claim` and is
# not one of them: the ingest supplies it, and a file that named it would be
# refused for an unknown key.
FILE_FIELDS: tuple[str, ...] = tuple(f.name for f in dataclasses.fields(Claim) if f.name != "batch")

VOCABULARY: tuple[str, ...] = CATEGORIES + SUBJECTS + POLARITIES

# Four token components, all distinct, none the sum or difference of any other
# two, and in the proportions the plan cites as the reason they stay apart — on
# the owner's machine cache reads outnumber fresh input by more than four orders
# of magnitude, so a summed figure would be dominated by the cheapest tokens.
INPUT_TOKENS = 1103
OUTPUT_TOKENS = 417
CACHE_CREATION_TOKENS = 25811
CACHE_READ_TOKENS = 9402133
TOTAL_TOKENS = INPUT_TOKENS + OUTPUT_TOKENS + CACHE_CREATION_TOKENS + CACHE_READ_TOKENS

USAGE: dict[str, int] = {
    # Claude Code's own spellings...
    "input_tokens": INPUT_TOKENS,
    "output_tokens": OUTPUT_TOKENS,
    "cache_creation_input_tokens": CACHE_CREATION_TOKENS,
    "cache_read_input_tokens": CACHE_READ_TOKENS,
    # ...and `ExtractionResult`'s, so the fake answers either reader.
    "cache_creation_tokens": CACHE_CREATION_TOKENS,
    "cache_read_tokens": CACHE_READ_TOKENS,
}

# Two configured models. Distinctive strings, so finding one in the request is
# not a coincidence and finding the other is a defect.
MODEL_A = "claude-test-alpha-9971"
MODEL_B = "claude-test-bravo-3344"

BUNDLE_ID = "bundle-007"

# The bundle the tests hand over, built through the real renderer so the file on
# disk is the file Stage A actually writes. The words are invented (R21).
EXCERPTS: tuple[Excerpt, ...] = (
    Excerpt(
        video_id="dQw4w9WgXcQ",
        video_title="Quorvex B940 VRM breakdown",
        start_seconds=61.0,
        end_seconds=361.0,
        text=(
            "the Quorvex B940 runs a genuine twelve phase and it holds "
            "an all core load without the vcore drooping at all"
        ),
        canonicals=("Quorvex B940",),
    ),
    Excerpt(
        video_id="oHg5SJYRHA0",
        video_title="Zendrel X9 firmware warning",
        start_seconds=900.0,
        end_seconds=1200.0,
        text="do not run the Zendrel X9 on its stock firmware, it will cook the chip",
        canonicals=("Zendrel X9",),
    ),
)

# The claims the faked model answers with. Every row is schema-valid, so a test
# that fails is failing about extraction rather than about slice 1.
CLAIM_ROWS: tuple[dict[str, object], ...] = (
    {
        "board": "Quorvex B940",
        "video_id": "dQw4w9WgXcQ",
        "video_title": "Quorvex B940 VRM breakdown",
        "timestamp_seconds": 61.0,
        "snippet": "runs a genuine twelve phase",
        "category": "tested",
        "subject": "vrm_capacity",
        "polarity": "positive",
    },
    {
        "board": "Zendrel X9",
        "video_id": "oHg5SJYRHA0",
        "video_title": "Zendrel X9 firmware warning",
        "timestamp_seconds": 900.0,
        "snippet": "do not run the Zendrel X9 on its stock firmware",
        "category": "warning",
        "subject": "voltage_firmware_safety",
        "polarity": "negative",
    },
)

# Indented by four, which no `json.dumps` default and no re-serialisation in
# this repository produces: a claims file written back out rather than kept as
# it arrived would not match this byte for byte, and R27 wants the bytes.
MODEL_REPLY = json.dumps(list(CLAIM_ROWS), indent=4)

# A reply the schema refuses, and one that is not JSON at all. Both are what a
# real model produces on a bad day, and both are evidence of a spend that has
# already happened.
INVALID_REPLY = json.dumps(
    [dict(CLAIM_ROWS[0]) | {"category": "Tested", "confidence": 0.8}], indent=4
)
UNPARSEABLE_REPLY = "I read the bundle but could not find anything worth quoting.\n"


# --------------------------------------------------------------------------
# The bundle on disk, and the configuration that points at it.
# --------------------------------------------------------------------------

_CONFIG_VALUES: dict[str, Any] = {
    "channel_url": "https://www.youtube.com/@test",
    "start_date": date(2023, 1, 1),
    "shorts_max_seconds": 120,
    "mention_threshold": 3,
    "window_before_seconds": 120,
    "window_after_seconds": 300,
    "per_video_excerpt_cap": 10,
    "bundle_token_cap": 24000,
    "calibration_batch_size": 12,
    "batch_count": 3,
    "chars_per_token": 4.0,
    "consecutive_fetch_error_limit": 3,
    "fetch_error_rate_limit": 0.03,
    "missing_caption_rate_limit": 0.05,
    "extraction_model": MODEL_A,
}


def config_fields() -> frozenset[str]:
    return frozenset(f.name for f in dataclasses.fields(Config))


def make_config(tmp_path: Path, **overrides: Any) -> Config:
    """A `Config` pointing at `tmp_path`, carrying only fields `Config` declares.

    `extraction_model` is filtered out rather than forced, so the rest of this
    file still exercises extraction on a build where the plan's configured model
    landed somewhere other than `Config`. The tests that are ABOUT the model say
    so directly instead.
    """
    values = dict(_CONFIG_VALUES) | {"data_dir": tmp_path / "data"} | overrides
    declared = config_fields()
    return Config(**{name: value for name, value in values.items() if name in declared})


def write_bundle(tmp_path: Path, batch: int = 1, bundle_id: str = BUNDLE_ID) -> Path:
    """Render one real bundle to `data/bundles/batch-N/`, and hand back its path."""
    bundle = Bundle(
        bundle_id=bundle_id,
        batch=batch,
        excerpts=EXCERPTS,
        projected_tokens=512,
    )
    directory = tmp_path / "data" / "bundles" / f"batch-{batch}"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{bundle_id}.xml"
    path.write_text(render_bundle(bundle), encoding="utf-8")
    return path


def outputs(config: Config) -> list[Path]:
    """Every file the run left in the cache directory that is not a bundle.

    Used where the claims path cannot be read off a returned result — the run
    that fails to parse raises instead of returning — so that "the file is still
    there" is asserted without assuming the layout the implementation chose.
    """
    root = config.data_dir
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix != ".xml")


# --------------------------------------------------------------------------
# The seam.
# --------------------------------------------------------------------------


@dataclass
class Call:
    """One thing the extraction sent outwards, and where it tried to send it."""

    where: str
    args: tuple[Any, ...]
    kwargs: dict[str, Any] = field(default_factory=dict)

    def payload(self) -> tuple[str, ...]:
        """Every string in the call, flattened — the request as a test can see it."""
        found: list[str] = []
        _texts(self.args, found)
        _texts(self.kwargs, found)
        return tuple(found)


def _texts(value: object, out: list[str]) -> None:
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, bytes):
        out.append(value.decode("utf-8", errors="replace"))
    elif isinstance(value, Path):
        out.append(str(value))
    elif isinstance(value, Mapping):
        for key, item in value.items():
            _texts(key, out)
            _texts(item, out)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            _texts(item, out)
    else:
        out.append(repr(value))


class Reply(dict[str, Any]):
    """What the faked model hands back, shaped for every plausible reader.

    A mapping of the envelope `claude -p --output-format json` prints, whose
    keys are also attributes, whose `stdout` is that envelope re-encoded for a
    caller that parses a completed process, and whose `str()` is the model's
    text for a caller that expects the seam to return prose.
    """

    def __init__(self, text: str) -> None:
        envelope: dict[str, Any] = {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": text,
            "usage": dict(USAGE),
            **USAGE,
        }
        super().__init__(envelope)
        self.__dict__.update(envelope)
        self.text = text
        self.content = text
        self.claims = text
        self.stdout = json.dumps(envelope)
        self.stderr = ""
        self.returncode = 0

    def __str__(self) -> str:
        return self.text

    def read(self) -> str:
        return self.stdout


class FakeModel:
    """Every route to a model, recorded, with one canned answer for all of them."""

    def __init__(self) -> None:
        self.calls: list[Call] = []
        self.reply = MODEL_REPLY
        self.seam = "none"

    def record(self, where: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Reply:
        self.calls.append(Call(where=where, args=args, kwargs=kwargs))
        return Reply(self.reply)

    @property
    def sent(self) -> str:
        """Everything the extraction sent, joined — the haystack for assertions."""
        return "\n".join(text for call in self.calls for text in call.payload())

    def requests(self) -> list[tuple[str, tuple[str, ...]]]:
        """The calls reduced to what determinism is about: where, and what strings."""
        return [(call.where, call.payload()) for call in self.calls]


class FakeClient:
    """A stand-in for the lazily built client, answering to any method name."""

    def __init__(self, model: FakeModel) -> None:
        self._model = model

    def __call__(self, *args: Any, **kwargs: Any) -> Reply:
        return self._model.record("client()", args, kwargs)

    def __getattr__(self, name: str) -> Callable[..., Reply]:
        if name.startswith("__"):
            raise AttributeError(name)

        def method(*args: Any, **kwargs: Any) -> Reply:
            return self._model.record(f"client.{name}", args, kwargs)

        return method


class FakePopen:
    """`subprocess.Popen`, for an implementation that streams rather than runs."""

    def __init__(self, model: FakeModel, *args: Any, **kwargs: Any) -> None:
        self._reply = model.record("subprocess.Popen", args, kwargs)
        self.returncode = 0
        self.stdout = io.StringIO(self._reply.stdout)
        self.stderr = io.StringIO("")
        self.args = args[0] if args else kwargs.get("args")

    def communicate(self, input: Any = None, timeout: Any = None) -> tuple[str, str]:
        return self._reply.stdout, ""

    def wait(self, timeout: Any = None) -> int:
        return 0

    def poll(self) -> int:
        return 0

    def __enter__(self) -> FakePopen:
        return self

    def __exit__(self, *_: object) -> None:
        return None


_SEAM_WORDS = ("CLIENT", "MODEL", "AGENT", "RUNNER", "SESSION", "CLAUDE")


def _client_candidates() -> list[str]:
    """Every module attribute that is spelled the way a held client is spelled.

    Narrower than `_SEAM_WORDS` deliberately — only `CLIENT` — because this list
    is also what the import test asserts is empty-handed, and a constant called
    `_MODEL_FLAG` is not a client.
    """
    return sorted(
        name
        for name in vars(extract)
        if name.startswith("_") and name.isupper() and "CLIENT" in name
    )


def _seam_name() -> str | None:
    """The name of `extract`'s lazily built client, the way `ytdlp` names its own.

    `ytdlp._CAPTION_CLIENT` is a private, upper-case module attribute that is
    `None` until first use, and that triple is specific enough to find without
    guessing the spelling of a name the Signatures block never gave. A client
    that is already built is still patched — that it was built at import is a
    defect of its own, and `test_importing_the_module_starts_no_session` is
    where it is reported rather than here, as a cascade of unrelated failures.
    """
    lazy = sorted(
        name
        for name, value in vars(extract).items()
        if name.startswith("_")
        and name.isupper()
        and value is None
        and any(word in name for word in _SEAM_WORDS)
    )
    if lazy:
        return lazy[0]
    eager = _client_candidates()
    return eager[0] if eager else None


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> FakeModel:
    """Close every door out of the process, and record what tries to leave."""
    fake = FakeModel()

    seam = _seam_name()
    if seam is not None:
        fake.seam = seam
        monkeypatch.setattr(extract, seam, FakeClient(fake))

    def fake_run(*args: Any, **kwargs: Any) -> Reply:
        return fake.record("subprocess.run", args, kwargs)

    def fake_check_output(*args: Any, **kwargs: Any) -> str:
        return fake.record("subprocess.check_output", args, kwargs).stdout

    def fake_popen(*args: Any, **kwargs: Any) -> FakePopen:
        return FakePopen(fake, *args, **kwargs)

    replacements: dict[Any, Any] = {
        subprocess.run: fake_run,
        subprocess.check_output: fake_check_output,
        subprocess.Popen: fake_popen,
    }
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    # `from subprocess import run` binds a second name; patching the module
    # alone would leave that one pointing at the real thing.
    for name, value in list(vars(extract).items()):
        for real, replacement in replacements.items():
            if value is real:
                monkeypatch.setattr(extract, name, replacement)
    return fake


@dataclass
class ParseCall:
    """One call to slice 1's parser, and what the disk looked like when it ran."""

    raw: str
    path: Path
    batch: int
    output_existed: bool


class ParseWatch:
    def __init__(self) -> None:
        self.calls: list[ParseCall] = []

    @property
    def only(self) -> ParseCall:
        assert len(self.calls) == 1, f"expected one parse, got {len(self.calls)}"
        return self.calls[0]


@pytest.fixture
def parses(monkeypatch: pytest.MonkeyPatch) -> ParseWatch:
    """Watch `parse_claims` — what it was handed, and whether the file was there.

    Patched under both names because `from find_best_mobo.claims import
    parse_claims` binds a copy in `extract` that patching the claims module
    would not reach.
    """
    watch = ParseWatch()
    real = claims_module.parse_claims

    def spy(raw: str, path: Path, batch: int) -> tuple[Claim, ...]:
        watch.calls.append(
            ParseCall(raw=raw, path=Path(path), batch=batch, output_existed=Path(path).is_file())
        )
        return real(raw, path, batch)

    monkeypatch.setattr(claims_module, "parse_claims", spy)
    if hasattr(extract, "parse_claims"):
        monkeypatch.setattr(extract, "parse_claims", spy)
    return watch


def _forget_prompt() -> None:
    """Drop any memoisation on `prompt_text`, so the next call re-reads the disk."""
    clear = getattr(prompt_text, "cache_clear", None)
    if callable(clear):
        clear()
    clear = getattr(getattr(extract, "prompt_text", None), "cache_clear", None)
    if callable(clear):
        clear()


@pytest.fixture
def rewrite_prompt() -> Iterator[Callable[[str], str]]:
    """Put different words in the prompt file, and put the real ones back after.

    The only way to prove `prompt_text` reads a FILE: the function takes no
    arguments, so a literal and a read are indistinguishable until the file
    underneath changes.
    """
    original = PROMPT_PATH.read_bytes()

    def rewrite(text: str) -> str:
        PROMPT_PATH.write_text(text, encoding="utf-8")
        _forget_prompt()
        return text

    try:
        yield rewrite
    finally:
        PROMPT_PATH.write_bytes(original)
        _forget_prompt()


def refusal(bundle_path: Path, batch: int, config: Config) -> InvalidClaims:
    """Extract a bundle whose output must be refused, and hand back the refusal."""
    with pytest.raises(InvalidClaims) as caught:
        extract_bundle(bundle_path, batch, config)
    return caught.value


# --------------------------------------------------------------------------
# The prompt is a file.
# --------------------------------------------------------------------------


class TestThePromptIsAFile:
    """R23 needs the prompt to be a versioned artifact, reachable one way only.

    "The same bundle produces a comparable file twice" is false the moment the
    prompt can change without a diff, and a prompt inlined in `extract.py` is a
    prompt whose changes hide inside a code review of something else.
    """

    def test_the_prompt_file_is_in_the_repository(self) -> None:
        assert PROMPT_PATH.is_file(), f"the plan's Files list names {PROMPT_PATH}"

    def test_the_prompt_file_is_not_empty(self) -> None:
        assert PROMPT_PATH.read_text(encoding="utf-8").strip()

    def test_prompt_text_is_exactly_the_file_on_disk(self) -> None:
        assert prompt_text() == PROMPT_PATH.read_text(encoding="utf-8")

    def test_prompt_text_is_the_same_twice(self) -> None:
        assert prompt_text() == prompt_text()

    def test_a_changed_file_changes_prompt_text(self, rewrite_prompt: Callable[[str], str]) -> None:
        rewritten = rewrite_prompt("# a different instruction entirely\n")

        assert prompt_text() == rewritten

    def test_a_changed_file_changes_what_is_sent(
        self, model: FakeModel, rewrite_prompt: Callable[[str], str], tmp_path: Path
    ) -> None:
        marker = "SENTINEL-PROMPT-b41d9c"
        rewrite_prompt(f"# {marker}\nWrite the claims as JSON.\n")

        extract_bundle(write_bundle(tmp_path), 1, make_config(tmp_path))

        assert marker in model.sent, (
            "the prompt reached the model as a literal rather than as the file: "
            "rewriting prompts/extract-claims.md changed nothing about the request"
        )

    def test_the_module_does_not_carry_the_prompt_as_a_literal(self) -> None:
        source = inspect.getsource(extract)
        substantial = [
            line.strip()
            for line in PROMPT_PATH.read_text(encoding="utf-8").splitlines()
            if len(line.strip()) > 40
        ]
        assert substantial, "the prompt has no line long enough to look for"
        for line in substantial:
            assert line not in source, f"extract.py inlines a line of the prompt: {line!r}"


class TestThePromptFitsTheSchema:
    """The prompt must make `claims.py`'s file producible — no more, no less.

    Slice 1 refuses a capitalised category and refuses an invented field, so a
    prompt that spelled a vocabulary differently or asked for one extra key
    would buy a batch of files that Python then throws away. No runtime test can
    see that drift; this one reads both sides and compares them.
    """

    @pytest.fixture
    def prompt(self) -> str:
        return PROMPT_PATH.read_text(encoding="utf-8")

    @pytest.mark.parametrize("term", VOCABULARY)
    def test_the_prompt_names_every_vocabulary_term(self, prompt: str, term: str) -> None:
        assert term in prompt, (
            f"claims.py accepts {term!r} and the prompt never says it — "
            "case included, because the schema treats case as part of the value"
        )

    @pytest.mark.parametrize("name", FILE_FIELDS)
    def test_the_prompt_names_every_required_field(self, prompt: str, name: str) -> None:
        assert name in prompt, f"every claim needs {name!r} and the prompt never asks for it"

    def test_the_prompt_never_asks_for_the_batch(self, prompt: str) -> None:
        """`batch` is a fact about the run. A file naming it is refused outright."""
        assert '"batch"' not in prompt

    def test_every_key_the_prompt_names_is_one_the_schema_knows(self, prompt: str) -> None:
        """A model that invents `confidence` misunderstood the contract — but so
        did the prompt that asked for it, and slice 1 refuses the file either way.

        The vocabulary values are subtracted before comparing, because a prompt
        that defines its terms as `"tested": he measured it` is quoting a VALUE
        in the same shape a JSON key takes, and that is not an invented field.
        """
        named = set(re.findall(r'"([A-Za-z_][A-Za-z0-9_]*)"\s*:', prompt))
        invented = sorted(named - set(FILE_FIELDS) - set(VOCABULARY))
        assert not invented, f"the prompt asks for {invented}, which slice 1 refuses"

    def test_the_prompt_shows_an_example_the_schema_accepts(self, prompt: str) -> None:
        """A worked example is the part of a prompt a model actually copies."""
        candidates = _json_arrays(prompt)
        assert candidates, "the prompt shows no example of the JSON array it demands"
        accepted = []
        for candidate in candidates:
            try:
                accepted.append(claims_module.parse_claims(candidate, PROMPT_PATH, 1))
            except InvalidClaims:
                continue
        assert accepted, (
            "no example in the prompt survives claims.parse_claims — the prompt "
            "and the schema have drifted apart"
        )


_FENCED = re.compile(r"```[A-Za-z0-9]*\n(.*?)```", re.DOTALL)
_BARE_ARRAY = re.compile(r"\[\s*\{.*?\}\s*\]", re.DOTALL)


def _json_arrays(text: str) -> list[str]:
    """Every JSON array the prompt shows, fenced or bare."""
    fenced = [block.strip() for block in _FENCED.findall(text)]
    arrays = [block for block in fenced if block.startswith("[")]
    return arrays or [match.group(0) for match in _BARE_ARRAY.finditer(text)]


# --------------------------------------------------------------------------
# What crosses the seam.
# --------------------------------------------------------------------------


class TestWhatIsSentToTheModel:
    def test_the_prompt_is_sent(self, model: FakeModel, tmp_path: Path) -> None:
        extract_bundle(write_bundle(tmp_path), 1, make_config(tmp_path))

        assert prompt_text().strip() in model.sent

    def test_the_bundle_is_sent(self, model: FakeModel, tmp_path: Path) -> None:
        """Either the XML itself or the path to it — the model must be able to read it."""
        bundle_path = write_bundle(tmp_path)

        extract_bundle(bundle_path, 1, make_config(tmp_path))

        sent = model.sent
        assert EXCERPTS[0].text in sent or str(bundle_path) in sent, (
            "neither the bundle's text nor its path reached the model"
        )

    def test_one_bundle_is_one_call(self, model: FakeModel, tmp_path: Path) -> None:
        extract_bundle(write_bundle(tmp_path), 1, make_config(tmp_path))

        assert len(model.calls) == 1, f"one bundle, one call; it made {model.requests()}"

    def test_the_bundle_file_is_left_exactly_as_it_was(
        self, model: FakeModel, tmp_path: Path
    ) -> None:
        bundle_path = write_bundle(tmp_path)
        before = bundle_path.read_bytes()

        extract_bundle(bundle_path, 1, make_config(tmp_path))

        assert bundle_path.read_bytes() == before


# --------------------------------------------------------------------------
# What comes back.
# --------------------------------------------------------------------------


class TestTheResult:
    @pytest.fixture
    def result(self, model: FakeModel, tmp_path: Path) -> ExtractionResult:
        return extract_bundle(write_bundle(tmp_path), 1, make_config(tmp_path))

    def test_the_result_declares_exactly_the_six_fields(self) -> None:
        assert tuple(f.name for f in dataclasses.fields(ExtractionResult)) == RESULT_FIELDS

    def test_the_result_is_frozen(self, result: ExtractionResult) -> None:
        with pytest.raises(FrozenInstanceError):
            result.input_tokens = 0  # type: ignore[misc]

    def test_the_bundle_id_names_the_bundle(self, result: ExtractionResult) -> None:
        assert result.bundle_id == BUNDLE_ID

    def test_the_claims_path_is_a_file(self, result: ExtractionResult) -> None:
        assert result.claims_path.is_file()

    def test_the_claims_path_is_inside_the_cache_directory(
        self, result: ExtractionResult, tmp_path: Path
    ) -> None:
        assert result.claims_path.is_relative_to(tmp_path / "data")

    def test_the_claims_file_is_the_model_output_as_it_arrived(
        self, result: ExtractionResult
    ) -> None:
        """R27: what is on disk is what the model said, not a tidied copy of it."""
        assert result.claims_path.read_text(encoding="utf-8").strip() == MODEL_REPLY.strip()

    def test_the_claims_file_is_one_ingest_accepts(self, result: ExtractionResult) -> None:
        parsed = claims_module.parse_claims(
            result.claims_path.read_text(encoding="utf-8"), result.claims_path, 1
        )

        assert len(parsed) == len(CLAIM_ROWS)
        assert parsed[0].board == "Quorvex B940"
        assert parsed[1].category == "warning"

    def test_two_bundles_do_not_share_one_claims_file(
        self, model: FakeModel, tmp_path: Path
    ) -> None:
        config = make_config(tmp_path)
        first = extract_bundle(write_bundle(tmp_path, bundle_id="bundle-007"), 1, config)
        second = extract_bundle(write_bundle(tmp_path, bundle_id="bundle-008"), 1, config)

        assert first.claims_path != second.claims_path
        assert first.claims_path.is_file() and second.claims_path.is_file()


class TestTheFourTokenComponents:
    """R8 as amended: four numbers, kept four numbers, all the way out.

    A single total is dominated by cache reads, which are the cheapest tokens in
    it, so a summed figure says nothing about what a batch cost. The values here
    are chosen so that a swap between any two fields, or a sum landing in any
    one of them, changes what these assertions see.
    """

    @pytest.fixture
    def result(self, model: FakeModel, tmp_path: Path) -> ExtractionResult:
        return extract_bundle(write_bundle(tmp_path), 1, make_config(tmp_path))

    def test_fresh_input_is_fresh_input(self, result: ExtractionResult) -> None:
        assert result.input_tokens == INPUT_TOKENS

    def test_output_is_output(self, result: ExtractionResult) -> None:
        assert result.output_tokens == OUTPUT_TOKENS

    def test_cache_creation_is_cache_creation(self, result: ExtractionResult) -> None:
        assert result.cache_creation_tokens == CACHE_CREATION_TOKENS

    def test_cache_read_is_cache_read(self, result: ExtractionResult) -> None:
        assert result.cache_read_tokens == CACHE_READ_TOKENS

    def test_no_field_carries_the_total(self, result: ExtractionResult) -> None:
        totals = [name for name in RESULT_FIELDS[2:] if getattr(result, name) == TOTAL_TOKENS]
        assert not totals, f"{totals} carries the summed total R8 forbids"

    def test_the_components_are_whole_numbers(self, result: ExtractionResult) -> None:
        for name in RESULT_FIELDS[2:]:
            value = getattr(result, name)
            assert isinstance(value, int) and not isinstance(value, bool), f"{name} is {value!r}"

    def test_the_result_never_offers_a_total(self, result: ExtractionResult) -> None:
        for forbidden in ("total_tokens", "tokens", "total"):
            assert not hasattr(result, forbidden), (
                f"ExtractionResult exposes {forbidden}, and R8 forbids a single total"
            )


# --------------------------------------------------------------------------
# The batch, and the ordering that makes a failed run evidence.
# --------------------------------------------------------------------------


class TestTheBatchIsPassedThrough:
    def test_the_batch_reaches_the_parse(
        self, model: FakeModel, parses: ParseWatch, tmp_path: Path
    ) -> None:
        extract_bundle(write_bundle(tmp_path, batch=1), 1, make_config(tmp_path))

        assert parses.only.batch == 1

    def test_a_later_batch_is_the_batch_that_is_stamped(
        self, model: FakeModel, parses: ParseWatch, tmp_path: Path
    ) -> None:
        extract_bundle(write_bundle(tmp_path, batch=3), 3, make_config(tmp_path))

        assert parses.only.batch == 3

    def test_the_argument_governs_and_not_the_bundle_file(
        self, model: FakeModel, parses: ParseWatch, tmp_path: Path
    ) -> None:
        """The batch is a fact about the RUN, which is why it is an argument at all.

        The bundle's XML says batch 1; the caller says 4. A build that read the
        file instead would make the parameter decoration.
        """
        bundle_path = write_bundle(tmp_path, batch=1)

        extract_bundle(bundle_path, 4, make_config(tmp_path))

        assert parses.only.batch == 4


class TestTheOutputIsWrittenBeforeItIsParsed:
    """R27, and the subtlest promise in the slice.

    A file that fails validation is evidence of what the model actually said,
    and the spend that produced it has already happened. Parsing first and
    writing only on success — or writing and then cleaning up after a failure —
    destroys the only record of it, and both look perfectly tidy in review.
    """

    def test_the_file_is_already_there_when_the_parse_runs(
        self, model: FakeModel, parses: ParseWatch, tmp_path: Path
    ) -> None:
        extract_bundle(write_bundle(tmp_path), 1, make_config(tmp_path))

        assert parses.only.output_existed, (
            "parse_claims ran before the model's output reached the disk"
        )

    def test_the_parse_reads_what_was_written(
        self, model: FakeModel, parses: ParseWatch, tmp_path: Path
    ) -> None:
        result = extract_bundle(write_bundle(tmp_path), 1, make_config(tmp_path))

        assert parses.only.path == result.claims_path
        assert parses.only.raw.strip() == MODEL_REPLY.strip()

    def test_a_refused_output_is_still_on_disk(self, model: FakeModel, tmp_path: Path) -> None:
        model.reply = INVALID_REPLY
        config = make_config(tmp_path)

        refusal(write_bundle(tmp_path), 1, config)

        kept = outputs(config)
        assert kept, "the run refused the output and left nothing behind to show for it"
        assert any(
            path.read_text(encoding="utf-8").strip() == INVALID_REPLY.strip() for path in kept
        )

    def test_an_unparseable_output_is_still_on_disk(self, model: FakeModel, tmp_path: Path) -> None:
        model.reply = UNPARSEABLE_REPLY
        config = make_config(tmp_path)

        refusal(write_bundle(tmp_path), 1, config)

        kept = outputs(config)
        assert kept, "a reply that was not even JSON was thrown away rather than kept"
        assert any(
            path.read_text(encoding="utf-8").strip() == UNPARSEABLE_REPLY.strip() for path in kept
        )

    def test_the_refusal_names_the_file_it_kept(self, model: FakeModel, tmp_path: Path) -> None:
        """`InvalidClaims` carries the path, and the path must lead somewhere."""
        model.reply = INVALID_REPLY

        caught = refusal(write_bundle(tmp_path), 1, make_config(tmp_path))

        assert caught.path.is_file(), f"{caught.path} was named in the refusal and is not there"
        assert caught.path.read_text(encoding="utf-8").strip() == INVALID_REPLY.strip()

    def test_the_refusal_carries_every_fault(self, model: FakeModel, tmp_path: Path) -> None:
        """Slice 1's message reaches the caller intact, rather than a first fault."""
        model.reply = INVALID_REPLY

        caught = refusal(write_bundle(tmp_path), 1, make_config(tmp_path))

        assert len(caught.faults) >= 2, caught.message()

    def test_the_model_was_paid_before_the_refusal(self, model: FakeModel, tmp_path: Path) -> None:
        """The call happened; the refusal is downstream of a spend, not instead of one."""
        model.reply = INVALID_REPLY

        refusal(write_bundle(tmp_path), 1, make_config(tmp_path))

        assert len(model.calls) == 1


# --------------------------------------------------------------------------
# The model is configuration.
# --------------------------------------------------------------------------


class TestTheModelIsConfigured:
    """The plan's second Uncertainty: "a configured `extraction_model` with no
    default in code, set in `config.toml`, so the choice is data rather than a
    constant". A factor measured against one model does not transfer to another,
    and slice 4's record has to be able to say which model it measured.
    """

    def test_the_extraction_model_is_a_configuration_field(self) -> None:
        assert "extraction_model" in config_fields(), (
            "the plan configures the extraction model rather than fixing it in code, "
            "and `extract_bundle` is handed nothing but the bundle, the batch and Config"
        )

    def test_the_configured_model_is_the_one_requested(
        self, model: FakeModel, tmp_path: Path
    ) -> None:
        config = make_config(tmp_path, extraction_model=MODEL_A)

        extract_bundle(write_bundle(tmp_path), 1, config)

        assert MODEL_A in model.sent, "the configured model never reached the request"

    def test_a_different_configured_model_changes_the_request(
        self, model: FakeModel, tmp_path: Path
    ) -> None:
        config = make_config(tmp_path, extraction_model=MODEL_B)

        extract_bundle(write_bundle(tmp_path), 1, config)

        assert MODEL_B in model.sent
        assert MODEL_A not in model.sent, "the model is hard-coded: configuration was ignored"

    def test_the_configured_model_is_what_config_toml_carries(self) -> None:
        """Data, in the file the owner edits — not a default hiding in `load_config`."""
        text = (REPO_ROOT / "config.toml").read_text(encoding="utf-8")

        assert re.search(r"(?m)^\s*extraction_model\s*=", text), (
            "config.toml does not set extraction_model, so the choice is not data"
        )


# --------------------------------------------------------------------------
# An unset model refuses before it spends.
# --------------------------------------------------------------------------

# Every spelling of "nobody chose a model". The empty string is what
# `load_config` leaves for a key that is absent from `config.toml`; the rest are
# what is left after someone clears the value and not the quotes. All of them
# are the ABSENCE of a choice and none of them is the name of a model.
UNSET_MODELS: tuple[str, ...] = ("", " ", "\t", "\n", "   ", " \t\n ")

# Anything in the message that looks like a file in this repository. Used
# instead of searching for one particular phrase, so the sentence around the
# pointer stays free to change.
_LOCATION = re.compile(r"[A-Za-z0-9_./-]+\.(?:toml|md)")


def named_locations(message: str) -> list[Path]:
    """Every repository file the message points the reader at."""
    return [REPO_ROOT / match.group(0) for match in _LOCATION.finditer(message)]


def openable_locations(message: str) -> list[Path]:
    """Those of them that are really there to be opened."""
    return [path for path in named_locations(message) if path.is_file()]


# Every way a message can say "this value is not yours to pick". Held as a
# handful of alternatives rather than one sentence because the prose is expected
# to be rewritten and it is the MEANING that has to survive the rewrite: pinning
# a sentence would fail on every improvement and teach nobody anything.
_ALREADY_DECIDED = re.compile(
    r"owner ruling|already decided|already been decided|fixed by|was ruled|not an open choice",
    re.I,
)


@pytest.fixture
def refusal_message(model: FakeModel, tmp_path: Path) -> str:
    """The text an unset `extraction_model` refuses with.

    Takes `model` so that a build which had LOST the refusal reaches the faked
    seam rather than a real `claude -p`: the tests about wording must be as
    unable to spend as every other test in this file.
    """
    config = make_config(tmp_path, extraction_model="")
    with pytest.raises(ExtractionFailed) as caught:
        extract_bundle(write_bundle(tmp_path), 1, config)
    return str(caught.value)


class TestAnUnsetModelRefusesBeforeItSpends:
    """The one failure in this slice that costs nothing to prevent and a batch to find late.

    `extraction_model` has no default in code, deliberately. The plan's second
    Uncertainty records why: the value was never an open choice — `docs/DESIGN.md`
    §6 fixes it by owner ruling ("Opus 5 throughout, low effort for per-excerpt
    extraction") and R17 makes it a key rather than a constant — so the code must
    not invent one, and an unset key has to cost a message rather than money.

    Nothing else in this file builds a config without a model: `make_config`
    always supplies one, which is precisely how a branch like this ships with
    every gate green and no test on it.
    """

    @pytest.mark.parametrize("unset", UNSET_MODELS, ids=repr)
    def test_it_raises_rather_than_extracting(
        self, model: FakeModel, tmp_path: Path, unset: str
    ) -> None:
        config = make_config(tmp_path, extraction_model=unset)

        with pytest.raises(ExtractionFailed):
            extract_bundle(write_bundle(tmp_path), 1, config)

    @pytest.mark.parametrize("unset", UNSET_MODELS, ids=repr)
    def test_nothing_at_all_was_sent(self, model: FakeModel, tmp_path: Path, unset: str) -> None:
        """The strongest thing this path promises, and the whole reason it exists.

        Not "it raised": a refusal raised AFTER the call would have spent the
        money anyway, and `--model ''` is a request `claude -p` may well answer
        by picking a default of its own — the one outcome the missing key is
        supposed to make impossible. The seam records every route out of the
        process, and here it must have recorded nothing whatsoever.
        """
        config = make_config(tmp_path, extraction_model=unset)

        with pytest.raises(ExtractionFailed):
            extract_bundle(write_bundle(tmp_path), 1, config)

        assert model.calls == [], (
            f"a model with no name was invoked anyway: {model.requests()}. The refusal "
            "came after the spend, which is no refusal at all."
        )

    def test_whitespace_is_not_the_name_of_a_model(self, model: FakeModel, tmp_path: Path) -> None:
        """`extraction_model = "   "` is a cleared key, not a model called "   ".

        Stated on its own rather than left to the parametrised cases above,
        because it is a different defect with a different cause: a guard written
        as `if model is None`, or one that only tests the string's truthiness,
        hands three spaces to `--model` and discovers the mistake inside a call
        that has already been paid for.
        """
        config = make_config(tmp_path, extraction_model="   ")

        with pytest.raises(ExtractionFailed):
            extract_bundle(write_bundle(tmp_path), 1, config)

        assert model.calls == [], f"three spaces were treated as a model: {model.requests()}"

    def test_a_key_that_was_never_set_refuses_too(self, model: FakeModel, tmp_path: Path) -> None:
        """The real unset case: `config.toml` without the key at all.

        Built through `load_config` rather than by passing `""` by hand, so that
        what is exercised is the value the loader actually produces for an
        absent key — the plan's "there is no default in code, so a missing key
        costs a message rather than money".
        """
        blank = tmp_path / "no-extraction-model.toml"
        blank.write_text("", encoding="utf-8")
        config = dataclasses.replace(load_config(blank), data_dir=tmp_path / "data")

        with pytest.raises(ExtractionFailed):
            extract_bundle(write_bundle(tmp_path), 1, config)

        assert model.calls == [], f"an absent key produced a call: {model.requests()}"

    def test_the_refusal_is_the_modules_own_failure(self, model: FakeModel, tmp_path: Path) -> None:
        """`ExtractionFailed`, and specifically not `InvalidClaims`.

        The distinction is load-bearing for slice 3, which decides between
        retrying a bundle and setting it aside: an `InvalidClaims` names a file
        on disk that can be read to see what the model said, while this says the
        call never happened and there is nothing to read. A bare `ValueError`
        would be neither, and `pytest.raises` above is what rejects it.
        """
        config = make_config(tmp_path, extraction_model="")

        with pytest.raises(ExtractionFailed) as caught:
            extract_bundle(write_bundle(tmp_path), 1, config)

        assert not isinstance(caught.value, InvalidClaims), (
            "an unset model was reported as a bad claims file, which names a path "
            "to read; nothing was written and there is nothing to read"
        )

    @pytest.mark.parametrize("unset", ("", "  "), ids=repr)
    def test_no_claims_file_is_left_behind(
        self, model: FakeModel, tmp_path: Path, unset: str
    ) -> None:
        """R27 keeps what the model said. A call that never happened said nothing.

        The mirror of `test_a_refused_output_is_still_on_disk`: a claims file
        here would be a record of a spend that did not occur, and slice 1's
        ingest would offer to store it.
        """
        config = make_config(tmp_path, extraction_model=unset)
        bundle_path = write_bundle(tmp_path)

        with pytest.raises(ExtractionFailed):
            extract_bundle(bundle_path, 1, config)

        assert outputs(config) == [], (
            f"the refusal left {outputs(config)} behind for a call that never happened"
        )
        strays = [path for path in tmp_path.rglob("*") if path.is_file() and path != bundle_path]
        assert strays == [], f"the refusal wrote {strays} before refusing"

    def test_the_output_is_never_parsed(
        self, model: FakeModel, parses: ParseWatch, tmp_path: Path
    ) -> None:
        """Nothing came back, so there is nothing to validate — and no file to name."""
        config = make_config(tmp_path, extraction_model="")

        with pytest.raises(ExtractionFailed):
            extract_bundle(write_bundle(tmp_path), 1, config)

        assert parses.calls == [], "the refusal ran the parser over something that never arrived"


class TestTheRefusalIsActionable:
    """A refusal a reader cannot act on is a stall, not a guard.

    Every assertion here is deliberately LOOSE — a substring, folded to one
    case, or a search for any repository file the message names. The prose is
    expected to improve, and a test that pinned whole sentences would fail on
    every improvement while teaching nobody anything. What is pinned is only
    what the reader must be able to ACT on.
    """

    def test_it_names_the_key_to_set(self, refusal_message: str) -> None:
        """The exact spelling of the key, because that is what has to be typed.

        Matched case-insensitively and as a bare substring: whether it is
        quoted, backticked or wrapped in a sentence is the message's business.
        """
        assert "extraction_model" in refusal_message.lower(), refusal_message

    def test_it_points_at_a_place_the_reader_can_open(self, refusal_message: str) -> None:
        """Some file in this repository, found by shape rather than by phrase.

        The VALUE is not an open choice — `docs/DESIGN.md` §6 fixed it by owner
        ruling and `docs/DECISIONS.md`'s 2026-08-25 entry rules on how it is
        paid for — so a message that said only "set a model" would leave the
        reader inventing one, and an invented model makes the calibration record
        evidence of nothing. What is asserted is that SOMETHING openable is
        named, not which words name it.
        """
        assert openable_locations(refusal_message), (
            "the refusal points the reader at no file they can open: " + refusal_message
        )

    def test_the_place_it_points_at_is_where_the_value_is_decided(
        self, refusal_message: str
    ) -> None:
        """Following the pointer has to reach the key and the ruling behind it.

        Loose in the same way and for the same reason: the message may name any
        file it likes, so long as opening that file shows the reader the key and
        says where the value was decided rather than inviting them to pick one.
        """
        openable = openable_locations(refusal_message)
        assert openable, refusal_message

        carries_key = [
            path for path in openable if "extraction_model" in path.read_text(encoding="utf-8")
        ]
        assert carries_key, (
            f"the refusal names {[path.name for path in openable]}, and none of them "
            "mentions the key it told the reader to set"
        )
        assert any(
            re.search(r"design|decisions|owner ruling", path.read_text(encoding="utf-8"), re.I)
            for path in carries_key
        ), (
            "the refusal points at a file that presents the model as an open choice; "
            "it is fixed by owner ruling (docs/DESIGN.md §6) and the pointer must lead there"
        )

    def test_it_points_at_the_document_where_the_value_was_ruled_on(
        self, refusal_message: str
    ) -> None:
        """A reader sent only to `config.toml` finds an empty key, and fills it in themselves.

        `config.toml` is where the value is TYPED; it is not where the value was
        decided. Someone who opens it on this refusal sees `extraction_model =`
        with nothing after it and no way to learn what belongs there, so they
        put in whichever model name they happen to trust — and a chars-per-token
        factor measured against a model nobody ruled on makes the calibration
        record evidence of nothing, which is exactly the outcome the missing
        default exists to prevent.

        So the pointer has to reach the ruling as well as the key: some file
        under `docs/`, where `docs/DESIGN.md` §6 fixes the model and effort tiers
        and `docs/DECISIONS.md` records how the call is paid for. WHICH document
        is the message's business, and so is the sentence that names it; that
        one of them is named at all is not.
        """
        openable = openable_locations(refusal_message)
        assert openable, (
            "the refusal points the reader at no file they can open: " + refusal_message
        )

        documented = [path for path in openable if REPO_ROOT / "docs" in path.parents]
        assert documented, (
            f"the refusal names only {[path.name for path in openable]}, and none of them "
            "lives under docs/, so the reader is sent to where the value is typed and never "
            "to where it was ruled on: " + refusal_message
        )

    def test_it_says_the_value_is_already_decided(self, refusal_message: str) -> None:
        """A message that says "set a model" invites a choice. There is none to invite.

        The difference is not politeness. A message phrased as an open question
        gets answered by the reader, and the reader has no standing to answer
        it: the tiers are fixed by owner ruling (`docs/DESIGN.md` §6, "Opus 5
        throughout, low effort for per-excerpt extraction"), and R17 makes that
        ruling a configuration key rather than a constant only so it can be seen
        and restated — not so it can be renegotiated by whoever hits the error.
        Told the value is already decided, the reader goes and copies it; told to
        pick one, they pick one.

        Matched against a few alternative phrasings, case-folded, because the
        wording will change and only the meaning is being pinned.
        """
        assert _ALREADY_DECIDED.search(refusal_message), (
            "the refusal presents the extraction model as a value for the reader to choose; "
            "it is already decided by owner ruling and the message has to say so, or the "
            "reader invents one: " + refusal_message
        )


class TestTheRefusalDoesNotFireWhenItShouldNot:
    """A guard that always refuses is as broken as one that never does.

    Without these, a mutation that raised unconditionally would still pass every
    test above — and the whole of Stage B would refuse to spend anything at all.
    """

    def test_a_configured_model_is_extracted_rather_than_refused(
        self, model: FakeModel, tmp_path: Path
    ) -> None:
        config = make_config(tmp_path, extraction_model=MODEL_A)

        result = extract_bundle(write_bundle(tmp_path), 1, config)

        assert result.claims_path.is_file()
        assert len(model.calls) == 1, f"one bundle, one call; it made {model.requests()}"
        assert MODEL_A in model.sent

    def test_a_model_name_with_a_space_in_it_is_still_a_model(
        self, model: FakeModel, tmp_path: Path
    ) -> None:
        """Only an ALL-whitespace value is unset; a space inside a name is not.

        A guard that stripped spaces out of the value rather than off its ends
        would pass every refusal test above and quietly request a different
        model than the one configured.
        """
        spaced = "claude test delta 5182"
        config = make_config(tmp_path, extraction_model=spaced)

        extract_bundle(write_bundle(tmp_path), 1, config)

        assert len(model.calls) == 1, f"a configured model was refused: {model.requests()}"
        assert spaced in model.sent


# --------------------------------------------------------------------------
# R23.
# --------------------------------------------------------------------------


class TestDeterminism:
    """The same bundle and the same prompt produce the same request twice.

    This is what "produces a comparable file twice" rests on: if the request
    carries a timestamp, a session id or a re-ordered payload, two runs of the
    same batch are not comparable and the calibration measures two things.
    """

    def test_the_same_bundle_sends_the_same_request_twice(
        self, model: FakeModel, tmp_path: Path
    ) -> None:
        bundle_path = write_bundle(tmp_path)
        config = make_config(tmp_path)

        extract_bundle(bundle_path, 1, config)
        extract_bundle(bundle_path, 1, config)

        first, second = model.requests()
        assert first == second

    def test_the_same_bundle_writes_to_the_same_path_twice(
        self, model: FakeModel, tmp_path: Path
    ) -> None:
        bundle_path = write_bundle(tmp_path)
        config = make_config(tmp_path)

        first = extract_bundle(bundle_path, 1, config)
        second = extract_bundle(bundle_path, 1, config)

        assert first.claims_path == second.claims_path

    def test_the_same_bundle_gives_the_same_result_twice(
        self, model: FakeModel, tmp_path: Path
    ) -> None:
        bundle_path = write_bundle(tmp_path)
        config = make_config(tmp_path)

        assert extract_bundle(bundle_path, 1, config) == extract_bundle(bundle_path, 1, config)


# --------------------------------------------------------------------------
# One seam, and nothing else.
# --------------------------------------------------------------------------


class TestNothingReachesAModel:
    """The suite runs offline, free, and identically on a machine with no
    subscription at all. `conftest.py` blocks the sockets; this class is about
    the process boundary, which a `claude -p` would cross instead.
    """

    def test_the_request_went_through_the_faked_seam(
        self, model: FakeModel, tmp_path: Path
    ) -> None:
        extract_bundle(write_bundle(tmp_path), 1, make_config(tmp_path))

        assert model.calls, (
            "nothing was recorded, so the extraction reached a model by a route this "
            f"file does not fake (module seam found: {model.seam})"
        )

    def test_importing_the_module_starts_no_session(self) -> None:
        """Lazily built, like `ytdlp._CAPTION_CLIENT`: importing opens nothing.

        `ytdlp` builds its client on first use rather than at import precisely so
        that merely importing the module opens nothing, "which is what keeps the
        offline test suite honest". The same is true here and costs more: a
        client built at import is a session started by collecting the suite.
        """
        candidates = _client_candidates()
        if not candidates:
            pytest.skip("extract.py holds no client to inspect")
        for name in candidates:
            assert getattr(extract, name) is None, f"{name} was built at import time"

    def test_the_seam_is_used_rather_than_a_second_route(
        self, model: FakeModel, tmp_path: Path
    ) -> None:
        extract_bundle(write_bundle(tmp_path), 1, make_config(tmp_path))

        wheres = {call.where for call in model.calls}
        assert len(wheres) == 1, f"the extraction left the process by {sorted(wheres)}"


# --------------------------------------------------------------------------
# A graphics card is not a motherboard, and a graphics card video is not
# a video without motherboards in it (ESC-29).
# --------------------------------------------------------------------------

# The thing being excluded, in the spellings a rewrite of this prose might
# reach for. Word boundaries rather than bare substrings, so that a `gpu`
# living inside a longer word is not read as the model being told anything.
_GRAPHICS_CARD = re.compile(
    r"\bgpus?\b|\b(?:graphics|video)\s+cards?\b|\bgraphics\s+(?:processors?|chips?)\b",
    re.IGNORECASE,
)

# How this prompt says "do not write this down". Taken from the exclusions it
# already carries — "Skip it.", "is not a claim about a board", "produces no
# claim" — plus the near neighbours an editor would use instead.
_EXCLUSION = re.compile(
    r"\bskip\b|\bnot a claim\b|\bnot a board\b|\bnot a motherboard\b|\bignore\b"
    r"|\bdo not record\b|\bexclude\b|\bleave (?:it|them) out\b|\bno claim\b|\bdiscard\b",
    re.IGNORECASE,
)

# The video, as a unit, rather than the sentence inside it.
_VIDEO = re.compile(r"\bvideos?\b", re.IGNORECASE)

# "the whole video", "the rest of the transcript", "the entire bundle" — the
# scope that ESC-29's ruling forbids the exclusion from reaching.
_WHOLE_VIDEO = re.compile(
    r"\b(?:whole|entire|all of (?:the|that)|rest of (?:the|that)|every claim in (?:the|that))\s+"
    r"(?:video|transcript|excerpt|bundle)s?\b"
    r"|\bvideos?\s+(?:as a whole|entirely|altogether)\b",
    re.IGNORECASE,
)

_DISCARD_VERB = re.compile(
    r"\b(?:skip|ignore|discard|drop|throw away|leave out|exclude)\b", re.IGNORECASE
)

# Anything that turns a discard verb into its own denial. Checked across the
# whole span between the verb and the scope it appears to govern, so that
# "skip the claim, not the whole video" reads as the permission it is.
_NEGATION = re.compile(
    r"\bnot\b|\bnever\b|n't\b|\bno\b|\bstill\b|\brather than\b|\binstead of\b|\bonly\b",
    re.IGNORECASE,
)

# That a claim survives whatever the video was about.
_SURVIVES = re.compile(
    r"\bstill\b|\banyway\b|\bnevertheless\b|\beven (?:so|then|when|if|in|though)\b"
    r"|\bkeeps?\b|\bkept\b|\brecord\b|\bwrite (?:it|them) down\b|\bdo not (?:skip|discard|drop)\b",
    re.IGNORECASE,
)

_BOARD = re.compile(r"\b(?:mother)?boards?\b", re.IGNORECASE)


def _graphics_windows(prompt: str, span: int = 300) -> list[str]:
    """Every stretch of the prompt that mentions a graphics card, plus its context.

    A window rather than a sentence or a bullet, because where the exclusion
    and its counterweight get split across two neighbouring bullets — which is
    how prose about a rule and prose about its limit usually ends up — a
    sentence-shaped unit sees only half of each and reports a prompt that says
    both as a prompt that says neither.
    """
    return [
        prompt[max(0, match.start() - span) : match.end() + span]
        for match in _GRAPHICS_CARD.finditer(prompt)
    ]


def _discards_a_whole_video(text: str) -> str | None:
    """The fragment where a discard verb governs a whole video, if there is one.

    Deliberately biased towards saying no. Any negation between the verb and
    the scope it reaches — "skip the claim, not the whole video" — clears it,
    because the sentence this test exists to protect is exactly the sentence
    that has to name the forbidden action in order to forbid it.
    """
    for scope in _WHOLE_VIDEO.finditer(text):
        lead = text[max(0, scope.start() - 60) : scope.start()]
        verbs = list(_DISCARD_VERB.finditer(lead))
        if not verbs:
            continue
        verb = verbs[-1]
        if _NEGATION.search(lead[verb.start() :]):
            continue
        offset = max(0, scope.start() - 60) + verb.start()
        return " ".join(text[max(0, offset - 40) : scope.end()].split())
    return None


def _exclusions_it_does_state(prompt: str) -> list[str]:
    """The lines where the prompt already tells the model to leave something out.

    Quoted back in every failure below, because "the graphics card sentence is
    missing" is only actionable next to the sentences it should have been
    written beside.
    """
    return [line.strip() for line in prompt.splitlines() if _EXCLUSION.search(line)]


class TestThePromptExcludesGraphicsCards:
    """ESC-29: 35 well-formed claims about GRAPHICS CARDS reached the corpus.

    Buildzoid reviews graphics cards as well as motherboards, and those videos
    are in the corpus legitimately — a real board name is mentioned in them, so
    `mention_threshold` selects them, exactly as it should. The prompt then
    names three things that are not a board (a CPU, a chipset in general, the
    industry) and does not name a graphics card, so the model did the only
    reasonable thing with a bench full of GPU talk: it wrote it down. Every one
    of the 35 rows was correctly categorised, correctly quoted and correctly
    timestamped. Nothing downstream could see them — `claims.py` validates the
    SHAPE of a row and has no opinion about what a `board` is — and a corpus
    about motherboards had a twentieth of its claims about something else.

    The exclusion is asserted loosely on purpose. This prose will be rewritten,
    and a test pinned to one sentence of it is a test that fails the next
    editor rather than the next escape.

    Everything here reads the prompt through `prompt_text()` rather than off
    `PROMPT_PATH`, because the loader is what the extraction actually sends: a
    rule that exists in the file but not in the loader's return value is a rule
    the model never sees.
    """

    @pytest.fixture
    def prompt(self) -> str:
        return prompt_text()

    def test_the_prompt_tells_the_model_to_skip_a_claim_about_a_graphics_card(
        self, prompt: str
    ) -> None:
        """The exclusion has to exist at all, and has to read as an exclusion.

        A prompt that merely MENTIONS graphics cards somewhere — in the list of
        what the channel covers, say — is what produced ESC-29's alternative
        outcome, which is nothing. The word and the instruction must arrive
        together.
        """
        windows = _graphics_windows(prompt)
        assert windows, (
            "the prompt never mentions a graphics card or a GPU, so ESC-29's 35 rows "
            "are still extractable; the exclusions it does state are "
            f"{_exclusions_it_does_state(prompt)}"
        )
        excluding = [window for window in windows if _EXCLUSION.search(window)]
        assert excluding, (
            "the prompt mentions a graphics card but never tells the model to leave one "
            f"out; what it says about them is {[' '.join(w.split()) for w in windows]}"
        )

    def test_the_exclusion_is_stated_in_prose_and_not_only_inside_an_example(
        self, prompt: str
    ) -> None:
        """A rule that lives only in a fenced block is a rule about the block.

        `TestThePromptFitsTheSchema` already treats the worked example as the
        part a model copies; the converse holds too. A `"board": "RTX 5090"`
        row inside an example, or a fenced bundle whose `<video_title>` names a
        graphics card, is not an instruction about what to skip, and ESC-29 is
        an escape about a missing instruction.
        """
        prose = _FENCED.sub("\n", prompt)
        windows = _graphics_windows(prose)
        assert windows, (
            "graphics cards appear in the prompt only inside a fenced example, where "
            "they are illustration rather than instruction; the prose exclusions are "
            f"{_exclusions_it_does_state(prose)}"
        )
        excluding = [window for window in windows if _EXCLUSION.search(window)]
        assert excluding, (
            "the prompt's PROSE names a graphics card without excluding one; what the "
            f"prose says about them is {[' '.join(w.split()) for w in windows]}"
        )

    def test_the_exclusion_is_weighed_against_the_video_it_appears_in(self, prompt: str) -> None:
        """The counterweight, and the half that matters more.

        The owner ruled it twice: motherboard claims must not be lost, and a
        GPU claim included by mistake is the acceptable error. A graphics card
        video is FULL of board claims, because he is testing on a board and
        says so — so the exclusion has to be about the sentence in front of the
        model, and the prompt has to say which scope it means. Prose that
        excludes graphics cards without ever mentioning the video is prose a
        model can reasonably read as "this bundle is not for you".
        """
        windows = _graphics_windows(prompt)
        assert windows, "the prompt never mentions a graphics card at all, so there is no scope"
        scoped = [window for window in windows if _VIDEO.search(window)]
        assert scoped, (
            "the prompt excludes graphics cards without ever saying that the VIDEO's "
            "subject is not what decides, which is the reading that loses the board "
            f"claims in a GPU video; what it says is {[' '.join(w.split()) for w in windows]}"
        )

    def test_a_board_claim_in_a_graphics_card_video_is_still_a_board_claim(
        self, prompt: str
    ) -> None:
        """Say the keeping part, not only the skipping part.

        "It is the subject of the sentence that decides" is only half an
        instruction; the half that saves the corpus is that the board claims in
        that same video are still wanted. This looks for the prompt saying so —
        loosely, over any of the ways one says "still", "keep" or "record" —
        near both a graphics card and a board.
        """
        windows = _graphics_windows(prompt)
        assert windows, "the prompt never mentions a graphics card at all, so it keeps nothing"
        keeping = [
            window for window in windows if _SURVIVES.search(window) and _BOARD.search(window)
        ]
        assert keeping, (
            "the prompt tells the model what to drop in a graphics card video and never "
            "tells it what to keep; ESC-29's ruling is that losing a board claim costs "
            "more than including a GPU one. What it says is "
            f"{[' '.join(w.split()) for w in windows]}"
        )

    def test_the_prompt_never_tells_the_model_to_discard_a_whole_video(self, prompt: str) -> None:
        """The over-correction, which would be worse than ESC-29 itself.

        The cheap fix for 35 GPU rows is "if the video is about a graphics
        card, skip it", and that fix throws away every real motherboard claim
        he makes while a graphics card is on the bench — a silent loss, in a
        corpus whose whole purpose is those claims, and one no count of rows
        would reveal. `[]` for a bundle is a valid answer; `[]` for a bundle
        because of what the video was ABOUT is not.
        """
        windows = _graphics_windows(prompt)
        assert windows, "the prompt never mentions a graphics card at all, so nothing is excluded"
        for window in windows:
            offending = _discards_a_whole_video(window)
            assert offending is None, (
                "the prompt tells the model to throw away a whole video for being about a "
                f"graphics card: {offending!r}. ESC-29's ruling is the other way round — "
                "the subject of the SENTENCE decides, and a GPU video still carries claims "
                "about the board he is testing on"
            )
