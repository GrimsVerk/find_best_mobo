---
description: Build one feature with parallel worker subagents
---
Build this one feature: $ARGUMENTS (more than one named? Build the first; the rest get their own sessions.)
1. Split it into at most 6 vertical slices, each usable end to end on its own (never "all storage, then all UI"). Note them in `next-steps.md`.
2. Give each slice to one worker subagent, in its own worktree, with the files it may touch. Workers spawn nothing: no subagents, no background agents.
3. Optional: give a slice's interface to the `test-writer` subagent at the same time, so tests come from the spec, not the code.
4. Assemble the slices yourself, run the checks in `AGENTS.md`, then open and merge one PR for the feature.
