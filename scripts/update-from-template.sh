#!/usr/bin/env bash
# Pull in the latest template on a branch and open a PR for it.
#
#   scripts/update-from-template.sh [--ref <tag-or-branch>]
set -euo pipefail

REF=()
case "${1:-}" in
  --ref) REF=(--vcs-ref "${2:?--ref needs a value}") ;;
  "") ;;
  *) echo "usage: $0 [--ref <tag-or-branch>]" >&2; exit 2 ;;
esac

cd "$(git rev-parse --show-toplevel)"
command -v copier >/dev/null || { echo "update-from-template: run 'uv tool install copier' first" >&2; exit 1; }
[[ -z "$(git status --porcelain)" ]] || { echo "update-from-template: commit or stash your changes first" >&2; exit 1; }

git switch main
git pull --ff-only || true
copier update --defaults ${REF[@]+"${REF[@]}"}

if [[ -z "$(git status --porcelain)" ]]; then
  echo "update-from-template: already up to date."
  exit 0
fi
VERSION="$(awk '/^_commit:/ {print $2}' .copier-answers.yml)"
if git grep -qE '^(<<<<<<<|>>>>>>>) '; then
  echo "update-from-template: conflicts. Resolve the <<<<<<< markers, then commit on a branch." >&2
  exit 1
fi
git switch -c "template/$VERSION"
git add -A
git commit -m "Update from template $VERSION"
git push -u origin HEAD
gh pr create --fill
