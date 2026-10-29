#!/usr/bin/env bash
# Create this project's GitHub repo (if there is no origin), push, and set it up:
# delete merged branches, block force-pushes and deletion of main.
#
#   scripts/setup-github.sh [--public]     # default: private
#
# Still manual for public repos: Settings > General > Pull requests >
# "Collaborators only", so outsiders can't open PRs.
set -euo pipefail

VISIBILITY=--private
case "${1:-}" in
  --public) VISIBILITY=--public ;;
  "") ;;
  *) echo "usage: $0 [--public]" >&2; exit 2 ;;
esac

cd "$(git rev-parse --show-toplevel)"
command -v gh >/dev/null || { echo "setup-github: install the GitHub CLI (gh) first" >&2; exit 1; }

if ! git remote get-url origin >/dev/null 2>&1; then
  gh repo create "$(basename "$PWD")" "$VISIBILITY" --source=. --push
fi
REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"

gh api -X PATCH "repos/$REPO" -F delete_branch_on_merge=true >/dev/null
echo "setup-github: $REPO deletes branches after merge."

# One ruleset on the default branch. Update it in place if it exists.
ID="$(gh api "repos/$REPO/rulesets" --jq '.[] | select(.name == "protect-main") | .id')"
BODY='{"name":"protect-main","target":"branch","enforcement":"active",
  "conditions":{"ref_name":{"include":["~DEFAULT_BRANCH"],"exclude":[]}},
  "rules":[{"type":"deletion"},{"type":"non_fast_forward"}]}'
if [[ -n "$ID" ]]; then
  gh api -X PUT "repos/$REPO/rulesets/$ID" --input - <<<"$BODY" >/dev/null
else
  gh api -X POST "repos/$REPO/rulesets" --input - <<<"$BODY" >/dev/null
fi
echo "setup-github: main is protected from force-pushes and deletion."
