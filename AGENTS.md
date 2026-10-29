# find-best-mobo: rules for agents

Searching Buildzoid videos on YT to extract his top pick for an AMD mobo.

## Every session

- Read `next-steps.md` first. Write your task there before you start; delete it when done. Nothing may live only in chat: the next session starts fresh with only these files.
- One feature per session.
- When unsure, pick a reasonable default, note the assumption (in `docs/DECISIONS.md` if it will matter later), and keep going.
- Read the owner's whole message before acting; the last word on a point wins. If an instruction contradicts something already settled, say so before doing the work.

## Files

- `docs/VISION.md`: what matters, the tiebreaker. `docs/DESIGN.md`: what we are building (requirements `R<n>`, success criteria `S<n>`).
- `docs/DECISIONS.md`: settled decisions and why. Don't relitigate them.
- `docs/BACKLOG.md`: ideas not started. Forget by deleting; git history is the archive.
- `docs/architecture.md`: what exists now and how it flows. Update it when behaviour changes.
- `config.toml`: every pipeline lever. `data/` is the local, gitignored corpus cache (index, transcripts, failure ledger); it never enters git.

## Working

- Non-trivial work: plan it in plan mode first. `/adversarial-review` attacks a plan before you build it (optional).
- A feature too big for one context: `/orchestrate`.
- Work on a branch, never on `main`. Run the checks below locally, then open a PR and merge it (`gh pr merge --squash --delete-branch`). CI runs only on `main`; a red `main` is the next task.
- Never force-push, rewrite pushed history, or skip hooks (`--no-verify`).
- Paths in repo files are relative, so any computer can resume the work. Machine-specific values go in one gitignored local file with a committed `.example`.
- Python never calls a model and nothing in the pipeline spends subscription usage: it stops at the `estimate` projection (R7). Agents never scrape YouTube; `yt-dlp` stays behind `src/find_best_mobo/ytdlp.py`.
- No new dependency without the owner's approval, recorded in `docs/DECISIONS.md` (what it is for, why the stdlib won't do, its license).

## Checks

```sh
uv sync && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
```

## Tests

- Test behaviour, not implementation. Keep tests that protect what matters: core user flows, anything that can lose data, payments.
- Tests run offline and deterministically: no real network, clock or randomness. `tests/conftest.py` fails any test that opens a real socket; fake `yt-dlp` at its boundary.
- For logic with a clear interface, the `test-writer` subagent can write tests from the spec while you write the code.

## Processes and agents

- Never stop processes or agents by name pattern (`pkill -f`, `killall`): other agents run identical commands. Stop only what you started, by its own ID.
- Before a big fan-out of subagents, check remaining usage; hitting the limit mid-run kills them all.

## Licensing

MIT (`LICENSE`, and `license` in `pyproject.toml`), chosen by the owner on 2026-10-29. Don't change the license or add another.
