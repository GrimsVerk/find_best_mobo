---
description: Turn an approved design milestone into a sliced plan under docs/plans/
---

Write a plan for one milestone of `docs/DESIGN.md`.

The behaviour is defined in the canonical files, not here — read them first:

- `docs/idea-to-design-doc.md`, section **"After the design doc: the plan"**
- `docs/plans/_TEMPLATE.md` — the schema, with guidance comments on every field
- `AGENTS.md`, the **Planning** rule

Then copy the template to `docs/plans/<slug>.md` and fill it in. Three things
that are easy to skip and are the whole point:

1. **Run the uncertainty gate before writing any slices.** List what you had to
   guess at, stop, and wait for a ruling. Record the rulings in the plan.

   If the list is genuinely **empty** — every decision derived from
   `docs/DESIGN.md`, nothing guessed — say so in that section and continue
   without stopping. Do not manufacture a question to have something to ask.
   Equally, do not empty the list to avoid waiting: the owner reviews the plan
   before it merges, and a plan that claims certainty it did not have is the one
   failure this gate exists to catch.
2. **Slice vertically** — each slice delivers something observable end-to-end.
3. **Land the plan on its own pull request, before any code exists.** Commit it
   on a `docs/`-prefixed branch — exempt from the plan check, which is what the
   exemption is for — and let it merge. `CODEOWNERS` puts `docs/plans/` behind
   the owner's review, so merging it *is* the ruling.

   Only then does `/orchestrate` branch off the default branch to build it. This
   ordering is enforced: CI's `plan` check fails a pull request whose plan does
   not already exist at the base commit, because a plan written alongside the
   code it authorises specifies nothing — the estimates, the file list, and the
   slice boundaries end up as whatever the change turned out to need.

Report the plan's path and slug, and stop there. Writing the plan and building
it are two separate pieces of work, in that order.

The milestone to plan (may be empty — if so, ask which one):

$ARGUMENTS
