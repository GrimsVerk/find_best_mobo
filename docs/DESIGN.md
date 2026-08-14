---
title: Finding Best Mobo by Buildzoid
status: draft            # draft | in-review | approved
created: <YYYY-MM-DD>
related: []              # links to other design docs, issues, prior art
---

# Finding Best Mobo by Buildzoid — Design Doc

<!-- Guidance comments (like this) tell you and the elicitation agent what each
section is for. Delete them in the final doc, or leave them; they don't render. -->

## 1. Summary
<!-- One short paragraph. What is this, in plain language? If you could only keep
one paragraph, this is it. A stranger should grasp the idea from this alone. -->

## 2. Problem & motivation
<!-- What problem does this solve, for whom, and why is it worth doing now?
What's painful or missing today? Keep it about the problem, not the solution. -->

## 3. Goals and non-goals
<!-- Goals: what success looks like, as a short list.
Non-goals: things this explicitly does NOT try to do. Non-goals matter as much as
goals — they're how scope stays honest and the build agent doesn't wander. -->

**Goals**
-

**Non-goals**
-

## 4. Users & core use cases
<!-- Who uses this and what are the handful of key scenarios? Write them as short
"as a <user>, I want to <do X> so that <Y>" or plain narrative. Cover the main
path and the one or two edge cases that actually shape the design. -->

## 5. Requirements
<!-- Functional: what it must DO. Non-functional: the qualities it must have.

Give every requirement a stable id (R1, R2, ...). Plans declare which ids they
implement in their `covers:` field, which is what makes "is the design actually
built?" a question a script can answer instead of a feeling. Never renumber an
existing id — append. -->

**Functional**
- **R1** —

**Non-functional** <!-- fill only those that apply; keep numbering continuous -->
- **R2** — Platform / targets: <!-- web, iOS, CLI, service, library, etc. -->
- Performance / scale:
- Privacy / security / data handling:
- Offline / connectivity:
- Accessibility:
- Cost / resource limits:

## 6. Constraints & assumptions
<!-- Fixed constraints (existing systems, budgets, deadlines, tech you must/can't
use) and assumptions you're making that, if wrong, would change the design. -->

## 7. Proposed approach (high level)
<!-- Language-agnostic. The main components and how they fit together, described in
prose or a simple list of "component -> responsibility". How data flows through.
No code, no premature stack choices unless the choice is itself a requirement. -->

## 8. Key design decisions & alternatives
<!-- The heart of the doc. For each meaningful decision:
- Decision:
- Options considered:
- Choice & rationale (tradeoffs):
This is what turns a wish into a design. Capture the "why", so future-you and the
build agent don't relitigate settled choices or repeat rejected ones. -->

## 9. Data model / key entities
<!-- Optional. The main things the system stores or manipulates and their
relationships. Skip if not applicable. -->

## 10. External dependencies & integrations
<!-- Optional. Third-party services, APIs, libraries, or systems this relies on. -->

## 11. Risks & open questions
<!-- What could go wrong, what's still undecided, what needs research. It's fine —
expected — for a draft to leave things open here rather than inventing answers. -->

## 12. Milestones / phasing
<!-- Break the work into increments, MVP first. For each, a one-line scope and
acceptance criteria (how you know it's done). The MVP should be the smallest thing
that's actually useful and testable.

A milestone here is a coarse phase, not an implementable unit. Breaking one down
into vertical slices — with file paths, signatures, and estimates — happens in a
plan (`docs/plans/<slug>.md`), one milestone at a time, when you're ready to
build it. Don't do that work here. -->

**MVP**
- Scope:
- Acceptance criteria:

**Later**
-

## 13. Success criteria
<!-- How you'll know the whole thing worked. Concrete and checkable where possible,
not "users are happy". Tie back to the goals in section 3.

Give each one a stable id (S1, S2, ...). These are what the acceptance pass
checks at the end, one row per id in `docs/acceptance.md`, with evidence. Write
them so that evidence is possible: "startup under 2s on the target device" can be
shown, "feels fast" cannot. Mark the ones only you can verify — anything needing
real hardware, real users, or a judgement call — because an agent must not claim
to have checked those. -->

- **S1** —
