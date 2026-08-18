# Backlog — completed items — find-best-mobo

One line per backlog item that is finished, withdrawn, or superseded. Append
only; nothing here is ever edited.

**Why this is a separate file.** `docs/BACKLOG.md` is evidence: the oracle's
gate (`.github/scripts/oracle-decisions.sh`) resolves a decision's citation
against the `BL-<n>` ids in it, so an item that gets edited is a landed
decision's justification getting edited. Recording completion *in place* would
mean touching those items constantly, in exactly the way that must not be
possible — so completion is recorded here instead, and both files are held
append-only by `.github/scripts/backlog-append-only.sh`.

The pair is the point: the backlog says what was asked for and never changes;
this file says what happened to it. Neither can be revised to suit the other.

**Format**, one line each:

    - `BL-<n>` — done | withdrawn | superseded by `BL-<m>` — <date> — <what landed, or why it stopped>

Name the id exactly as the backlog spells it. If the work landed in a pull
request, say which — an id here with no trace is a claim, and this file is
where a reader comes to check one.

Do **not** remove an item from `docs/BACKLOG.md` when you add a line here. The
backlog is the record of what was asked; this is the record of what came of it.
A decision that cited `BL-7` must still find `BL-7` where it was.

---

_(nothing yet)_
