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
   guess at rather than derive, and classify each by one contract test: it is
   **HIGH-risk** if the candidate answers change slice boundaries, a Signatures
   block, an external format or schema, or anything expensive to reverse — and
   being unsure which side it is on itself makes it HIGH. Then who rules
   depends on who is awake:

   - **Attended** (the owner invoked you): stop and wait for the owner's
     ruling on everything listed, exactly as before. Record the rulings in the
     plan.
   - **Unattended** (the prompt says UNATTENDED — the delivery driver invoked
     you): never answer a HIGH uncertainty yourself. File each one as the next
     `BL-<n>` under **"Uncertainties awaiting oracle ruling"** in
     `docs/BACKLOG.md` — the question, your proposed default, the risk class,
     one line on why — commit that alone on a `docs/`-prefixed branch, and
     stop, reporting "plan pending oracle rulings". The driver runs the oracle
     and re-invokes you; then record each ruling in the plan by its `OD-<n>`
     id and continue. A **LOW** uncertainty proceeds immediately on your
     recorded default — still filed as a `BL-<n>` so the oracle reviews it
     next cycle. Guessing is allowed; guessing silently is not
     (`docs/DECISIONS.md`, the mid-run authority ruling).

   **Classify before you list: a choice the design layer explicitly hands to
   the plan is a derivation, not an uncertainty.** If a requirement or decision
   answers the question — even by delegating it to the plan — make the choice,
   cite the id that delegates it, and record it as a derivation in the plan's
   reasoning. Only a genuine gap in the design layer is an uncertainty, and
   only those are filed. Writing "risk: HIGH — proceeded on the default" is
   self-ruling, and the review gate blocks it.

   If the list is genuinely **empty** — every decision derived from
   `docs/DESIGN.md`, nothing guessed — say so in that section and continue
   without stopping. Do not manufacture a question to have something to ask.
   Equally, do not empty the list to avoid waiting: a plan that claims
   certainty it did not have is the one failure this gate exists to catch.
2. **Slice vertically** — each slice delivers something observable end-to-end.
3. **Land the plan on its own pull request, before any code exists.** Commit it
   on a `docs/`-prefixed branch — exempt from the plan check, which is what the
   exemption is for — and let it merge. Where it lives depends on the mode:

   - **Attended:** `docs/plans/<slug>.md`. `CODEOWNERS` puts `docs/plans/`
     behind the owner's review, so merging it *is* the ruling.
   - **Unattended:** `docs/plans/oracle/<slug>.md` — the deliberately un-owned
     path, so the pull request merges on green checks with nobody awake. What
     replaces the owner's review there is mechanical:
     `.github/scripts/oracle-decisions.sh` fails any plan on that path unless
     it cites a landed `OD-<n>` or its `covers:` are requirement ids that
     already exist in a design document — so an unattended plan can implement
     landed requirements but can never propose work. The slug must be unique
     across every plan in the tree, including `docs/plans/` proper.

   Only then does `/orchestrate` branch off the default branch to build it. This
   ordering is enforced: CI's `plan` check fails a pull request whose plan does
   not already exist at the base commit, because a plan written alongside the
   code it authorises specifies nothing — the estimates, the file list, and the
   slice boundaries end up as whatever the change turned out to need.

Report the plan's path and slug, and stop there. Writing the plan and building
it are two separate pieces of work, in that order.

The milestone to plan (may be empty — if so, ask which one):

$ARGUMENTS
