# Backlog — approvals — find-best-mobo

One line per backlog item that has been approved for work, and **who approved
it**. Append only; nothing here is ever edited.

## Why this is a file and not a section

`docs/BACKLOG.md` has an "Approved" heading, and moving an item into it is
structurally impossible: the backlog is held append-only
(`.github/scripts/backlog-append-only.sh`), landed items never move, and moving
one from Proposed to Approved changes its position — which that check fails.
Approval by moving was never available. This file is what makes approval
recordable at all.

## It is ADVISORY, and that is the owner's ruling

> i would make it advisory i guess. it might be worth making a distinction
> between approved by me and approved by the oracle. both allows work to be
> done, but if a reviewer is looking at it, it is genuinely more informative for
> the reviewer to know who approved, as the oracle might be wrong.

**No gate reads this file to decide whether work may proceed.** An approval gate
on this path would put the owner back in the loop at 3am, which is the single
thing the unattended arrangement exists to prevent — the same reasoning that
kept `docs/BACKLOG.md` out of `CODEOWNERS`.

What it buys instead is **provenance**. A reviewer reading a plan built on
`BL-7` can see whether `BL-7` was approved by the owner or by the oracle, and
those read differently: the oracle can be wrong, and an item it blessed is a
different kind of evidence from one the owner chose. Until this file existed,
nothing anywhere recorded the difference.

## Format

One line each:

    - `BL-<n>` — approved by: owner | oracle — <date> — <one clause on why, or the OD-<n> that ruled it>

Rules, and they are the same three the backlog itself carries:

- **Name the id exactly as `docs/BACKLOG.md` spells it.** An approval that
  points at nothing is a claim nobody can check.
- **An oracle approval cites its decision.** `approved by: oracle` with no
  `OD-<n>` is an agent approving its own work with no trace back to the ledger
  that constrains it.
- **Never edit a landed line — append.** Changed your mind? Append a line that
  says so and repeats the id, exactly as `docs/escapes.md` handles the same
  problem. This file is held append-only by the same check as the other two
  backlog ledgers.

Approving an item here does not mean it is next, and it does not mean it is
still wanted. It means somebody said yes once, and says who.

---

_(nothing yet)_

- `BL-1` — approved by: owner — 2026-08-19 — blanket approval, 2026-08-19 ruling in docs/DECISIONS.md
- `BL-2` — approved by: owner — 2026-08-19 — blanket approval, 2026-08-19 ruling in docs/DECISIONS.md
- `BL-3` — approved by: owner — 2026-08-19 — blanket approval, 2026-08-19 ruling in docs/DECISIONS.md
- `BL-4` — approved by: owner — 2026-08-19 — blanket approval, 2026-08-19 ruling in docs/DECISIONS.md
- `BL-5` — approved by: owner — 2026-08-19 — blanket approval, 2026-08-19 ruling in docs/DECISIONS.md
- `BL-6` — approved by: owner — 2026-08-19 — blanket approval, 2026-08-19 ruling in docs/DECISIONS.md
- `BL-7` — approved by: owner — 2026-08-19 — blanket approval, 2026-08-19 ruling in docs/DECISIONS.md
- `BL-8` — approved by: owner — 2026-08-19 — blanket approval, 2026-08-19 ruling in docs/DECISIONS.md
- `BL-9` — approved by: owner — 2026-08-19 — blanket approval, 2026-08-19 ruling in docs/DECISIONS.md
- `BL-10` — approved by: owner — 2026-08-19 — blanket approval, 2026-08-19 ruling in docs/DECISIONS.md
- `BL-11` — approved by: owner — 2026-08-19 — blanket approval, 2026-08-19 ruling in docs/DECISIONS.md
- `BL-12` — approved by: owner — 2026-08-19 — blanket approval, 2026-08-19 ruling in docs/DECISIONS.md
- `BL-13` — approved by: owner — 2026-08-19 — blanket approval, 2026-08-19 ruling in docs/DECISIONS.md
