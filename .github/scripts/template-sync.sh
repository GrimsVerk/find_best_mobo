#!/usr/bin/env bash
#
# template-sync.sh — prove a `template/` pull request contains exactly what
# `copier update` produces, and nothing else.
#
# WHY THIS EXISTS.
#
# A template update is a third kind of change, and the other gates only know
# about two. A planned feature has a specification written before it, which the
# `plan` check enforces. A trivial chore is small enough not to need one, which
# the size-capped `chore/` exemption covers. A template update is neither: it is
# externally authored and was already reviewed — in the template repository, at
# the merge that produced the version being pulled in. Its specification exists;
# it just does not live in this repo, so no plan can ever resolve for it.
#
# Rather than widen the planning exemption on trust — which is the hole the size
# cap was added to close — this replaces the plan with a STRONGER guarantee. A
# plan says "someone intended this". This says "this diff is byte-for-byte what
# the template produces, and contains nothing else". That is the only property
# actually worth checking here: that no hand-written change rode along with the
# sync.
#
# HOW.
#
# Check out the PR's base commit into a scratch worktree, run `copier update`
# there against the version the PR targets, and compare the resulting git tree
# object with the PR head's tree. Identical tree hashes mean identical content,
# exactly and without ambiguity.
#
# Required env:
#   BASE_SHA, HEAD_SHA   the commits bounding the pull request
#   HEAD_REF             the PR head branch name (decides whether this applies)
# Optional env:
#   SYNC_PREFIX          branch prefix this check governs (default: template/)
#   TEMPLATE_TOKEN       token with read access to the template repository,
#                        required when the template repo is private
#
# Exits 0 for any branch outside SYNC_PREFIX — those are the plan check's job.

set -euo pipefail

SYNC_PREFIX="${SYNC_PREFIX:-template/}"
ROOT="$(git rev-parse --show-toplevel)"
: "${HEAD_REF:?HEAD_REF is required (the PR head branch name)}"
: "${BASE_SHA:?BASE_SHA is required (the PR base commit)}"
: "${HEAD_SHA:?HEAD_SHA is required (the PR head commit)}"

die() { echo "template-sync: $*" >&2; exit 1; }

if [[ "$HEAD_REF" != "$SYNC_PREFIX"* ]]; then
  echo "template-sync: '$HEAD_REF' is not a ${SYNC_PREFIX} branch — not a template"
  echo "template-sync: sync, so the plan check governs it instead. Nothing to do."
  exit 0
fi

command -v copier >/dev/null 2>&1 || die "copier is not on PATH."

ANSWERS="${ANSWERS_FILE:-.copier-answers.yml}"
git -C "$ROOT" cat-file -e "${HEAD_SHA}:${ANSWERS}" 2>/dev/null \
  || die "no ${ANSWERS} at the head commit.

A ${SYNC_PREFIX} branch is for pulling in template changes, and that is driven
entirely by the answers file. Without one there is nothing to verify, and
nothing this branch could legitimately be doing."

# The version the pull request claims to be updating to. Read from the HEAD
# answers file because that is what the author targeted; the check is whether
# reproducing that update from the base yields precisely this diff.
TARGET_REF="$(git -C "$ROOT" show "${HEAD_SHA}:${ANSWERS}" \
  | awk '/^_commit:/ { print $2; exit }' | tr -d '"'"'"'')"
[[ -n "$TARGET_REF" ]] || die "could not read _commit from ${ANSWERS} at HEAD."

BASE_REF="$(git -C "$ROOT" show "${BASE_SHA}:${ANSWERS}" 2>/dev/null \
  | awk '/^_commit:/ { print $2; exit }' | tr -d '"'"'"'')"

echo "template-sync: base is at template ${BASE_REF:-<unknown>}, PR targets ${TARGET_REF}"

if [[ "$TARGET_REF" == "$BASE_REF" ]]; then
  die "the answers file still records template version '$TARGET_REF'.

This branch changes no template version, so it is not a template sync. Either
run \`copier update\` so the answers file advances, or move this work to a
branch whose prefix matches what it actually is."
fi

WORKTREE="$(mktemp -d)"
cleanup() { git -C "$ROOT" worktree remove --force "$WORKTREE" 2>/dev/null || true; }
trap cleanup EXIT

# A detached worktree at the base commit: a clean tree, which copier requires,
# and one that cannot disturb the checkout CI is running in.
git -C "$ROOT" worktree add --detach --quiet "$WORKTREE" "$BASE_SHA" \
  || die "could not create a worktree at $BASE_SHA"

echo "template-sync: replaying \`copier update --vcs-ref=$TARGET_REF\` from the base commit"

# --defaults so a template that added a question takes its default rather than
# hanging on a prompt; --trust because the template may carry tasks. Both match
# what a person running this locally would need.
if ! ( cd "$WORKTREE" && copier update --defaults --trust --vcs-ref="$TARGET_REF" ) 2>&1; then
  die "\`copier update\` failed when replayed from the base commit.

If the template repository is private, CI needs a token that can read it —
see TEMPLATE_TOKEN in .github/workflows/ci.yml. Otherwise the target version
'$TARGET_REF' may not exist, or the update may not apply cleanly on top of
this project's base commit."
fi

# Compare content, not diffs: `git write-tree` hashes the whole tree, so equal
# hashes mean every tracked path matches exactly. Anything the author added,
# removed, or edited by hand alongside the sync changes this hash.
git -C "$WORKTREE" add -A
REPLAYED_TREE="$(git -C "$WORKTREE" write-tree)"
HEAD_TREE="$(git -C "$ROOT" rev-parse "${HEAD_SHA}^{tree}")"

if [[ "$REPLAYED_TREE" == "$HEAD_TREE" ]]; then
  echo "template-sync: PASS — the diff is exactly \`copier update\` to ${TARGET_REF}."
  echo "template-sync: nothing hand-written rode along with it."
  exit 0
fi

echo "template-sync: FAIL — this pull request is not a pure template sync." >&2
echo >&2
echo "Replaying the update from the base commit produced a different tree." >&2
echo "Files that differ between the replay and this pull request:" >&2
echo >&2
git -C "$ROOT" diff --stat "$REPLAYED_TREE" "$HEAD_TREE" >&2 || true
cat >&2 <<EOF

Each path above is somewhere the pull request disagrees with what the template
actually produces — a hand edit alongside the sync, a conflict resolved by hand,
or an unrelated commit on the same branch.

A ${SYNC_PREFIX} branch skips the plan check, and this is what earns that: it may
carry the template's output and nothing else. Fix by rebuilding it cleanly:

    git switch main && git pull
    git switch -c ${SYNC_PREFIX}<version>
    copier update --defaults --trust
    git commit -am "Update from template <version>"

If a hand change is genuinely needed on top, it belongs in its own pull request,
with a plan, after this one merges.
EOF
exit 1
