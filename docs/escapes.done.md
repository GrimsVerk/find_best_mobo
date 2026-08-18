# Escapes — closed — find-best-mobo

One row per escape in [`escapes.md`](escapes.md) that is **finished**: the defect
is fixed and the check that would have caught it exists. Append only; nothing
here is ever edited.

## Why this is a separate file

`docs/escapes.md` is append-only, and enforced
(`.github/scripts/escapes-append-only.sh`). That is what makes an `ESC-<n>`
citation mean something: a landed row cannot be reworded into evidence for
something else after a decision cited it.

The cost of that rule is that **an escape cannot be marked done in place**. So
"done" was only ever recorded in the ledger's *Check added* prose, which no
script reads — and the log grew forever without converging. `docs/BACKLOG.md`
hit the identical problem and got [`BACKLOG.done.md`](BACKLOG.done.md); this is
the same answer for the same reason.

The pair is the point: `escapes.md` says what went wrong and never changes;
this says what came of it. Neither can be revised to suit the other.

**Do not remove a row from `docs/escapes.md` when you add one here.** A decision
that cited `ESC-7` must still find `ESC-7` where it was.

## What this file is FOR, and the risk that comes with it

The delivery driver reads it. `.claude/scripts/deliver-phase.sh` subtracts the
ids closed here before deciding the oracle has evidence to rule on — so a
project with a long history reaches its real open questions instead of handing
the oracle everything it ever logged.

**That is also the risk.** A row here makes the oracle stop looking. If closing
an escape were free, the party that wanted it closed would be the party that
closed it. Three things hold that line, and only the third is mechanical:

- the file is append-only, so a closure cannot be quietly rewritten later;
- the closure is visible in a diff the review gate reads;
- **a closure row must name at least one repository path, and that path must
  exist.** The check refuses a row that says "closed — it is fine now".

That last rule is deliberately weak: it proves a file is there, not that the
file checks anything. The stronger versions were rejected — requiring the named
check to *run* puts a test harness inside a gate, and requiring the owner's
approval puts them back in the loop at 3am, which is the failure the unattended
arrangement exists to prevent. If a bogus closure is ever observed, that is an
escape and the ratchet applies.

## What does NOT belong here

- **An escape whose fix is built but never observed working.** Say so in the
  ledger row instead. Closing it erases the one fact worth keeping — that
  nobody has seen it work — and this project has a row that has been wrong
  about exactly that three times.
- **An escape you decided not to fix.** That is still a closure, and it is
  welcome, but write the reasoning: which check was declined and why. A reader
  who disagrees can then disagree with something.
- **A stub.** An entry whose ledger row still reads *unverified — pending* is
  not closed; it is a proposal nobody has built.

## Format

One row each. The **Check** column carries the path, in backticks:

| Id | Date | Check that closes it | How it was demonstrated |
| --- | --- | --- | --- |
| _ESC-&lt;n&gt;_ | _YYYY-MM-DD_ | _`path/to/the/check`_ | _red against the defect, green against the fix — or, for a declined check, what was declined and why_ |

<!-- The placeholder id above is written so it does not match ESC-<digits>, the
same trick the escapes ledger uses, so this skeleton never trips its own check
on a fresh project. Append real rows below. -->
