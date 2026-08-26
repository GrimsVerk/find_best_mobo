# collision-check.md

Mechanical diff of `docs/DESIGN.oracle.md` and `docs/BACKLOG.md` between the two lanes.

- Left: `run/local` read at `89351d71b44fcc5382f2708cbeba6c2c905c7ae0` (the pinned commit, not the branch tip).
- Right: `run/web` read at `9525e3e6be747c972d3e046a3f0a22367416274b` (branch tip).

An id is reported when it is present on **both** branches and the text under it differs.
**Nothing here is resolved.** Both texts are stated side by side; choosing between them is a later pass.

Sectioning rule: a section starts at a line matching `#{1,6} <ID>` or `- **<ID>**`, and runs to the next such line.

## `docs/DESIGN.oracle.md`

- ids present on both branches: **18**
- text differs: **6** — OD-13, OD-14, OD-15, OD-16, OD-17, OD-18
- text identical: **12** — OD-1, OD-2, OD-3, OD-4, OD-5, OD-6, OD-7, OD-8, OD-9, OD-10, OD-11, OD-12
- `run/local` only: OD-19, OD-20, OD-21, OD-22
- `run/web` only: (none)

### OD-13

| lane | headline as written | lines | bytes |
| --- | --- | ---: | ---: |
| `run/local` | ## OD-13 — OD-5 is superseded: the whole-transcript path is uncapped, and an over-cap transcript spans sequential bundles | 29 | 4351 |
| `run/web` | ## OD-13 — OD-5/R1001 is superseded by the owner's ruling; the capped plan is re-cut to the clustering design before anything builds it | 35 | 4498 |

**Headlines disagree: the two lanes gave this id to different subjects.**

Opening of each side, verbatim (list-form entries wrap, so one line is not the whole headline):

```
run/local:
  ## OD-13 — OD-5 is superseded: the whole-transcript path is uncapped, and an over-cap transcript spans sequential bundles
  - **Date:** 2026-08-20
  - **Evidence:** BL-14, BL-13
  - **Requirements added:** R1008

run/web:
  ## OD-13 — OD-5/R1001 is superseded by the owner's ruling; the capped plan is re-cut to the clustering design before anything builds it
  - **Date:** 2026-08-20
  - **Evidence:** BL-14
  - **Requirements added:** (none)
```

### OD-14

| lane | headline as written | lines | bytes |
| --- | --- | ---: | ---: |
| `run/local` | ## OD-14 — The zero-duration warning judges the listing shape, not the count | 25 | 3721 |
| `run/web` | ## OD-14 — R1002's caption-split matching is per-cue; a split straddling two cues stays out of scope | 23 | 3305 |

**Headlines disagree: the two lanes gave this id to different subjects.**

Opening of each side, verbatim (list-form entries wrap, so one line is not the whole headline):

```
run/local:
  ## OD-14 — The zero-duration warning judges the listing shape, not the count
  - **Date:** 2026-08-20
  - **Evidence:** BL-15, ESC-21
  - **Requirements added:** R1009

run/web:
  ## OD-14 — R1002's caption-split matching is per-cue; a split straddling two cues stays out of scope
  - **Date:** 2026-08-20
  - **Evidence:** BL-15, BL-8
  - **Requirements added:** (none)
```

### OD-15

| lane | headline as written | lines | bytes |
| --- | --- | ---: | ---: |
| `run/local` | ## OD-15 — R1002 applies within one cue; a cross-cue split is counted, never matched | 27 | 5347 |
| `run/web` | ## OD-15 — R1002's variant fixture is the declared reconstruction, and the reconstruction is the reference set | 27 | 4381 |

**Headlines disagree: the two lanes gave this id to different subjects.**

Opening of each side, verbatim (list-form entries wrap, so one line is not the whole headline):

```
run/local:
  ## OD-15 — R1002 applies within one cue; a cross-cue split is counted, never matched
  - **Date:** 2026-08-20
  - **Evidence:** BL-16, BL-8
  - **Requirements added:** R1010

run/web:
  ## OD-15 — R1002's variant fixture is the declared reconstruction, and the reconstruction is the reference set
  - **Date:** 2026-08-20
  - **Evidence:** BL-16, BL-8
  - **Requirements added:** (none)
```

### OD-16

| lane | headline as written | lines | bytes |
| --- | --- | ---: | ---: |
| `run/local` | ## OD-16 — R1002's variant fixture is a labelled reconstruction; the lost original is recorded as unrecoverable | 39 | 5194 |
| `run/web` | ## OD-16 — R1003's regression title is the declared reconstruction, asserted by canonical and never by string | 27 | 4046 |

