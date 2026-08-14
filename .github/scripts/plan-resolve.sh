#!/usr/bin/env bash
#
# plan-resolve.sh — find the plan a pull request belongs to.
#
# Plans live at docs/plans/<slug>.md and declare a `slug` in their front-matter.
# Every branch working a plan must contain that slug in its name, so resolution
# is a pure offline string match — no API calls, no PR body parsing.
#
# Prints the resolved plan's path on stdout and exits 0.
#
# FAILS HARD (exit 1) with a diagnosis when no single plan resolves. That is
# deliberate: a PR with no plan means either the planning step was skipped or the
# branch is misnamed, and both are wiring faults worth stopping for. An estimate
# the reviewer never receives is a gate that silently stopped working.
#
# Branches whose name starts with an exempt prefix skip the check entirely and
# print nothing (exit 0) — see EXEMPT_PREFIXES. The exemption is SIZE-CAPPED:
# it exists for typos and doc tweaks, so a branch claiming it while adding more
# than EXEMPT_MAX_ADDED lines fails instead. Without the cap the hatch is
# self-service — renaming a branch to chore/ skips this check AND leaves the
# review gate with no plan to check conformance against, which is two gates
# disarmed by a string the author chooses.
#
# The resolved plan must ALSO already exist at BASE_SHA. A plan introduced by
# the same pull request it authorises is not a specification, it is a
# description written after the fact: the reviewer would be checking the diff
# against a document from that same diff, including the estimates it is judged
# by and the file list that defines scope creep. Plans land first, on their own
# (docs/-prefixed) pull request, and the work branches off afterwards.
#
# Required env:
#   HEAD_REF   the PR's head branch name (e.g. feat/draft-saving)
#   BASE_SHA   the PR's base commit — the plan must exist here, and the exempt
#              size cap is measured against it
# Optional env:
#   PLANS_DIR         where plans live (default: docs/plans)
#   HEAD_SHA          the PR head commit (default: HEAD)
#   EXEMPT_MAX_ADDED  added-line cap for exempt branches (default: 50)

set -euo pipefail

# Keep in sync with the Planning rule in AGENTS.md.
EXEMPT_PREFIXES=(chore/ docs/)
EXEMPT_MAX_ADDED="${EXEMPT_MAX_ADDED:-50}"

ROOT="$(git rev-parse --show-toplevel)"
PLANS_DIR="${PLANS_DIR:-docs/plans}"
: "${HEAD_REF:?HEAD_REF is required (the PR head branch name)}"
: "${BASE_SHA:?BASE_SHA is required (the PR base commit)}"
HEAD_SHA="${HEAD_SHA:-HEAD}"

die() { echo "plan-resolve: $*" >&2; exit 1; }

for prefix in "${EXEMPT_PREFIXES[@]}"; do
  if [[ "$HEAD_REF" == "$prefix"* ]]; then
    added="$(git -C "$ROOT" diff --numstat "${BASE_SHA}...${HEAD_SHA}" \
      | awk '{ s += $1 } END { print s + 0 }')"
    if [[ "$added" -gt "$EXEMPT_MAX_ADDED" ]]; then
      die "branch '$HEAD_REF' claims the exempt prefix '$prefix' but adds $added
lines (cap: $EXEMPT_MAX_ADDED).

The exemption is for changes too small to plan — a typo, a doc tweak. A change
this size needs a plan: copy $PLANS_DIR/_TEMPLATE.md to $PLANS_DIR/<slug>.md,
land it, then branch with the slug in the branch name.

Raising the cap to get this through is gate tampering under AGENTS.md."
    fi
    echo "plan-resolve: branch '$HEAD_REF' uses the exempt prefix '$prefix' \
($added added lines, cap $EXEMPT_MAX_ADDED) — no plan required" >&2
    exit 0
  fi
done

DIR="$ROOT/$PLANS_DIR"
[[ -d "$DIR" ]] || die "no $PLANS_DIR/ directory.
Branch '$HEAD_REF' needs a plan. Write one (copy $PLANS_DIR/_TEMPLATE.md to
$PLANS_DIR/<slug>.md), or use a chore/ or docs/ branch prefix if the change is
genuinely trivial."

# Collect slug -> path for every real plan (the _TEMPLATE is not a plan).
declare -a SLUGS=() PATHS=() UNSLUGGED=()
while IFS= read -r file; do
  base="$(basename "$file")"
  [[ "$base" == _* ]] && continue
  # `slug:` from the front-matter only: stop at the closing --- so a stray
  # "slug:" later in the body can't be picked up instead.
  slug="$(awk '
    NR==1 && $0=="---" { infm=1; next }
    infm && $0=="---"  { exit }
    infm && /^slug:/   { sub(/^slug:[[:space:]]*/, ""); sub(/[[:space:]]*(#.*)?$/, ""); print; exit }
  ' "$file")"
  if [[ -z "$slug" ]]; then
    UNSLUGGED+=("${file#"$ROOT"/}")
    continue
  fi
  SLUGS+=("$slug")
  PATHS+=("${file#"$ROOT"/}")
done < <(find "$DIR" -maxdepth 1 -name '*.md' | sort)

if [[ ${#SLUGS[@]} -eq 0 ]]; then
  msg="no plan in $PLANS_DIR/ declares a slug."
  [[ ${#UNSLUGGED[@]} -gt 0 ]] && msg+="
Files present but missing a 'slug:' in their front-matter: ${UNSLUGGED[*]}"
  die "$msg
Branch '$HEAD_REF' needs a plan with a slug that appears in the branch name."
fi

declare -a MATCHED=() MATCHED_SLUG=()
for i in "${!SLUGS[@]}"; do
  if [[ "$HEAD_REF" == *"${SLUGS[$i]}"* ]]; then
    MATCHED+=("${PATHS[$i]}")
    MATCHED_SLUG+=("${SLUGS[$i]}")
  fi
done

case ${#MATCHED[@]} in
  1)
    # The plan must predate the work. Reading it from the head checkout is what
    # makes this check worth doing at all — see the header.
    if ! git -C "$ROOT" cat-file -e "${BASE_SHA}:${MATCHED[0]}" 2>/dev/null; then
      die "plan '${MATCHED[0]}' does not exist at this pull request's base commit.

It is being introduced by the pull request it is supposed to specify, so the
reviewer would check this diff against a document written alongside it — the
estimates, the file list, and the slice boundaries would all be whatever this
change needed them to be.

Land the plan first, on its own docs/ pull request, then branch off the default
branch with the slug in the branch name and open the implementation separately."
    fi
    echo "${MATCHED[0]}"
    ;;
  0)
    printf -v available '  %s\n' "${SLUGS[@]}"
    die "no plan slug appears in branch '$HEAD_REF'.
Available slugs:
$available
Fix one of the two: rename the branch to contain the plan's slug, or correct the
'slug:' field in the plan. They must agree — that match is the only link between
a PR and the plan it is judged against."
    ;;
  *)
    printf -v hits '  %s\n' "${MATCHED_SLUG[@]}"
    die "branch '$HEAD_REF' matches more than one plan slug:
$hits
Slugs must be unambiguous. Rename a plan's slug so only one matches (a slug that
is a substring of another, like 'auth' and 'auth-tokens', will always collide)."
    ;;
esac
