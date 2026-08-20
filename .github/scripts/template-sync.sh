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
#   TEMPLATE_TOKEN       read token for the template repository — in CI this
#                        is minted per run from the GitHub App, down-scoped to
#                        Contents: read on the template repo alone (no PAT;
#                        PATs expire and fail every project at once) —
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

# WHICH template. `_commit` says which VERSION to replay; `_src_path` says which
# REPOSITORY to replay it from, and until this comparison existed the pull
# request chose that freely. The replay then runs `copier update --trust`, which
# executes the template's own `_migrations`, inside a job whose git config has
# just been given a credential rewrite carrying TEMPLATE_TOKEN. Meanwhile
# plan-resolve.sh steps aside by prefix, test-the-tests.sh skips by prefix, and
# the review gate is told by the TEMPLATE SYNC note that provenance is
# mechanically settled — four mechanisms deferring to one comparison that was
# not being made. Both fields are the template's identity; both are pinned.
BASE_SRC="$(git -C "$ROOT" show "${BASE_SHA}:${ANSWERS}" 2>/dev/null \
  | sed -n 's/^_src_path:[[:space:]]*//p' | tr -d "\"'" | head -1)"
HEAD_SRC="$(git -C "$ROOT" show "${HEAD_SHA}:${ANSWERS}" \
  | sed -n 's/^_src_path:[[:space:]]*//p' | tr -d "\"'" | head -1)"
if [[ -n "$BASE_SRC" && "$HEAD_SRC" != "$BASE_SRC" ]]; then
  die "this branch changes which TEMPLATE the project is generated from.

  base: ${BASE_SRC}
  head: ${HEAD_SRC:-<missing>}

