# Journal — Finding Best Mobo by Buildzoid

One dated entry per working session: what was done, what was decided elsewhere
and only referenced here, and what the next session should pick up. Newest at
the bottom. This is the hand-off file — chat is not storage.

## 2026-08-14 — pipeline bootstrap

The `copier update to v0.4.0` pull request (#2) landed the enforcement pipeline:
CI, the `plan` gate, `test-the-tests`, the LLM review gate, and auto-merge.

Two failures were fixed on the branch before it merged:

- `uv.lock` still recorded a `ruff` version outside the range `pyproject.toml`
  pins, so `uv sync --locked` refused to install and CI stopped before running
  anything. Relocked.
- The `secrets` job crashed with a 403 on every pull request — the default token
  cannot list a pull request's commits, so gitleaks aborted instead of scanning.
  The job now requests `pull-requests: read`. Logged in `docs/escapes.md`.

The `plan` and `review` gates could not pass and were not made to: this is the
pull request that introduces the planning system, so no plan for it can exist on
the default branch, and the review gate blocks a large unplanned rewrite of the
gates themselves by design. The owner merged it with bypass rights. That is the
bootstrap path, not a precedent — from here every change has a pipeline to pass.

Next session: `docs/DESIGN.md` is still the unfilled template, so §5 has no
requirements for a plan to cover and §13 no success criteria for the acceptance
pass to evidence. Filling it in is the gate on all planned work.

## 2026-08-14 — template v0.4.4, and the template URL

The v0.4.4 update (#4) introduces `template-sync`: it replays `copier update`
from the base commit and passes only if the result matches the branch exactly.
That check is what earns a `template/` branch its exemption from planning — a
stronger claim than a plan, because it verifies the diff rather than recording
an intention.

It could not run. `_src_path` named `github.com-grimsverk`, an SSH host alias
defined in the owner's `~/.ssh/config` and resolvable nowhere else, so the clone
failed before copier started. `TEMPLATE_TOKEN` does not reach this: the workflow
rewrites `https://github.com/` and `git@github.com:`, and an `ssh://` alias URL
matches neither. This pull request points `_src_path` at the plain `https://`
URL, which the runner can resolve and the token can authenticate.

Two consequences worth carrying forward. First, #4 was merged by owner override:
it also carried unresolved conflict markers in `src/find_best_mobo/__init__.py`,
and fixing them by hand is itself a manual edit, so `template-sync` would reject
that branch even once it could run. Second, `project_name` is now the slug and
`project_slug` is gone — deliberate, matching the new template, not drift.

## 2026-08-14 — the design doc, written and nearly lost

`docs/DESIGN.md` is filled in, replacing the skeleton that has been gating all
planned work since the bootstrap session. It carries 25 requirements and 11
success criteria. Every owner ruling behind it is recorded in `docs/DECISIONS.md`
(created this session) rather than left in chat.

The shape that came out of elicitation: the pipeline splits at the model
boundary, because no API key exists and all inference runs on the owner's
subscription. Python owns the deterministic corpus work and writes bundles to
disk; agents read bundles and write claims back. Between them sits a hard
checkpoint that prints a cost projection and stops, then a small calibration
batch that turns the projection into a measurement, then three larger batches
with a stop after them. Reports are generable at any batch boundary with a
coverage stamp, so stopping early is a real option rather than an abandonment.

Two owner revisions during drafting, both superseding positions taken earlier in
the same session and both recorded in `DECISIONS.md`: transcript failures are
logged and tolerated with two halt triggers rather than failing hard, and the
excerpt window starts wide (2 min before a mention, 5 after) to be narrowed
later on evidence rather than starting tight.

**Nearly lost.** The owner reset their local checkout to `origin/main` partway
through, and the design doc — tracked, but never committed — went back to the
skeleton. It was reconstructed from the session's context in full. Nothing else
was affected; `GLOSSARY.project.md` survived as an untracked file. The lesson is
the ordinary one: git protects what has been committed, and a large document
living only in the working tree is one command from gone.

**Found while reviewing before the pull request:** two requirement ids added
during drafting, `R2a` and `S1a`, do not match what the coverage gate parses
(`**R<digits>**`, validated as `^R[0-9]+$`). They would have been silently
uncounted. Renumbered to `R24` and `S10`. The gate ignores unrecognised ids
rather than failing on them — it fails open on a malformed id — which is a
ratchet candidate for the owner, since gate scripts are human-owned.

**Open, and blocking the merge of this pull request.** The design doc cannot
pass the `plan` check. The `docs/` exemption is size-capped at 50 added lines and
the doc adds around 600; no plan can cover it either, since plans implement the
design doc's requirements and would have to predate it. This is the same
bootstrap shape as #2 and #4 — a document the pipeline requires but has no path
for — and it needs an owner decision: bypass and log, or add an uncapped
exemption for the design doc in `plan-resolve.sh`, which is a gate path and
therefore the owner's to change.

Next session: with the design doc landed, write the plan for the MVP milestone —
corpus and the cost checkpoint, no inference at all — as `docs/plans/<slug>.md`
on its own `docs/` pull request, before any code.

## 2026-08-14 — slice 1 built; the process, not the product, was the day's work

Slice 1 exists and works. Almost everything else in this session was the
orchestration path failing on first use, in six distinct ways, all now in
`docs/escapes.md`. Read that file before restarting: it is the accurate account
of what is broken. This entry carries what does not fit there — state, working
knowledge, and the order things must happen in.

### Where work stands

`feat/corpus-and-checkpoint` carries slice 1: the `index` command, the config
and CLI every later slice builds on, and 27 passing tests. It is open as #20 and
**red**, for a reason that has nothing to do with the code — see the queue below.

Four slices of the plan remain unbuilt: fetch, normalize/aliases, select, and
excerpt/bundle/estimate.

### The pull-request queue, and why the order is fixed

At the time of writing: #24 and #25 (ratchet entries), #22 (plan and template
parser fix), #20 (slice 1). They must land in that order:

1. **#24 then #25** — both append to `docs/escapes.md`, so the second will
   conflict trivially at the end of the table. Resolve by keeping both rows, and
   by merging `main` into the branch rather than rebasing it, since it is
   already pushed.
2. **#22 next** — it cites the escapes entry from #24, and the reviewer reads
   that file at the pull request's *base* commit. Cited before it lands, the
   claim is false at the only moment it is checked, and the review blocks. This
   already happened twice.
3. **#20 last** — rebase it onto the result. Its `plan` check cannot pass until
   #22's parser fix is on `main`, because the plan itself is unparseable
   without it and an unparseable plan empties the reviewer's facts table.

The general rule this cost a day to learn: **land the ratchet entry first, then
the document that cites it, then the work.**

### Uncommitted and in-flight

- The owner's zero-duration rule is **implemented but not committed**, in
  `src/find_best_mobo/commands/index.py` on `feat/corpus-and-checkpoint`. It
  reports the count of videos with no duration and warns above one, naming ids.
  It is deliberately uncommitted: a blind test-writer was still working on its
  tests, and those should land in history before the implementation.
- A worker branch `worker/cac-1-zerodur-tests` may exist with those tests. Check
  it committed before trusting it — a worker that does nothing still exits 0.
- The worker prompts live in `/tmp` and **will not survive a reboot**. They are
  worth rewriting from this entry rather than recovering.

### Orchestration: what actually works

- **Engine must be `claude`, not the default `codex`** — there is no codex
  subscription on this account, and the script only checks that the binary
  exists, not that it can run.
- **`--bypass-sandbox` is required.** Worktrees are created under
  `.claude/worktrees/`, which Claude Code protects, so a sandboxed worker cannot
  write a single file and exits 0 having done nothing. The owner approved the
  bypass knowingly; workers stay in isolated worktrees and every diff is read
  before assembly.
- **Always check `git log base..HEAD` per worker branch.** Exit code 0 means the
  engine ran, not that it produced anything.
- **Merge the test branch before the code branch**, so the blind tests precede
  the implementation in history and `blind-tests.sh` can report later edits.

### The technique that made blind authorship work

The first attempt produced two workers that disagreed on six points — the fake
surface, the config file's shape, how the entry point is called, and more. The
fix was a **shared contract block quoted verbatim into both briefs**: anything
both sides can observe must be identical in both, or it does not reach one of
them. After that, the six settled points all held and the single remaining
disagreement was the one rule that predated the block (record ordering), which
had reached the coder's brief only.

Corollary worth keeping: when the two disagree, the plan is the arbiter. If the
plan is silent, the plan is what needs fixing — not whichever side is easier to
edit.

### Watching pull requests

Wait on **"no check is still pending"**, never on "the pull request is no longer
open". A failing pull request never leaves the open state, so the second
condition makes red indistinguishable from still-running until a timeout, and
indistinguishable from success if nothing is watching at all.

### Known rough edges in slice 1, already recorded in `docs/architecture.md`

- Flat channel listing has no upload date without the
  `youtubetab:approximate_date` extractor argument; the dates it then gives are
  approximate, so a video near the 2023-01-01 boundary may land on either side.
- A missing upload date is stored as `0001-01-01` — deterministic, and obviously
  not a real date.
- A missing duration reads as 0 and therefore classifies as a Short. The owner's
  rule accepts exactly one such video (a stream in progress) and treats two or
  more as evidence of another cause; that is what the uncommitted change reports.

### Next session

Land the queue in the order above, commit the zero-duration change behind its
tests, then build slice 2 (transcript fetch and the failure ledger) with the
same two-worker pattern. The parser fix the owner is adding to the template —
fixture tests for `plan-parse.sh`, plus a check that every real plan parses on
its own pull request — is what stops this session's central failure recurring.
