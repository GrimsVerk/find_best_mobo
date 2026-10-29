---
description: Have a fresh subagent attack a plan or design before it is built
---
Spawn one fresh subagent (it must not have helped write the plan). Give it the plan ($ARGUMENTS, or the current plan, or `docs/DESIGN.md`) plus `docs/VISION.md`, and this brief:

> Read-only. Attack this plan; don't fix code or edit files. Find, ranked by how likely each is to slip through unnoticed:
> 1. Goals the plan would not actually deliver if built exactly as written.
> 2. Open decisions whose answer would reshape most of the build (one process or many, local files or a service, and so on).
> 3. Vision lines too vague to settle a real disagreement.
> For each: where (quote it), the gap, the consequence, and the exact replacement sentence. Skip generic advice and style notes. End with a short list of angles you checked that hold up.

Then show the findings to the owner in plain words, fix the plan with them, and record what was settled in `docs/DECISIONS.md`.
