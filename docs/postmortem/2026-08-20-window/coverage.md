# coverage.md

`events.jsonl` holds **616** records. One JSON object per line. Sorted by lane,
then by `timestamp_utc` inside the lane. `event_id` is `<lane>-NNNN`, sequential inside the lane.

## What was read

| source | branch | read at | what came out |
| --- | --- | --- | --- |
| `docs/runs/20260820T085531Z/run.md` | `run/local` | `89351d71` | machine log, tier `recorded` |
| `docs/runs/20260820T102917Z/run.md` | `run/local` | `89351d71` | machine log, tier `recorded` |
| `docs/runs/20260820T112543Z/run.md` | `run/local` | `89351d71` | machine log, tier `recorded` |
| `docs/runs/<STAMP>/workers/*.log` (17 files) | `run/local` | `89351d71` | tier `derived` |
| `docs/runs/<STAMP>/reviews/<slug>/` (16 dirs) | `run/local` | `89351d71` | tier `derived` |
| commit metadata, 54 commits | `run/local` | `88400b80..89351d71` | tier `derived` |
| commit metadata, 46 commits | `run/web` | `88400b80..9525e3e6` | tier `derived` |
| `docs/runs/operator/local.md` | `chore/test-report-local` | tip `2f779a82` | F1-F36 + 25 phase rows, tier `reconstructed` |
| `docs/runs/operator/web.md` | `chore/test-report-web` | tip `bfc25c1a` | 23 F headings + 131 table rows, tier `reconstructed` |
| commit metadata, 17 commits | `chore/test-report-local` | `88400b80..2f779a82` | tier `derived` |
| commit metadata, 44 commits | `chore/test-report-web` | `88400b80..bfc25c1a` | tier `derived` |
| `docs/runs/operator/runner-2026-08-20.md` | `main` | `316ff10f` | RN-1..RN-3, tier `reconstructed` |
| commit metadata, 4 commits | `main` | `88400b80..52735f8c` | tier `derived` |

Excluded as instructed: commits `b443caa`, `eeeafab` and merge `5f0e372` on `run/local`
(2026-08-24 post-experiment cleanup). `run/local` was read at `89351d71`, not at the tip.
The GitHub API was not called. No commits, branches or pushes were made.

## Per lane

### `local` — 287 events, 2026-08-20T08:28:50Z to 2026-08-20T13:51:03Z

**By `event_class`**

| event_class | count |
| --- | ---: |
| `other` | 148 |
| `pr_merged` | 44 |
| `worker_dispatched` | 40 |
| `worker_result` | 22 |
| `ruling_issued` | 8 |
| `plan_written` | 7 |
| `check_failed` | 5 |
| `operator_action` | 5 |
| `template_update` | 4 |
| `uncertainty_opened` | 4 |

**By `phase`**

| phase | count |
| --- | ---: |
| `WAIT` | 101 |
| `(null)` | 98 |
| `STEWARD` | 53 |
| `ORACLE` | 35 |

**By `evidence_tier`**

| evidence_tier | count |
| --- | ---: |
| `recorded` | 200 |
| `derived` | 87 |

**By `timestamp_precision`**

| timestamp_precision | count |
| --- | ---: |
| `second` | 240 |
| `range` | 31 |
| `derived` | 16 |

**By `actor_role`**

| actor_role | count |
| --- | ---: |
| `driver` | 113 |
| `steward` | 70 |
| `oracle` | 51 |
| `bot` | 44 |
| `owner` | 7 |
| `unknown` | 2 |

### `web` — 177 events, 2026-08-20T08:24:10Z to 2026-08-20T16:15:00Z

**By `event_class`**

| event_class | count |
| --- | ---: |
| `pr_merged` | 35 |
| `operator_action` | 31 |
| `pr_opened` | 24 |
| `check_failed` | 22 |
| `ruling_issued` | 20 |
| `worker_dispatched` | 18 |
| `plan_written` | 12 |
| `template_update` | 9 |
| `uncertainty_opened` | 3 |
| `worker_result` | 3 |

**By `phase`**

