# Backlog — Finding Best Mobo by Buildzoid

Ideas and found problems not yet built. Ids are never reused (the last one
used is BL-29). Forget an item by deleting it; git history is the archive.

The owner approved BL-1 to BL-13 on 2026-08-19 and BL-15, BL-23 and BL-28
later (`docs/DECISIONS.md`). Everything a requirement answered is now built
and was deleted from here: R1000 and R1002 to R1013 (BL-4 to BL-11, BL-13,
BL-15, BL-27, BL-28), and Stage B itself (BL-23). The questions filed for
rulings (BL-14, BL-16 to BL-19, BL-24 to BL-26) are answered in
`docs/DESIGN.md` §14 and `docs/DECISIONS.md`. Items about the summer delivery
pipeline (BL-12, BL-20 to BL-22, BL-29) went with it.

## Still open

- **BL-1** — **A clean rerun leaves a stale failure ledger.**
  `data/failures.jsonl` is rewritten when a failure is recorded, so a run with
  no failures never rewrites it and the previous run's file survives, reading
  as current. Options: rewrite unconditionally at end of run (preferred),
  delete on a clean run, or keep it and rename the concept to "the last run
  that had failures".
- **BL-3** — **`FetchFailure` is re-exported from `transcripts.py`.** It lives
  in `ledger.py` (placing it in `transcripts.py` was circular); retire the
  re-export shim and import it from `ledger.py` everywhere.
