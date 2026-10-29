# Next steps

Work in flight. Write a task here before starting it; delete it when done.
Keep this short enough to read in one go.

Where it stands: Stage A (index, fetch, select, estimate) and Stage B
(extract, ingest, claim store, calibration record) are built, and R1000 to
R1013 with them (R1001 superseded). The first full extraction produced 2,736
claims; `calibration/batch-1.json` measured 2.33 chars per token against the
4.0 guess. `analysis/report.md` is a one-off board ranking built from those
claims outside the pipeline. Stages C to E (synthesis, tiers, report: DESIGN
§7, M3, M4) are not built; each spending stage needs the owner's approval.

- Owner: decide whether Stage C/E should replace `analysis/` (its ranking and
  board resolution were done by hand-run workers, not by the pipeline), and
  approve the next stage.
- `analysis/board-map.jsonl` is keyed by claim line number in
  `data/claims.jsonl` as it was before `scripts/drop-gpu-claims.py`; rerunning
  `analysis/aggregate.py` on the cleaned store needs `claims.jsonl.bak` or a
  re-keying. Nothing in the repo reruns it, and no checkout but the owner's
  has `data/`.
- Open backlog: BL-1 (stale failure ledger), BL-3 (`FetchFailure` re-export).
- Bundles are still packed at the configured 4.0 factor, not the measured one
  (`docs/architecture.md`, Known rough edges); decide before the next
  extraction run.
