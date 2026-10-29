# find-best-mobo

Searching Buildzoid videos on YT to extract his top pick for an AMD mobo.

It lists the Actually Hardcore Overclocking channel, caches the captions,
narrows them to videos that really discuss AM5 boards, and prints what a model
run over them would cost. Then it stops: nothing here calls a model or spends
money. Why and how: `docs/VISION.md`, `docs/DESIGN.md`, `docs/architecture.md`.

Made from [grimsverk-template](https://github.com/GrimsVerk/grimsverk-template).
Agents: start with `AGENTS.md`.

## Run

```sh
./scripts/install.sh               # once: uv and the dependencies
./scripts/run.sh                   # index, fetch, select, estimate; stops at the cost projection
./scripts/run.sh select estimate   # just some stages, e.g. after changing config.toml
```

Every lever is in `config.toml`. The video index and transcript cache live in
`data/`, which stays on this machine and out of git. A second run refetches
nothing it already has.

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
