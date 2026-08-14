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