| phase | count |
| --- | ---: |
| `(null)` | 84 |
| `WAIT` | 42 |
| `STEWARD` | 24 |
| `ORACLE` | 22 |
| `PLAN` | 2 |
| `RESTART` | 2 |
| `READY` | 1 |

**By `evidence_tier`**

| evidence_tier | count |
| --- | ---: |
| `reconstructed` | 131 |
| `derived` | 46 |

**By `timestamp_precision`**

| timestamp_precision | count |
| --- | ---: |
| `second` | 120 |
| `minute` | 55 |
| `range` | 2 |

**By `actor_role`**

| actor_role | count |
| --- | ---: |
| `driver` | 93 |
| `bot` | 43 |
| `oracle` | 22 |
| `steward` | 11 |
| `planner` | 4 |
| `owner` | 2 |
| `unknown` | 2 |

### `ledger-local` — 78 events, 2026-08-20T08:26:20Z to 2026-08-20T16:32:20Z

**By `event_class`**

| event_class | count |
| --- | ---: |
| `finding_logged` | 53 |
| `operator_action` | 17 |
| `check_failed` | 5 |
| `pr_merged` | 1 |
| `template_update` | 1 |
| `uncertainty_opened` | 1 |

**By `phase`**

| phase | count |
| --- | ---: |
| `(null)` | 53 |
| `RESTART/UPDATE` | 3 |
| `RUN STOPPED` | 3 |
| `DRIVER START` | 2 |
| `EVIDENCE LANDED` | 1 |
| `EVIDENCE SECURED BY HAND` | 1 |
| `LANE CLEAR` | 1 |
| `MID WRAP-UP` | 1 |
| `ORACLE` | 1 |
| `PR MERGED` | 1 |
| `PRE-DRIVER` | 1 |
| `PRE-DRIVER PR` | 1 |
| `RESTART/BLOCKED` | 1 |
| `RESTART/CLEANUP` | 1 |
| `RESTART/READY` | 1 |
| `RIG/BLOCKED` | 1 |
| `RIG/GATED` | 1 |
| `RIG/GATED-BOTH` | 1 |
| `RIG/WAIT` | 1 |
| `SETUP/UPDATE` | 1 |
| `STEWARD` | 1 |

**By `evidence_tier`**

| evidence_tier | count |
| --- | ---: |
| `reconstructed` | 61 |
| `derived` | 17 |

**By `timestamp_precision`**

| timestamp_precision | count |
| --- | ---: |
| `second` | 42 |
| `derived` | 36 |

**By `actor_role`**

| actor_role | count |
| --- | ---: |
| `owner` | 76 |
| `oracle` | 1 |
| `steward` | 1 |

### `ledger-web` — 67 events, 2026-08-20T08:25:07Z to 2026-08-20T16:29:04Z

**By `event_class`**

| event_class | count |
| --- | ---: |
| `finding_logged` | 67 |

**By `phase`**

| phase | count |
| --- | ---: |
| `(null)` | 67 |

**By `evidence_tier`**

| evidence_tier | count |
| --- | ---: |
| `derived` | 44 |
| `reconstructed` | 23 |

**By `timestamp_precision`**

| timestamp_precision | count |
| --- | ---: |
| `second` | 44 |
| `derived` | 23 |

**By `actor_role`**

| actor_role | count |
| --- | ---: |
| `owner` | 67 |

### `runner` — 7 events, 2026-08-20T16:47:02Z to 2026-08-24T08:58:42Z

**By `event_class`**

| event_class | count |
| --- | ---: |
| `finding_logged` | 4 |
| `pr_merged` | 2 |
| `other` | 1 |

**By `phase`**

| phase | count |
| --- | ---: |
| `(null)` | 7 |

**By `evidence_tier`**

| evidence_tier | count |
| --- | ---: |
| `derived` | 4 |
| `reconstructed` | 3 |

**By `timestamp_precision`**

| timestamp_precision | count |
| --- | ---: |
| `second` | 4 |
| `derived` | 3 |

**By `actor_role`**

| actor_role | count |
| --- | ---: |
| `unknown` | 4 |
| `owner` | 2 |
| `bot` | 1 |

## Reconciliation

