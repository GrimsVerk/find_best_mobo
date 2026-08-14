# Template fix prompt

The brief sent to an agent working in the **template repository** — the one this
project's `_src_path` points at — after the 2026-08-14 session found that every
orchestration defect it hit originated upstream and would recur in the next
generated project.

Kept here for safekeeping and provenance. It is derived entirely from
`docs/escapes.md`; that file is the evidence, this is the distilled ask. Neither
replaces the other: the log stays as this project's incident record, and the
template needs its own record so the reasoning behind each check survives where
the check lives.

The prompt was written to stand alone, because the agent receiving it has not
seen this project's history.

---

You are working in the project template repository that generates new projects
(the one this repo's `_src_path` points at). A generated project has just spent a
full working session hitting defects that all originate here. Every one of them
will recur in the next generated project. Your job is to fix them at the source,
each with a check that would have caught it.

Follow this repository's own AGENTS.md and its planning process. The work below
is more than one plan's worth — propose a split, and confirm it before building.

Ground rule, from the ratchet: a fix without a check buys one bug. Every item
below names a required check. If you believe a check cannot work, say so and
propose a different one — do not record an untested check as though it were
verified. One of the entries below exists precisely because that happened.

## P1 — Orchestration has never successfully run

`.claude/scripts/spawn-worker.sh` cannot launch a working worker. Four separate
faults, each independently fatal:

1. It calls `codex exec --full-auto`. That argument no longer exists in
   codex-cli (0.147.0 rejects it); the current equivalent is `--approve-for-me`.
   Every codex worker dies before reading its prompt.

2. It creates worktrees under `.claude/worktrees/`. Claude Code treats `.claude/`
   as a protected directory, so a sandboxed worker is refused every write —
   `Write`/`Edit` denied, `touch` rejected as outside the allowed working
   directory, `git hash-object -w` left unapproved. Headless mode cannot prompt,
   so every denial is silent. The worker produces nothing and exits 0.
   Fix: create worktrees somewhere unprotected. Do not make `--bypass-sandbox`
   the workaround — that drops the sandbox for unreviewed model-written code.

3. A worker that does nothing exits 0, so the script reports success for a run
   that wrote no file and made no commit. The only thing catching that today is
   the orchestrator remembering to diff each branch against its base — prose in
   `.claude/commands/orchestrate.md`, enforced by nothing.
   Fix: the script itself compares the branch to its base after the engine
   returns and exits non-zero when the worker committed nothing.

4. It checks only `command -v "$ENGINE"`, which says nothing about whether the
   engine can authenticate. The default engine is `codex`; on an account with no
   codex subscription the default path cannot work at all — and it fails as an
   argument error, which sends the first diagnosis at entirely the wrong problem.
   Fix: a real preflight that confirms the engine can run, failing with
   "engine X is installed but not usable" before any worktree is created.

Required check: a smoke test that spawns one trivial worker per engine and
asserts it committed. It costs subscription budget, so make it on-demand rather
than part of every CI run — but make it exist, because all four faults above
survived only because nothing ever exercised this path until a human needed it.

## P2 — Gates that misfire or fail open

5. `.github/scripts/plan-parse.sh` treats every heading matching
   `^#+[[:space:]]*Slice` as a slice. `docs/plans/_TEMPLATE.md` contains a
   `## Slices` section banner, which matches — so it parses as a slice declaring
   no files and no estimate, and the whole plan is rejected. Every plan copied
   from the template inherits this.
   The symptom is badly misleading: the plan check fails, the review gate
   receives an empty mechanical facts table and blocks on that alone, and neither
   message points at the heading. In the generated project this surfaced two pull
   requests downstream of its cause.
   Fix, three parts: tighten the pattern to require whitespace after the word;
   rename the banner in `_TEMPLATE.md` to something not beginning with "Slice";
   and add the checks below.

   Required checks, on every pull request:
   - Parser fixtures: one valid plan and several malformed ones — including a
     plural section banner, a slice with no estimate, and a slice with no file
     list — asserting what the parser returns for each.
   - Every real plan under `docs/plans/` must parse, so a malformed plan fails on
     its own pull request where the error can point at the right document. Skip
     underscore-prefixed files: the template's placeholders are unparseable by
     design, so do NOT write a check that parses `_TEMPLATE.md` itself. That
     exact check was proposed downstream, would have been red from the day it was
     added, and was caught only by chance before it landed.

6. `.github/scripts/coverage.sh` recognises only `**R<digits>**` and validates a
   plan's `covers:` entries against `^R[0-9]+$`. Any other id — `R2a`, a typo, a
   renumbering slip — is silently ignored rather than rejected. It is never
   counted as covered and never reported as missing, and a plan claiming it is
   rejected with no hint why. A gate that ignores what it cannot parse fails
   open.
   Fix: fail on any `**R…**` or `**S…**` in the design doc that does not match
   the id pattern.
   Required check: a fixture design doc containing a malformed id, asserting the
   script fails.

7. `.github/scripts/plan-resolve.sh` caps the `chore/`/`docs/` planning exemption
   at 50 added lines. The cap is right for ordinary documentation, but there is
   no path at all for the two documents the process itself demands: a completed
   design doc runs to several hundred lines, and `docs/plans/_TEMPLATE.md` is 124
   lines before anything is filled in, so every plan exceeds the cap too. A plan
   branch also cannot resolve to a plan that does not yet exist on the default
   branch — which is the rule's whole point.
   Downstream this forced three separate owner bypasses in one session. A gate
   bypassed three times in a day is one nobody will trust on the day it matters.
   Fix: give those two documents a path — for example, exempt from the size cap a
   branch whose additions are confined to `docs/plans/` or `docs/DESIGN.md`. A
   branch adding a plan is not skipping planning; it is the planning.
   Required check: fixture branches asserting the exemption applies to a
   plans-only branch and still does not apply to a branch that also touches code.

## P3 — Process documentation that let avoidable failures happen

These are wording fixes, but each corresponds to a real failure:

8. `.claude/commands/orchestrate.md` should require that both workers for a slice
   receive an identical shared contract block, quoted verbatim into each brief.
   Downstream, the first attempt gave the coder a rule the test author never saw;
   the two built to different contracts and disagreed at assembly about a
   behaviour the plan never stated. The second attempt used a shared block and
   the disagreements vanished. State plainly: anything both sides can observe
   belongs in the plan's signatures or its prose, never in one prompt alone.

9. The same file should state the wait condition for pull request checks:
   wait until no check is still pending, never until the pull request is no
   longer open. A failing pull request never leaves the open state, so the second
   condition makes red indistinguishable from still-running, and — where nothing
   is watching at all — indistinguishable from success. Downstream, a red pull
   request sat unnoticed until the owner mentioned it.

10. `AGENTS.md` should state the ordering rule for cross-referencing governance
    documents: land the ratchet entry first, then the document that cites it,
    then the work. The review gate reads `docs/escapes.md` at the pull request's
    base commit, so a document citing an entry that has not landed makes a claim
    that is false at the only moment it is checked. Downstream this blocked the
    same pull request twice.

11. `AGENTS.md` should require that a recorded ratchet check be either
    demonstrated — red against the defect, green against the fix — or explicitly
    marked as an unverified proposal. An untested suggestion in that column reads
    with the same authority as a verified one.

12. Consider a narrow relaxation: allow one pull request to carry an
    `docs/escapes.md` entry together with the fix it describes, when they share a
    root cause. The reason gated documents must travel alone is that a change
    must not carry its own revision of the standard it is judged against; an
    append-only incident log is arguably not that standard. Downstream, one root
    cause fanned into four serialized pull requests and the chain blocked on
    itself. Weigh this against the risk of an agent logging its own escape
    self-servingly — if you reject it, say so in the file so it is not
    relitigated.

## Also add

A short, project-agnostic record in this repository of defects found in
generated projects and the checks added for them — one line each, the same shape
as `docs/escapes.md`. The originating project keeps its own log as its incident
record; this one exists so the reasoning behind each check survives here, where
the check lives.
