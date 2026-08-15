---
description: Turn a rough idea into a complete design doc at docs/DESIGN.md
---

Read `docs/idea-to-design-doc.md` and act as the elicitation agent it
describes: interrogate the user for what's missing, then write the finished
design doc.

The structure to follow is `docs/DESIGN.md` (the skeleton already in this
repo). Write the completed doc back into `docs/DESIGN.md`, replacing the
skeleton.

**Two documents, not one.** `docs/VISION.md` must be filled in by asking — see
"The vision file" in `docs/idea-to-design-doc.md`. **Offer it at the start, and
accept "after the design" as an answer**: a vision written before the user has
seen the design is a guess about their own priorities, where one written after
is a judgement about a thing they now understand. If they defer, say so in your
report and ask again the moment the design doc is written. The deadline is not
the design — it is the first plan, and that is checked
(`.github/scripts/vision-complete.sh`).

**Write both, push a branch, and STOP THERE. Do not open the pull request.**
`.github/scripts/owner-authored.sh` fails any pull request touching either
document that the owner did not open, so opening one wastes a run and lands
nothing. Report the branch name and tell them to open it themselves — reading
that diff is the point, since these are the two documents everything else is
judged against. It is a different
question from the design: what matters when two reasonable designs disagree, and
what the user would trade away. Do not infer it from their idea, and do not
produce a confident-looking file from guesses — every unattended design decision
must quote a statement from it, so a sentence the user never said is worse than
an empty section. If they decline, write what you honestly can, mark it
provisional, and say plainly in your report that it is unfinished.

The user's raw idea follows (may be empty — if so, ask for it first):

$ARGUMENTS
