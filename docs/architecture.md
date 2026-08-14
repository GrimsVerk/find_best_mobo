# Finding Best Mobo by Buildzoid — Architecture

<!-- The living description of what exists RIGHT NOW. Updated at the end of every
slice (AGENTS.md, "Architecture doc"), so it describes the system as built, never
as planned. `docs/DESIGN.md` is the intent and doesn't change; this changes.

Keep it at the level of LOGIC, NOT CODE. Components and what each is responsible
for, what data moves between them, what happens on the main paths. No signatures,
no line-by-line description, nothing that a rename would invalidate — if a
refactor that changes no behaviour would force an edit here, it's too low-level.

It has two readers and they keep each other honest: the owner, who does not read
the code and needs somewhere to understand the system; and the next agent, which
starts with no context beyond this repository and reads this first to get its
bearings. Written for the human, it stays truthful; written at all, it saves the
agent from rediscovering the system by grepping.

Delete these comments or leave them; they don't render. -->

## Components

<!-- One entry per component: its name, and the single thing it is responsible
for. If a component needs "and" to describe its responsibility, say so plainly —
that's worth seeing. -->

| Component | Responsible for |
| --- | --- |
| _name_ | _the single thing it is responsible for_ |

## Data flow

<!-- What moves between the components, in what direction, and in what form.
Prose or a simple list is fine — `A --(what)--> B`. A diagram is welcome but
never required; an accurate list beats a stale picture. -->

## Main paths

<!-- Walk the two or three journeys that matter, start to finish, in plain
language: what triggers it, which components it touches in order, what the
observable result is. These are what someone reads to understand how the system
actually behaves, and they are the first thing to go stale — check them at the
end of each slice. -->

### <path name>

1.

## State and storage

<!-- Optional. What persists, where it lives, and what owns it. Skip if the
system holds nothing. -->

## Known rough edges

<!-- Optional but valuable. Things that work but are awkward, deliberate
shortcuts, and where the next change in this area is likely to hurt. This is the
section that stops a future agent confidently "fixing" something load-bearing,
and it's where the reviewer's "easy to change next time" findings should land
when they're accepted rather than acted on. -->

-
