# find-best-mobo

Searching Buildzoid videos on YT to extract his top pick for an AMD mobo.

It lists the Actually Hardcore Overclocking channel, caches the captions,
narrows them to videos that really discuss AM5 boards, prints what a model run
over them would cost, and then, only when you run `extract`, has a model read
them into sourced claims (board, what was said, timestamped snippet). Why and
how: `docs/VISION.md`, `docs/DESIGN.md`, `docs/architecture.md`.

The current answer is `analysis/report.md`: a safety-weighted board ranking
from the first full extraction (2,736 claims), every claim linked to its
video and timestamp.

Made from [grimsverk-template](https://github.com/GrimsVerk/grimsverk-template).
Agents: start with `AGENTS.md`.

## Run

```sh
./scripts/install.sh                   # once: uv and the dependencies
./scripts/run.sh select estimate       # cost projection only; spends nothing
./scripts/run.sh                       # index, fetch, select, estimate, extract (one batch)
./scripts/run.sh extract --batches all # every pending batch
./scripts/run.sh aliases               # how much of the corpus the alias table matches
```

**`extract` spends subscription usage** (`claude -p`, Opus 5 at low effort).
Everything before it spends nothing. It does one batch unless told otherwise,
then stops and reports, and it stops early rather than spend more than 10
points of your weekly limit (read with `omarchy-agent-usage-claude`). Each batch's measured cost is
written to `calibration/batch-<n>.json`, which you commit.

Every lever is in `config.toml`; the alias table is `aliases.toml` and the
extraction prompt `prompts/extract-claims.md`. The video index, transcripts,
bundles and claim store (`data/claims.jsonl`, explained in
`docs/reading-the-claims.md`) live in `data/`, which stays on this machine
and out of git. A second run refetches nothing and re-extracts no batch it
already has.

## Develop

```sh
uv sync                     # install (creates .venv)
uv run pytest               # tests (offline)
uv run pre-commit install   # checks on every commit
```

## Template updates

`scripts/update-from-template.sh` pulls in the latest template on a branch and opens a PR.

## License

MIT, see `LICENSE`.
