# Next steps

Work in flight. Write a task here before starting it; delete it when done.
Keep this short enough to read in one go.

Where it stands: the corpus milestone is built up to the cost projection
(`index`, `fetch`, `select`, `estimate`). Nothing past the checkpoint exists:
extraction, claim store, tiers and report (DESIGN §12, M2-M4) wait for the
calibration batch.

Not on `main` yet, and bigger than anything above: branch
`claude/template-lessons-merge-26dxdn` (~273 commits, summer layout) has
Stage B built and run: extraction, claim store, calibration record, R1006 and
R1007 (alias table at the root). `analysis/board-verdicts` adds two commits on
top: a graded board ranking (`analysis/report.md`, from 2,736 claims). The
owner decides whether to bring that product code onto v2 `main`; if yes, do
it before the backlog below, which it partly answers.

- Build the approved backlog items, one per session. Each maps to a requirement
  in `docs/DESIGN.md` (list at the top of `docs/BACKLOG.md`). Suggested order:
  R1006 (CLI flags, then drop the Python workaround in `scripts/run.sh`),
  R1007 (alias table out of `data/`), R1005, R1002, R1003, R1004, then R1000
  with R28 (clusters, whole-transcript path). The summer plan drafts for the
  last two are in git history (`git show 8a9f6b4:docs/plans/oracle/recut-merged-excerpts.md`
  and `docs/plans/whole-transcript-threshold.md` at the same commit).
- `docs/architecture.md` opening paragraph predates the excerpt/estimate slice;
  correct it with the next change that touches that code.
- Owner: one real run (`./scripts/run.sh`) for S1 and S2; check `./scripts/run.sh aliases`
  first. Then decide on the projected cost and the excerpt window.
