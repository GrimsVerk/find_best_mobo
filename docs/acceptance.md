# Acceptance — Finding Best Mobo by Buildzoid

Does the built system actually satisfy `docs/DESIGN.md` §13? One row per success
criterion id, filled in during the acceptance pass.

This exists because **"every plan merged" is not "the project works."** Merged
plans tell you each slice passed its own tests. They say nothing about whether
the pieces compose, or whether the thing you set out to build is what got built.
Coverage (`.github/scripts/coverage.sh`) answers the narrower question — is every
requirement *planned* — and even a full pass there only means the work was
scheduled, not that it works.

## How to fill this in

For each criterion, record what was actually observed, not what should follow
from the code. `AGENTS.md` applies in full here: never claim something is
verified in an environment where it could not be observed.

**An `agent` row is a script, not a sentence.** Every criterion §13 does not
mark `(owner)` has one at `acceptance/S<n>.sh` — exit 0 is pass, standard output
is the evidence — and `.github/scripts/acceptance-criteria.sh` runs them as a
required check on **every** pull request, not once here.

That is the whole reason this file changed shape. Its evidence used to be
narration: *"I ran X and it printed Y."* Everywhere else this template separates
computed facts from judged verdicts; this was the one place narration was
admitted as evidence, and it is the last thing the owner reads. The check now
refuses a row marked `pass / agent` with no script behind it — a pass an agent
claims is a pass somebody else can re-run, or it is narration.

Running them per pull request rather than only here is deliberate: a criterion
verified once and trusted thereafter is exactly the "verified once, trusted
forever" shape this template distrusts everywhere else.

**A failing criterion is not a stop.** File it as a `BL-<n>` in
`docs/BACKLOG.md`, record the row as `fail` with the script's real output, and
let the oracle rule — the test may be wrong, the implementation may be wrong, or
the criterion may be met in a way the script does not recognise. In that last
case the oracle records a waiver in `docs/DESIGN.oracle.md` and **the row here
stays `pending / owner`**. The oracle may not mark a criterion passed; that is
the owner's.

The **Verified by** column is the one that matters. Split it honestly:

- `agent` — checked by running `acceptance/S<n>.sh` and reading its real output.
  Cite the script and what it printed.
- `owner` — needs real hardware, real users, real data, or a judgement call. An
  agent **must not** fill these in. Write exactly what the owner should run or
  look at, then leave the status `pending` until they report back.

A criterion nobody can check as written is not a criterion. If you hit one, say
so and fix the wording in `DESIGN.md` §13 rather than quietly marking it passed.

**The `owner` rows were decided in `docs/DESIGN.md` §13, not here.** A criterion
§13 did not mark `(owner)` is verified with real output or recorded as `fail` —
it is not reclassified at acceptance time. If you believe §13 got one wrong, say
so in Outstanding, name the criterion, and leave the row as the design assigned
it.

The reason is an incentive, not a suspicion. Moving a row to `owner` is the
cheapest thing an agent can do at the end of a run — one sentence, and the
driver's stop for it (exit 4, "blocked on the owner") is a documented
*successful* ending. Verifying it means running something that can fail. In the
finished table those two look identical, and the owner reading five `pending /
owner` rows out of eight cannot tell which were always theirs. The templates
warn at length about the opposite abuse — claiming `agent` on thin evidence —
and this is the cheap one.

**Every §13 criterion gets a row here, and every §5 requirement is named by at
least one criterion.** If a requirement reaches this table with no criterion
that would notice its absence, that is the gap worth reporting in Outstanding:
`coverage.sh` will have called it "covered" on the strength of a plan listing
its id, and this table is the only place that claim meets the built system.

