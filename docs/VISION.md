# Vision — find-best-mobo

**Not requirements.** `docs/DESIGN.md` says what gets built; this file says what
matters when two reasonable designs disagree. It is the tiebreaker an agent
reaches for when the evidence is genuinely ambiguous and nobody is awake to ask.

`CODEOWNERS` puts this file behind the owner. **No agent may edit it** — and
that is not a restriction bolted on, it is the mechanism: the oracle names, in
every decision it writes, the statement here that it leaned on
(`docs/DESIGN.oracle.md`). When a decision comes out wrong, the owner edits the
statement rather than arguing with the decision, and every future decision moves
with it.

So write it for that use. A sentence here is worth having if a reasonable agent
could cite it to justify one choice over another. A sentence nobody could ever
cite is decoration.

## What this project is for

<!-- One paragraph. The outcome, in the owner's words. Not a feature list —
     the thing that would be true if this worked. -->

## Priorities, in order

<!-- Ordered, and the order is the useful part. "Correctness, then cost, then
     speed" answers a real question; an unordered list of virtues does not. -->

1.
2.
3.

## What I would trade away

<!-- The half that actually decides things. Name what is expendable: features,
     completeness, generality, polish, latency, breadth of support. An agent
     that knows what may be sacrificed can make a call; one that only knows
     what matters cannot. -->

## Core tenets

<!-- The stops. A decision that would violate one of these is not made at all —
     the oracle halts and reports instead of deciding. Keep this list SHORT;
     a long one turns every decision into an escalation and unattended work
     stops entirely, which is the failure this whole arrangement exists to
     prevent. Two or three. -->

## What makes an answer unacceptable

<!-- Failure described from the outside: what the owner would look at and
     reject regardless of how it was built or how well it performs. -->