Every file under `docs/runs/<STAMP>/workers/` and every directory under
`docs/runs/<STAMP>/reviews/` was enumerated from the git tree, independently of
the event walk over `run.md`. Each one is emitted as its own event. Mismatches
are listed here and flagged in the emitting event's `notes`.

### Counts

| run stamp | dispatch lines in `run.md` | worker logs on disk | review dirs on disk | fix sessions |
| --- | ---: | ---: | ---: | ---: |
| `20260820T085531Z` | 5 | 3 | 3 | 0 |
| `20260820T102917Z` | 4 | 4 | 3 | 0 |
| `20260820T112543Z` | 10 | 10 | 10 | 4 |

### Mismatch 1 — `steward-od-6` is dispatched three times and leaves one log

Run `20260820T085531Z` logs `dispatch steward worker (steward-od-6)` at
`09:03:58Z` (iteration 3), `09:18:32Z` (iteration 7) and `09:18:35Z`
(iteration 8). Only one file exists:
`docs/runs/20260820T085531Z/workers/steward-od-6.log`, whose header timestamp is
`2026-08-20T09:03:59Z` — the **first** dispatch.

- Iteration 7 failed at spawn (`branch 'worker/steward-od-6' already exists`) and
  the run.md records the branch being deleted.
- Iteration 8's dispatch has **no `WORKER_RESULT` line and no log file**. The run
  stops at `09:24:57Z` with exit code 0.