| Criterion | Status | Verified by | Evidence |
| --- | --- | --- | --- |
| S1 | pending | owner | Needs a full run against the real channel: `uv run find-best-mobo index` then `uv run find-best-mobo fetch`. Check that every pending video is either cached under `data/transcripts/` or has a row in `data/failures.jsonl` with a class and an error. Cannot be observed here — this environment has no access to the channel. |
| S2 | partial — mechanical half passes, printed projection pending | agent + owner | **Agent:** `uv run pytest tests/test_estimate.py -k "NoInference or stop or invok"` → `10 passed`. Those parse `estimate.py` and `commands/estimate.py` with `ast` and assert no model client, HTTP transport, socket/ssl or credential read; a negative control points the same check at `ytdlp.py` and requires it to find an offender, so the check cannot pass by reading nothing. **Owner:** run the pipeline through `estimate` and confirm the projection prints and the run stops. |
| S3 | pending | owner | Belongs to M2. Requires the calibration batch to have run and real subscription usage to be read, which only the owner can see. |
| S4 | pending | owner | Belongs to M3–M4 — there is no report yet. |
| S5 | pending | owner | Belongs to M3–M4 — there are no tiers yet. |
| S6 | pending | owner | Belongs to M3–M4 — there is no claim store yet. |
| S7 | pending | owner | Belongs to M3–M4 — there is no report generator yet. |
| S8 | pending | owner | The criterion the project exists for. Needs a report, and then a judgement. |
| S9 | pending | agent | `uv run pytest` → `447 passed`, run twice with identical results. The suite is offline by construction: `tests/conftest.py` fails any test that opens a non-loopback socket, and `yt-dlp` is exercised only through faked boundaries (`list_channel_entries`, `fetch_caption_track`). No test carries `@pytest.mark.allow_network`.  **Downgraded from `pass` by this template update:** the new `acceptance-criteria` check counts a pass as narration until a script anyone can re-run exists. `acceptance/S9.sh` lands in the follow-up pull request, and this row returns to `pass` there. |
| S10 | pending | agent | `uv run pytest tests/test_ledger.py -k "trigger or consecutive or rate"` → `16 passed`. All three triggers are covered at their boundaries — at the limit and one below: 3 consecutive fetch errors, cumulative fetch errors past 3% of indexed videos, and missing caption tracks counted separately against their own 5%. A `no_captions` record resets the consecutive counter, and a zero denominator never fires a rate trigger.  **Downgraded from `pass` by this template update:** the new `acceptance-criteria` check counts a pass as narration until a script anyone can re-run exists. `acceptance/S10.sh` lands in the follow-up pull request, and this row returns to `pass` there. |

Row order follows `docs/DESIGN.md` §13's ids numerically, not the order they
appear in that document.

## Outstanding

<!-- Anything failing or pending, and what it needs. This is the honest answer
to "is it done?" — an empty section here, with every criterion passed and
attributed, is the only version of done worth the word. -->

**The project is not done.** Two of eleven criteria pass, one passes in half.
That is the expected state at the end of the MVP milestone, not a shortfall: six
of the pending criteria describe stages the design deliberately leaves
unspecified until the calibration batch has run.

**Pending on the owner, and nothing else can move them:**

- **S1 and the second half of S2** need one real run against the real channel.
  Nothing here can produce that evidence: the test environment has no access to
  YouTube by construction, the same property that makes the suite trustworthy.
  Run, in order:

      uv run find-best-mobo index          # writes data/index.jsonl, prints the counts
      uv run find-best-mobo fetch          # caches captions, writes data/failures.jsonl

  Then, because the CLI cannot yet reach the last three stages (an open plan
  question in `docs/BACKLOG.md`, ruled to stay that way for now), from Python:

      from argparse import Namespace; from pathlib import Path
      from find_best_mobo.config import load_config
      from find_best_mobo.commands import aliases, select, estimate
      c = load_config(Path("config.toml"))
      aliases.run(c, Namespace(check=True)); select.run(c, Namespace()); estimate.run(c, Namespace())

  **Read the `aliases` output before trusting anything downstream.** A canonical
  it reports as never matched is a board the corpus cannot see — the failure
  mode this milestone is least able to detect on its own. For S1, confirm every
  pending video is either cached or in the ledger; for S2, that the projection
  prints (factor included) and the run stops there.

- **S3 through S8** are M2–M4 work. They need extraction, a claim store, tiering
  and a report generator, none of which exist or are planned yet. That is by
  design: the design doc's shape is that nothing past the checkpoint gets
  specified until the calibration batch says what the excerpts actually contain.

**To decide after that run:** whether the projected cost is acceptable, and
whether the excerpt window (2 min before, 5 after) wants narrowing. Both are
configuration; changing either re-runs from cache without refetching.