**Headlines disagree: the two lanes gave this id to different subjects.**

Opening of each side, verbatim (list-form entries wrap, so one line is not the whole headline):

```
run/local:
  ## OD-16 — R1002's variant fixture is a labelled reconstruction; the lost original is recorded as unrecoverable
  - **Date:** 2026-08-20
  - **Evidence:** BL-17, BL-8
  - **Requirements added:** (none)

run/web:
  ## OD-16 — R1003's regression title is the declared reconstruction, asserted by canonical and never by string
  - **Date:** 2026-08-20
  - **Evidence:** BL-17, BL-9
  - **Requirements added:** (none)
```

### OD-17

| lane | headline as written | lines | bytes |
| --- | --- | ---: | ---: |
| `run/local` | ## OD-17 — R1003's regression title is a labelled reconstruction; only the board name and the zero-`B850` property carry measured provenance | 43 | 5511 |
| `run/web` | ## OD-17 — R1005 binds `aliases --check`: an absent cache refuses, an empty cache is reported as an empty corpus | 28 | 3992 |

**Headlines disagree: the two lanes gave this id to different subjects.**

Opening of each side, verbatim (list-form entries wrap, so one line is not the whole headline):

```
run/local:
  ## OD-17 — R1003's regression title is a labelled reconstruction; only the board name and the zero-`B850` property carry measured provenance
  - **Date:** 2026-08-20
  - **Evidence:** BL-18, BL-9
  - **Requirements added:** (none)

run/web:
  ## OD-17 — R1005 binds `aliases --check`: an absent cache refuses, an empty cache is reported as an empty corpus
  - **Date:** 2026-08-20
  - **Evidence:** BL-18, BL-7
  - **Requirements added:** (none)
```

### OD-18

| lane | headline as written | lines | bytes |
| --- | --- | ---: | ---: |
| `run/local` | ## OD-18 — `--help` after a subcommand is forwarded: the subcommand's help prints | 20 | 3316 |
| `run/web` | ## OD-18 — After a subcommand name, `-h/--help` stays the dispatcher's; a subcommand parser never advertises it | 24 | 3494 |

**Headlines disagree: the two lanes gave this id to different subjects.**

Opening of each side, verbatim (list-form entries wrap, so one line is not the whole headline):

```
run/local:
  ## OD-18 — `--help` after a subcommand is forwarded: the subcommand's help prints
  - **Date:** 2026-08-20
  - **Evidence:** BL-19, BL-5
  - **Requirements added:** (none)

run/web:
  ## OD-18 — After a subcommand name, `-h/--help` stays the dispatcher's; a subcommand parser never advertises it
  - **Date:** 2026-08-20
  - **Evidence:** BL-19, BL-5
  - **Requirements added:** (none)
```

## `docs/BACKLOG.md`

- ids present on both branches: **22**
- text differs: **9** — BL-13, BL-15, BL-16, BL-17, BL-18, BL-19, BL-20, BL-21, BL-22
- text identical: **13** — BL-1, BL-2, BL-3, BL-4, BL-5, BL-6, BL-7, BL-8, BL-9, BL-10, BL-11, BL-12, BL-14
- `run/local` only: BL-23
- `run/web` only: (none)

### BL-13

| lane | headline as written | lines | bytes |
| --- | --- | ---: | ---: |
| `run/local` | ### BL-13 — Send whole transcripts instead of excerpts | 35 | 1933 |
| `run/web` | ### BL-13 — Send whole transcripts instead of excerpts | 41 | 2183 |

Headlines are byte-identical; the section bodies differ. Full unified diff:

```diff
--- run/local
+++ run/web
@@ -35 +35,7 @@
 proposal and neither the design nor any plan has been edited.
+
+## Uncertainties awaiting oracle ruling
+
+_(nothing yet — filed by `/plan` when a design leaves a question open; format:_
+_`BL-<n>` — the question, the proposed default, HIGH or LOW risk, one line on_
+_why that class, and `— filed by: plan`.)_
```

Note, factual: every added line is the document section heading
`## Uncertainties awaiting oracle ruling` and its explanatory italics, which follow
BL-13 on `run/web` and carry no id of their own, so the sectioning rule above
attributes them to BL-13. BL-13's own prose is identical on both branches.
Reported because the rule produced a difference. Not resolved.

### BL-15

| lane | headline as written | lines | bytes |
| --- | --- | ---: | ---: |
| `run/local` | ### BL-15 — The zero-duration warning cries wolf on every real run | 80 | 4526 |
| `run/web` | - **BL-15** — Must OD-6/R1002's caption-split matching also recover a split that | 16 | 1190 |