Two of the three dispatches therefore have no worker-log evidence. Flagged on
`local-0020` (the surviving log's event).

### Mismatch 2 — a worker log with no review directory

`docs/runs/20260820T102917Z/workers/oracle-20260820110210.log` exists. No
directory under `docs/runs/20260820T102917Z/reviews/` corresponds to it. The
other three workers in that run each have one. Flagged on that log's event.

The run stopped at `11:08:20Z` while iteration 8 was still waiting on PR #116.

### Mismatch 3 — four fix sessions, zero worker logs and zero review dirs

Run `20260820T112543Z` logs `dispatch fix session` four times (`13:19:47Z`,
`13:26:35Z`, `13:35:00Z`, `13:44:17Z`). `collect-evidence.sh` lands 10 worker
logs and 10 reviews for that run — none of them a fix session. A fix session's
only surviving evidence is the prose it appends into `run.md` itself, which is
emitted as four `worker_result` events (`local-0257`, `local-0264`,
`local-0272`, `local-0279`) carrying the line range of each block.

### No orphans in the other direction

No worker log lacks a dispatch line, and no review directory lacks a matching
worker log, in any of the three runs.

### Reviews skipped by the collector, per the driver's own console log

`docs/runs/operator/driver-logs/run-20260820T112543Z-console.log` on
`chore/test-report-local` records:

```
collect-evidence: 10 worker log(s) into docs/runs/20260820T112543Z/workers.
collect-evidence: 10 review(s) into docs/runs/20260820T112543Z/reviews (78 skipped).
```

The 78 skipped reviews are not on any branch in scope. They are named nowhere and
cannot be enumerated. Recorded as a gap, not resolved.

---

## Nulls, and why

`timestamp_utc`, `actor_role`, `event_class` and `notes` are never null.

| field | null count of 616 | why |
| --- | ---: | --- |
| `commit_sha` | 373 | log lines, ledger rows and worker/review artefacts are not commits |
| `phase` | 309 | commit metadata and ledger findings carry no phase; only the driver loop and the web ledger's driver tables state one |
| `iteration` | 337 | same — only loop events and the web driver tables carry an iteration number |
| `engine_model` | 590 | only 26 commits in the whole window carry a `Co-Authored-By` trailer; the schema takes this field from that trailer and from nowhere else |
| `pr_number` | 409 | most events are not attached to a pull request |
| `file_class` | 200 | `files_touched` is empty on log lines and ledger rows, which touch no path; a class over an empty set would be invented |
| `oracle_bytes_added` | 602 | the schema defines it for `ruling_issued` only; all 14 `ruling_issued` **commits** carry it, the 20 reconstructed web-ledger rulings cannot (no commit to measure) |
| `gap_seconds` | 453 | the schema says null unless both sides are `recorded`; only `lane=local` has `recorded` events at all, so every `web`, `ledger-local`, `ledger-web` and `runner` event has it null by rule |

`ids_referenced` is an empty array on 302 events (budget readings, iteration
markers, cleanup lines). Empty array, not null — the field is present and the
event genuinely references no id.

### `actor_role: unknown` — 8 events, listed

| event | what it is | why not derivable |
| --- | --- | --- |
| `local-0002` | `File BL-15…`, landed by PR #98, head `docs/bl-15-zero-duration-warning` | the branch is outside the driver loop; `run.md` names no worker for it |
| `local-0004` | `Land the setup-github.sh run logs…`, PR #99 | same — no worker id, no lane slug |
| `web-0065` | `File BL-15: OD-6 does not say…`, PR #110 | `run/web` has no machine log to name the worker |
| `web-0172` | `File BL-20, BL-21, BL-22…`, PR #141 | same |
| `runner-0002` `runner-0003` `runner-0004` | RN-2, RN-3, RN-1 | the `actor_role` vocabulary has no value for a third template-runner session; the file's own first line says "Written by the template runner session, not by either lane", but that is prose, not a derivable slug |
| `runner-0006` | `Redact machine-local paths…`, PR #144 | branch slug not recoverable from the merged history |

Deriving these from the git author was available and was **not** used, per the
brief: on `run/local` the owner's identity signs machine commits.

---

## Conflicts between sources — both emitted, none resolved

### C1 — run stop times: machine log vs operator ledger

| run | `run.md` `Stopped` line | `local.md` phase row `RUN STOPPED` | difference |
| --- | --- | --- | ---: |
| `20260820T085531Z` | `2026-08-20T09:24:57Z` | `2026-08-20T09:28:11Z` | +194 s |
| `20260820T102917Z` | `2026-08-20T11:08:20Z` | `2026-08-20T11:12:08Z` | +228 s |
| `20260820T112543Z` | `2026-08-20T13:49:30Z` | `2026-08-20T15:26:51Z` | **+5 841 s (97 min)** |

Both values are in `events.jsonl` — the machine value on `lane=local` (tier
`recorded`), the ledger value on `lane=ledger-local` (tier `reconstructed`).

### C2 — which pull requests run `20260820T085531Z` merged

`local.md` says "6 clean iterations, PRs #100-#103 merged". `run.md` for that
run logs eight iterations and three merges: **#101, #102, #103**. `web.md`
records **PR #100 as the web lane's**, base `run/web`, merged `08:59:00Z`.
Stated three ways; not reconciled here.

### C3 — `web.md` numbers two different findings `F21`

`docs/runs/operator/web.md` line 723 — "the run hit the engine's usage allowance…"
and line 767 — "the detector's HIGH-uncertainty branch has never fired…". The
brief says F1-F22; the file carries 23 `F` headings. Both are emitted, both
carry `ids_referenced` id `ledger-web/F21`, and both `notes` say DUPLICATE.

### C4 — the runner file's date

The brief says `runner-2026-08-20.md` "was written during the window by a third
session". Its only commit, `316ff10f`, has committer date `2026-08-20T16:47:02Z`
— after the last lane event of the window (`15:46:33Z`, PR #141 merged). It
merged to `main` on 2026-08-24. Both facts are in the `notes` of RN-1..RN-3.

### C5 — the two lanes' design and backlog layers

Six `OD` ids and eight `BL` ids carry different subjects on the two branches.
Full side-by-side in `collision-check.md`.

---

## Could not parse, or is not there

- **`run/web` landed no run directory for this window.** `docs/runs/` on
  `run/web` holds only `20260818T222639Z`, `20260818T225124Z`,
  `20260819T001105Z` and `manual-20260819`. There is no `20260820T*` directory
  and no machine log. Every `lane=web` event of tier `reconstructed` says so in
  its `notes`.
- **`run/web`'s branch history was reset mid-experiment.** `web.md` records
  `git checkout -B run/web origin/main` at `09:29Z`, so rounds 1 and 2 (PRs
  #100, #106) are not in the branch. Commit-derived web events therefore begin
  at `2026-08-20T10:26:14Z`, while the reconstructed timeline begins at
  `08:24:10Z`. The two tiers cover different spans of the same lane.
- **The driver console log path in the brief is wrong.** Given as
  `driver-logs/run-20260820T112543Z-console.log`; the file is at
  `docs/runs/operator/driver-logs/run-20260820T112543Z-console.log` on
  `chore/test-report-local`. It carries **no timestamps at all** — it repeats
  `run.md`'s 26 iterations as bare `deliver-loop:` lines. It is therefore not
  emitted as 26 duplicate events; only its two `collect-evidence` count lines are
  used, above.
- **`WORKER_RESULT`, `spawn-worker` and `Deleted branch` lines carry no
  timestamp of their own.** Each is emitted with
  `timestamp_precision: "range"` and the upper bound (the next timestamped log
  line) as `timestamp_utc`; the `notes` state both bounds.
- **Check-run names and conclusions are absent by instruction.** `check_failed`
  events carry the check names exactly as the driver printed them — for PR #133
  that is the literal string `plan ` and later `plan review `, trailing space
  included. `pr_number` is emitted on every event that has one so a later pass
  can join against the GitHub API.
- **Pull-request open times are absent.** Merge times come from the merge
  commit's committer date, as instructed. The `pr_opened` events on `lane=web`
  are the `.pr-request.json` marker commits and the ledger rows that record the
  App opening a pull request — not API data.
- **The 78 reviews skipped by `collect-evidence.sh`** are named nowhere in scope.

---

## Two mechanical rules worth stating

**`F` ids are namespaced by lane.** `local F1` and `web F1` are different
findings, so `ids_referenced` writes them as `ledger-local/F1` and
`ledger-web/F1`. The namespace is per lane *pair*, not per lane: the findings
live in the ledgers, so a reference to `F5` from a `run/local` commit and the
`F5` heading in `local.md` resolve to the same `ledger-local/F5`.

| lane of the event | `F` namespace | why |
| --- | --- | --- |
| `local`, `ledger-local` | `ledger-local` | same lane's ledger |
| `web`, `ledger-web` | `ledger-web` | same lane's ledger |
| `runner` | `ledger-local` | the runner file's only `F` reference names `docs/runs/operator/local.md` by path in the same sentence |

Counts: 244 `ledger-local/F*` references, 138 `ledger-web/F*`.

One known soft edge: the template-update commits on both `run/local` and
`run/web` cite `F` ids belonging to the *template's own changelog*. Which lane
those refer to is not mechanically recoverable, and they are namespaced by the
branch they were read on. Stated, not resolved.

`BL`, `OD`, `R`, `ESC`, `V`, `S` and `RN` are repository-wide and are not
namespaced — which is exactly why `collision-check.md` has anything in it.

**Ids come from the diff, not only the subject.** `ids_referenced` merges three
sources, each tagged: `subject` (the commit subject line), `diff` (tokens on
**added** lines of the commit diff, so a document that merely mentions an id
without changing it is not counted) and `body` (the commit message body, or the
log-line / ledger-row text). Range notation expands to every member. Nineteen distinct
ranges were found and expanded, among them `OD-1..OD-22`, `OD-6 through OD-11`,
`BL-1..13`, `BL-1 through BL-13`, `R8-R16`, `R1002-R1007` and `F31-F34`. A plain
hyphen counts as a range only for the undashed families (`R`, `V`, `S`, `F`); for
`BL`/`OD`/`ESC`/`RN` only `..` and ` through ` do, because a dash or em dash
between two dashed ids is prose — `OD-13 — OD-5` is a headline, not a range, and
is not expanded. `PRs #109-#117` is not an id and is not expanded. Measured on the two lane branches (100 commits in the window on `run/local` and
`run/web`), **42** carry no id in their subject line and are reachable only
through the diff — 42%. Across all five branches read (165 commits) it is 57,
or 35%.

---

## One observation the counts make on their own

`file_class` never takes the value `product` or `machinery` alone. Across all
616 events, 144 distinct paths were touched and **none** is under `src/`,
`tests/`, `acceptance/` or `data/`. The whole window is design, backlog, plan,
run-evidence and template machinery. Ten events are `mixed`, and all ten are
template updates or their merges.
