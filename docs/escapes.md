# Escapes — Finding Best Mobo by Buildzoid

Append-only log of everything that reached the owner instead of being caught by
a gate. One line per escape, newest at the bottom. Never rewrite an entry; if
something turns out to be wrong, append a correction.

The rule that fills this file is the **ratchet** in `AGENTS.md`: nothing that
escapes gets fixed without also adding a permanent check that would have caught
it. "Why did this bug exist" and "which gate should have caught this" are the
same question, and this is where the second answer lives.

This is a log, not a dashboard, and that is deliberate — with one project there
is nothing to aggregate yet. Its job is to accumulate evidence about which gate
is missing, so the next check added is one the evidence asked for rather than one
someone guessed at. If the same gate column keeps appearing, that is the signal.

| Date | What escaped | Which gate should have caught it | Check added |
| --- | --- | --- | --- |
| _YYYY-MM-DD_ | _what went wrong, one clause_ | _CI / review / plan / test-the-tests / none existed_ | _what now exists so it can't recur_ |

<!-- Append below, newest at the bottom. Never rewrite an entry; if one turns
out to be wrong, append a correction. -->

| 2026-08-14 | `secrets` job crashed with a 403 on every pull request — the default token cannot list PR commits, so gitleaks never scanned | CI (the gate was present but could not run on the event it matters for) | `secrets` now declares `pull-requests: read`, so the job scans instead of aborting |
| 2026-08-14 | `template-sync` could not run at all — `_src_path` named an SSH host alias that exists only on the owner's machine, so CI could not reach the template | CI (the gate was present but unrunnable, so a `template/` branch's exemption was unbacked) | `_src_path` is now an `https://` URL the runner can resolve and `TEMPLATE_TOKEN` can authenticate |
| 2026-08-14 | the completed design doc had no path through the `plan` check — the `docs/` exemption caps at 50 added lines and the doc adds ~600, while no plan can cover the very document that plans are written against | plan (none existed: the gate handles planned code and template syncs, and the design doc is neither) | none yet — the fix is a gate change and gate paths are owner-owned; candidate is an uncapped prefix for the design doc in `plan-resolve.sh`, earned by the review gate the way `template/` is earned by `template-sync` |
| 2026-08-14 | requirement ids `R2a`/`S1a` in the design doc did not match what `coverage.sh` parses, so they would have counted as neither covered nor missing — caught by hand before #12 opened, not by a gate | CI (the coverage gate ignores an id it does not recognise instead of failing on it, so it fails open on a malformed id) | none yet — `coverage.sh` is a gate path and owner-owned; candidate is to fail on any `**R…**` or `**S…**` in the design doc that does not match the id pattern, rather than skipping it |
| 2026-08-14 | the same `plan` gate gap recurred for plans themselves — the plan template is 124 lines empty, so any filled plan blows the 50-line `docs/` cap, and a plan branch cannot resolve to a plan that does not yet exist on main | plan (none existed: third instance of the same gap, after the design doc — the gate has no path for the documents it demands) | none yet — owner ruled to bypass again deliberately, treating this project as data collection on where the process binds; the standing fix is an uncapped exemption for branches whose only additions are under `docs/plans/`, which is a gate path and owner-owned |
