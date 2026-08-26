# Experiment window, 2026-08-20 — mechanical event skeleton

This directory is **evidence**, not analysis. It records what happened during the
2026-08-20 delivery window, event by event, with a source reference on every
record. It does not say what any of it means. Glossing the ids and drawing
conclusions is a later pass.

Nothing here was interpreted. Where two sources disagree, both are recorded and
the disagreement is flagged. Where a value could not be read, the field is
`null` and the `notes` say why.

## Files

| file | what it is |
| --- | --- |
| `events.jsonl` | 616 events, one JSON object per line, 19 fields each |
| `collision-check.md` | ids that exist on both lane branches with different text |
| `coverage.md` | counts per lane, reconciliation gaps, every null, every conflict |
| `tools/` | the exact scripts that produced the three files above |

## Scope

Merge base — the last pre-experiment commit on every branch:

```
88400b8036bb20b4a2eb6233d98731f4821a4723
```

| branch | read at | note |
| --- | --- | --- |
| `run/local` | `89351d71b44fcc5382f2708cbeba6c2c905c7ae0` | **pinned, not the tip** |
| `run/web` | `9525e3e6be747c972d3e046a3f0a22367416274b` (tip) | |
| `chore/test-report-local` | `2f779a82` (tip) | |
| `chore/test-report-web` | `bfc25c1a` (tip) | |
| `main` | `52735f8c` (tip) | for `docs/runs/operator/runner-2026-08-20.md` |

`run/local` is read at the pinned commit because commits `b443caa`, `eeeafab`
and merge `5f0e372` (2026-08-24) edit three window `run.md` files **in place**
after the fact. They are post-experiment cleanup. They are excluded as events
and no window file is read at the tip.

The GitHub API was **not** called. Pull-request open times, check-run names and
check conclusions are deliberately absent. `pr_number` is emitted on every event
that has one, so a later pass can join against the API. Merge times come from
the merge commit's committer date.

## The five lanes

| lane | events | what it is |
| --- | ---: | --- |
| `local` | 287 | `run/local` — machine logs, worker logs, review artefacts, commits |
| `web` | 177 | `run/web` — **reconstruction only**, see below |
| `ledger-local` | 78 | `docs/runs/operator/local.md`, findings F1–F36 |
| `ledger-web` | 67 | `docs/runs/operator/web.md`, findings F1–F22 |
| `runner` | 7 | `docs/runs/operator/runner-2026-08-20.md`, RN-1 to RN-3 |

## Evidence tiers

Every event carries one. This is the field to read first.

| tier | meaning | count |
| --- | --- | ---: |
| `recorded` | read from a machine log line | 200 |
| `derived` | computed from commit or worker-log metadata | 198 |
| `reconstructed` | hand-typed ledger prose | 218 |

**`run/web` landed no run directory for this window.** `docs/runs/` on `run/web`
holds only `20260818T222639Z`, `20260818T225124Z`, `20260819T001105Z` and
`manual-20260819`. There is no `20260820T*` directory and no machine log for the
web lane at all. Its entire timeline is `reconstructed` from `web.md` prose plus
commit dates, and every such event says so in its `notes`.

## The three headline gaps

1. **`run/web` has no machine log** (above), and its branch history was reset
   mid-experiment — `web.md` records `git checkout -B run/web origin/main` at
   `09:29Z`, so rounds 1 and 2 are not in the branch. Commit evidence starts at
   `10:26Z`; the hand-typed timeline starts at `08:24Z`.
2. **Three reconciliation mismatches.** `steward-od-6` was dispatched three
   times and left one log. One worker log has no review directory. Four fix
   sessions left no log and no review at all.
3. **The run-stop times disagree by 97 minutes** for run `20260820T112543Z`:
   the machine log says `13:49:30Z`, the operator ledger says `15:26:51Z`. Both
   are in `events.jsonl`. Neither is preferred.

`coverage.md` has all of these in full, plus two more conflicts and every null.

## Reading `events.jsonl`

```
jq -c 'select(.lane=="local" and .evidence_tier=="recorded")' events.jsonl
jq -r 'select(.event_class=="ruling_issued") | [.event_id,.timestamp_utc,.oracle_bytes_added.lines_added] | @tsv' events.jsonl
jq -r '.ids_referenced[] | select(.family=="OD") | .id' events.jsonl | sort | uniq -c | sort -rn
```

Field notes worth knowing before you query:

- **`actor_role` is never taken from the git author.** On `run/local` the
  owner's identity signs machine commits, so the author field is meaningless
  for this. Roles come from the worker id, the worker-log filename, or the
  branch slug. Eight events could not be resolved and say `unknown`;
  `coverage.md` lists all eight and why.
- **`ids_referenced` comes from the diff, not just the subject.** 42 of the 100
  commits on the two lane branches carry no id in their subject line. Each
  reference is tagged `subject`, `diff` (added lines only) or `body`. Range
  notation such as `OD-1..OD-22`, `BL-1 through BL-13` and `R1002-R1007`
  expands to every member.
- **`F` ids are namespaced by lane**, because `ledger-local/F1` and
  `ledger-web/F1` are different findings. Everything else — `BL`, `OD`, `R`,
  `ESC`, `V`, `S`, `RN` — is repository-wide and is not namespaced. That is
  exactly why `collision-check.md` has anything in it.
- **`gap_seconds` is null unless both sides are `recorded`.** Only `lane=local`
  has recorded events, so it is null on 453 of 616 events by rule, not by
  omission.
- **`file_class` is null when `files_touched` is empty** — a log line touches no
  path, and a class over an empty set would be invented.

## Rebuilding

The three files are reproducible byte-for-byte from the repository:

```
git fetch origin 'refs/heads/*:refs/remotes/origin/*' --prune
docs/postmortem/2026-08-20-window/tools/rebuild.sh /tmp/out
diff /tmp/out/events.jsonl docs/postmortem/2026-08-20-window/events.jsonl
```

`rebuild.sh` is read-only. It makes no commit, branch or push. It needs
`python3` and `git`, nothing else.

`tools/coverage_narrative.md` is the hand-written half of `coverage.md`
(reconciliation, nulls, conflicts). `tools/mk_coverage.py` generates the
counted half; `rebuild.sh` concatenates them.