A template sync replays \`copier update\` from the recorded template and proves
the diff is exactly its output. That proof says nothing about WHICH template
produced it, so a changed _src_path would have this check verify the tree
against a repository chosen by this pull request — and run that repository's
migrations, with credentials, before any reviewer sees the diff.

Moving a project to a different template is a real thing to want and it is not
this. Do it deliberately, on a branch that is not exempt from planning and
review, so a human reads the source change as the change it is."
fi

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
  SRC="$(git -C "$ROOT" show "${HEAD_SHA}:${ANSWERS}" \
    | sed -n 's/^_src_path: *//p' | tr -d "\"'" | head -1)"
  # Order matters: name the cause that is NOT a credentials problem first.
  # "Could not resolve hostname" from an ssh:// alias reads exactly like an auth
  # failure, and an earlier version of this message sent people to check a token
  # that was perfectly fine.
  case "$SRC" in
    *ssh://git@*|git@*)
      die "\`copier update\` failed when replayed from the base commit.

_src_path in ${ANSWERS} is:

    $SRC

That is an SSH URL. If it names a host alias from a personal ~/.ssh/config, no
CI runner can resolve it — the failure above will say \"Could not resolve
hostname\", which looks like a credentials problem and is not one. The workflow
rewrites the alias through the read token it mints from the GitHub App, so this
should have been handled; if you are seeing it anyway, check that the App is
installed on the TEMPLATE repository (its id is the APP_ID secret), then change
_src_path to https://github.com/<owner>/<repo>.git, which is what CI can fetch
without any rewriting at all." ;;
    *)
      die "\`copier update\` failed when replayed from the base commit.

_src_path is '$SRC'. If the template repository is private, CI reads it with a
token minted from the GitHub App (APP_ID / APP_PRIVATE_KEY secrets) — the App
must be INSTALLED on the template repository, not only on this one: App
settings -> Install App -> add the template repo. There is deliberately no PAT
path. Otherwise the target version '$TARGET_REF' may not exist, or the update
may not apply cleanly on top of this project's base commit." ;;
  esac
fi

# Compare content, not diffs: `git write-tree` hashes the whole tree, so equal
# hashes mean every tracked path matches exactly. Anything the author added,
# removed, or edited by hand alongside the sync changes this hash.
#
# ONE path is dropped from both sides first: `.pr-request.json`, the opener's
# request marker (ESC-63). A driver that cannot author pull requests as the
# App commits it as the branch's last commit — it is pull-request machinery
# riding with the update, not a hand edit to the update, and it can never be
# copier output. Removing it from both trees keeps the comparison exact for
# every other byte.
git -C "$WORKTREE" add -A
git -C "$WORKTREE" rm -q --cached --ignore-unmatch .pr-request.json
REPLAYED_TREE="$(git -C "$WORKTREE" write-tree)"
HEAD_INDEX="$(mktemp)"
GIT_INDEX_FILE="$HEAD_INDEX" git -C "$ROOT" read-tree "${HEAD_SHA}^{tree}"
GIT_INDEX_FILE="$HEAD_INDEX" git -C "$ROOT" rm -q --cached --ignore-unmatch .pr-request.json
HEAD_TREE="$(GIT_INDEX_FILE="$HEAD_INDEX" git -C "$ROOT" write-tree)"
rm -f "$HEAD_INDEX"

if [[ "$REPLAYED_TREE" == "$HEAD_TREE" ]]; then
  echo "template-sync: PASS — the diff is exactly \`copier update\` to ${TARGET_REF}."
  echo "template-sync: nothing hand-written rode along with it (the opener's"
  echo "template-sync: .pr-request.json marker, if present, is machinery and exempt)."
  exit 0
fi

# ------------------------------------------------- the files copier delegated
#
# ESC-14: this check could not pass ANY update that conflicts. It demands a
# byte-identical tree, and a conflict is precisely the case copier hands back to
# a human — the replay reproduces the same markers, so the only tree that
# satisfied the comparison was one committing conflict markers to the default
# branch. Reported twice from one project, on separate updates. A gate blocking
# the change it exists to authorise is the shape of ESC-20, ESC-22 and ESC-24.
#
# So a file the replay left conflict markers in is EXEMPT from byte-matching,
# and named in the output. Everything else is still exact.
#
# FILE LEVEL, NOT HUNK LEVEL, and that is a deliberate trade rather than an
# oversight: a hand edit hidden inside a conflicted file still gets through.
# What replaces the lost precision is the reviewer, who is now told exactly
# which files carry a hand resolution and therefore which ones to read. Hunk
# level — comparing only the unconflicted regions of a marked file — is
# strictly better and materially harder; if a hand edit is ever observed
# riding in this way, that is an escape and the ratchet asks for it.
#
# The markers are copier's own inline-conflict output, which is git's format.
# A file the TEMPLATE legitimately ships containing those tokens would be
# exempted wrongly; no such file exists in this template, and one would be a
# strange thing to ship.
mapfile -t CONFLICTED < <(
  git -C "$WORKTREE" grep -lE '^<<<<<<< ' -- . 2>/dev/null | sort -u || true
)

if [[ ${#CONFLICTED[@]} -gt 0 ]]; then
  # Compare every path EXCEPT those, by diffing the two trees and dropping the
  # exempt paths from the result. An empty remainder means the pull request
  # matches the replay everywhere copier did not delegate.
  mapfile -t DIFFERING < <(
    git -C "$ROOT" diff --name-only "$REPLAYED_TREE" "$HEAD_TREE" || true
  )
  declare -a UNEXPLAINED=()
  for path in "${DIFFERING[@]:-}"; do
    [[ -z "$path" ]] && continue
    exempt=0
    for c in "${CONFLICTED[@]}"; do [[ "$c" == "$path" ]] && exempt=1 && break; done
    [[ "$exempt" -eq 1 ]] || UNEXPLAINED+=("$path")
  done

  if [[ ${#UNEXPLAINED[@]} -eq 0 ]]; then
    echo "template-sync: PASS — the diff is \`copier update\` to ${TARGET_REF}, with"
    echo "template-sync: ${#CONFLICTED[@]} file(s) copier could not merge and handed to a human:"
    printf 'template-sync:   %s\n' "${CONFLICTED[@]}"
    cat <<MSG
template-sync:
template-sync: Those files are EXEMPT from the byte-for-byte comparison, because
template-sync: the replay left conflict markers in them and the only tree that
template-sync: would otherwise pass is one committing markers to the default
template-sync: branch. Every other path matches the replay exactly.
template-sync:
template-sync: THE EXEMPTION IS FILE-WIDE. A hand edit inside one of those files
template-sync: is not detected here — read them.
MSG
    exit 0
  fi

  echo "template-sync: FAIL — this pull request is not a pure template sync." >&2
  echo >&2
  echo "copier could not merge these files and handed them to a human, so they" >&2
  echo "are exempt from the comparison:" >&2
  printf '  %s\n' "${CONFLICTED[@]}" >&2
  echo >&2
  echo "But these differ from the replay and copier did NOT delegate them:" >&2
  printf '  %s\n' "${UNEXPLAINED[@]}" >&2
  echo >&2
  cat >&2 <<'EOF'
A conflict resolution explains a difference in a conflicted file. It does not
explain a difference anywhere else. Rebuild the branch from the template's
output, resolve only what copier marks, and put any hand change in its own
later pull request with a plan.
EOF
  exit 1
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
