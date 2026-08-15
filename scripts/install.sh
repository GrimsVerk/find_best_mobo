#!/usr/bin/env bash
#
# install.sh — make sure this machine can run the pipeline. Run once.
#
# Idempotent by design: every step checks before it acts and says which it did.
# Re-running is safe and cheap, and nothing is reinstalled that is already here.
#
#   ./scripts/install.sh
#
# Then: ./scripts/run.sh

set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Checking uv"
if command -v uv >/dev/null 2>&1; then
  echo "    uv $(uv --version | awk '{print $2}') is installed. Checking for updates."
  # `uv self update` is both halves of the check in one call: it asks whether a
  # newer uv exists and installs it only if so. It can fail for reasons that say
  # nothing about this machine's health — a uv owned by a package manager (brew,
  # pipx, apt) refuses to replace itself, and the check itself is a GitHub API
  # call that can be rate-limited. An existing, working uv is enough to run the
  # pipeline, so the update is reported and stepped over rather than made fatal.
  if uv self update 2>&1 | sed 's/^/    /'; then
    :
  else
    echo "    The update check did not succeed (see above). This is not fatal:"
    echo "    the uv you already have runs the pipeline. If uv came from a"
    echo "    package manager (brew, pipx, apt), update it that way instead."
  fi
else
  echo "    uv not found. Installing from astral.sh (the official installer)."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # The installer puts uv in ~/.local/bin, which is not on PATH in this shell
  # yet — sourcing its env file is what makes the rest of this script work
  # without asking you to open a new terminal.
  # shellcheck disable=SC1091
  [ -f "$HOME/.local/bin/env" ] && . "$HOME/.local/bin/env"
  command -v uv >/dev/null 2>&1 || {
    echo "    uv installed but not on PATH. Open a new terminal and re-run this." >&2
    exit 1
  }
fi

# uv sync is itself idempotent: it reads uv.lock and only changes what differs,
# so this is a no-op on an up-to-date checkout. --locked refuses to silently
# resolve something different from what CI tested.
echo "==> Installing Python dependencies (uv sync --locked)"
uv sync --locked

echo "==> Verifying the package imports"
uv run python -c "import find_best_mobo; print('    find_best_mobo imports cleanly')"

# Optional and non-fatal: the git-level checks. Only relevant if you commit from
# this machine, so a failure here is reported and ignored rather than fatal.
echo "==> Git hooks (optional)"
if [ -f .git/hooks/pre-commit ]; then
  echo "    pre-commit hooks already installed — skipping."
elif uv run pre-commit install >/dev/null 2>&1; then
  echo "    pre-commit hooks installed."
else
  echo "    could not install pre-commit hooks; not required to run the pipeline."
fi

cat <<'DONE'

Done. Nothing else to install.

Next:  ./scripts/run.sh          the whole pipeline, stopping at the cost projection
       ./scripts/run.sh --help   the stages, and how to run just some of them
DONE