**Headlines disagree: the two lanes gave this id to different subjects.**

Opening of each side, verbatim (list-form entries wrap, so one line is not the whole headline):

```
run/local:
  ### BL-15 — The zero-duration warning cries wolf on every real run
  The `index` command warns loudly when more than one video reports no duration,
  on the reasoning that a missing duration reads as 0, classifies as a Short, and
  silently drops a real video. Exactly one is expected and harmless — a stream in

run/web:
  - **BL-15** — Must OD-6/R1002's caption-split matching also recover a split that
    straddles two cues — `toma` ending one cue and `hawk` starting the next?
    `find_mentions` normalizes and scans one cue at a time, so a token-join rule
    stated over "the text being matched" leaves cue-spanning splits invisible, and
```

### BL-16

| lane | headline as written | lines | bytes |
| --- | --- | ---: | ---: |
| `run/local` | - **BL-16** — Does R1002 (OD-6) have to recover an alias split across a **cue | 24 | 1827 |
| `run/web` | - **BL-16** — What is BL-8's measured 52-variant set? R1002 says "BL-8's | 15 | 1078 |

**Headlines disagree: the two lanes gave this id to different subjects.**

Opening of each side, verbatim (list-form entries wrap, so one line is not the whole headline):

```
run/local:
  - **BL-16** — Does R1002 (OD-6) have to recover an alias split across a **cue
    boundary** — `toma` ending one cue and `hawk` beginning the next — or only a
    split inside one cue's text? R1002 fixes the rule ("the concatenation of
    adjacent whole tokens", every alias space landing on a token boundary) but

run/web:
  - **BL-16** — What is BL-8's measured 52-variant set? R1002 says "BL-8's
    measured 52-variant set lands as a fixture", but the list itself was never
    committed — the backlog entry records the count (49 matched + 3 failures), the
    three named failures and the damage classes, and nothing in the tree, the
```

### BL-17

| lane | headline as written | lines | bytes |
| --- | --- | ---: | ---: |
| `run/local` | - **BL-17** — What are BL-8's 52 measured caption variants? R1002 (OD-6) says | 18 | 1323 |
| `run/web` | - **BL-17** — What title does OD-7/R1003's regression case use? R1003 says "the | 14 | 1039 |

**Headlines disagree: the two lanes gave this id to different subjects.**

Opening of each side, verbatim (list-form entries wrap, so one line is not the whole headline):

```
run/local:
  - **BL-17** — What are BL-8's 52 measured caption variants? R1002 (OD-6) says
    "BL-8's measured 52-variant set lands as a fixture", but BL-8 records only the
    count, the three named failures (`toma hawk`, `aor us master`,
    `air us elite`) and the damage classes — the list itself is in no commit, no

run/web:
  - **BL-17** — What title does OD-7/R1003's regression case use? R1003 says "the
    real B850I review's title auto-includes on its chipset", and that title is not
    in the repository: BL-9 records the board (MSI MPG B850I Edge TI) and the
    video's duration, while no index, fixture, journal entry or `docs/runs/`
```

### BL-18

| lane | headline as written | lines | bytes |
| --- | --- | ---: | ---: |
| `run/local` | - **BL-18** — What is the real B850I review's title? R1003 (OD-7) names the | 17 | 1255 |
| `run/web` | - **BL-18** — Does OD-9/R1005 bind `aliases --check`? R1005 states its rule over | 15 | 1048 |

**Headlines disagree: the two lanes gave this id to different subjects.**

Opening of each side, verbatim (list-form entries wrap, so one line is not the whole headline):

```
run/local:
  - **BL-18** — What is the real B850I review's title? R1003 (OD-7) names the
    regression as "the real B850I review's title auto-includes on its chipset",
    and that title is in no commit, no journal entry and no run record. BL-9
    records the board (`MSI MPG B850I Edge TI`), the 33-minute duration and the

run/web:
  - **BL-18** — Does OD-9/R1005 bind `aliases --check`? R1005 states its rule over
    "a pipeline stage", and the repository says this command is not one:
    `scripts/run.sh` calls it a diagnostic and `docs/plans/run-scripts.md` says
    "the pipeline is four stages, not five" — while `docs/architecture.md` calls
```

### BL-19

| lane | headline as written | lines | bytes |
| --- | --- | ---: | ---: |
| `run/local` | - **BL-19** — When `--help` follows a subcommand — `find-best-mobo aliases | 19 | 1463 |
| `run/web` | - **BL-19** — After a subcommand name, does `-h/--help` belong to the | 18 | 1270 |

**Headlines disagree: the two lanes gave this id to different subjects.**

Opening of each side, verbatim (list-form entries wrap, so one line is not the whole headline):

```
run/local:
  - **BL-19** — When `--help` follows a subcommand — `find-best-mobo aliases
    --help` — whose help prints, the subcommand's or the dispatcher's? R1006
    (OD-10) says every flag a subcommand *documents* is reachable from the CLI
    and that the dispatcher forwards arguments it does not recognise, but

run/web:
  - **BL-19** — After a subcommand name, does `-h/--help` belong to the
    subcommand or to the dispatcher? OD-10/R1006 makes the dispatcher forward
    arguments it does not recognise, and `--help` is one it does recognise — so
    `find-best-mobo aliases --help` prints the top-level help, never the
```

### BL-20

| lane | headline as written | lines | bytes |
| --- | --- | ---: | ---: |
| `run/local` | ### BL-20 — The driver will eventually commission a superseded plan slice | 22 | 1415 |
| `run/web` | - **BL-20** — May the pipeline take a subscription-usage reading itself, or must | 18 | 1320 |

**Headlines disagree: the two lanes gave this id to different subjects.**

Opening of each side, verbatim (list-form entries wrap, so one line is not the whole headline):

```
run/local:
  ### BL-20 — The driver will eventually commission a superseded plan slice
  `docs/plans/whole-transcript-threshold.md` is the owner's, `CODEOWNERS`-held, and
  partly wrong: OD-13 (and OD-5 before it) answered its "pending" ceiling
  uncertainty, and its slice 1 builds R28's routing without R5's clustering,

run/web:
  - **BL-20** — May the pipeline take a subscription-usage reading itself, or must
    a reading be handed to it? R26 names two readers — `claude -p "/usage"` and
    `omarchy-agent-usage-claude --limits-only --force` — and then says "The Python
    pipeline itself still cannot read them", while S3 calls its criterion
```

### BL-21

| lane | headline as written | lines | bytes |
| --- | --- | ---: | ---: |
| `run/local` | ### BL-21 — A superseded requirement id is uncoverable, and coverage says NOT PLANNED forever | 23 | 1516 |
| `run/web` | - **BL-21** — What is "actual usage" in R8 and S3, and what does the reported | 18 | 1339 |

**Headlines disagree: the two lanes gave this id to different subjects.**

Opening of each side, verbatim (list-form entries wrap, so one line is not the whole headline):

```
run/local:
  ### BL-21 — A superseded requirement id is uncoverable, and coverage says NOT PLANNED forever
  `.github/scripts/coverage.sh` builds its requirement universe from `docs/DESIGN.md`
  §5 and from column-anchored `**Requirements added:**` lines in
  `docs/DESIGN.oracle.md`. It does not read `**Requirements superseded:**`. The

run/web:
  - **BL-21** — What is "actual usage" in R8 and S3, and what does the reported
    delta compare? The projection is in tokens and its factor is chars-per-token
    (R7), while the only readings the design names return percentage points of a
    weekly subscription limit and no token count at all (R26). The two quantities
```

### BL-22

| lane | headline as written | lines | bytes |
| --- | --- | ---: | ---: |
| `run/local` | ### BL-22 — R1001's false gap livelocks the driver on a steward for OD-5 | 49 | 3165 |
| `run/web` | - **BL-22** — Where does the corrected chars-per-token factor land, so that | 17 | 1222 |

**Headlines disagree: the two lanes gave this id to different subjects.**

Opening of each side, verbatim (list-form entries wrap, so one line is not the whole headline):

```
run/local:
  ### BL-22 — R1001's false gap livelocks the driver on a steward for OD-5
  Measured, not predicted: on 2026-08-20 the driver dispatched a steward for
  **OD-5** — a decision OD-13 superseded in full — and that steward wrote no plan,
  because OD-5's only requirement R1001 is design history (retired by R1008), the

run/web:
  - **BL-22** — Where does the corrected chars-per-token factor land, so that
    subsequent projections use it? R8 says the factor is corrected "for subsequent
    projections"; today it is a `config.toml` key, R17 makes the cost levers
    configuration, and R23 promises byte-identical corpus and bundling output
```

## Not compared

- `docs/DESIGN.md`, `docs/VISION.md`, `docs/DECISIONS.md` — outside the two files this pass was asked to diff.
- Requirement ids (`R…`), vision ids (`V…`) and scope ids (`S…`) are not separately sectioned in either file, so they are not diffed here as ids. They appear in `ids_referenced` on the events that touch them.
- `F` ids: the two operator ledgers live on different branches and are not the subject of this diff. Their id collision is recorded in `coverage.md`.
