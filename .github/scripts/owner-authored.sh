#!/usr/bin/env bash
#
# owner-authored.sh — the design and the vision are landed by the owner, and by
# nobody else.
#
# WHY, IN ONE LINE: if any agent can land `docs/DESIGN.md`, there is no reason
# for `docs/DESIGN.oracle.md` to exist.
#
# The whole arrangement rests on one asymmetry. `docs/DESIGN.md` and
# `docs/VISION.md` are the owner's — the standard everything else is judged
# against, and the tiebreaker an unattended agent reaches for. Against them sits
# `docs/DESIGN.oracle.md`, which an agent MAY write while nobody is awake,
# precisely because it cannot touch the other two. Blur that line and the second
# document is pointless: an agent that can edit the design does not need an
# evidence ledger, it just edits the design.
#
# `CODEOWNERS` alone does not draw the line. It requires the owner's APPROVAL,
# which is one click on a diff someone else composed and opened. This check
# requires the owner's AUTHORSHIP of the pull request itself — a different and
# stronger claim, and the one the owner actually wanted.
#
# WHAT AN AGENT MAY STILL DO, WHICH IS MOST OF THE WORK. Write both documents,
# commit them, push the branch. `/design` does exactly that: it interviews the
# owner and writes their answers down. What it may not do is open the pull
# request. The owner opens it, reads it as a diff, and merges — and that reading
# is the point, because these are the two documents they most need to actually
# know the contents of.
#
# EVERYTHING ELSE IS UNAFFECTED. Plans stay agent-written and agent-opened;
# `docs/DESIGN.oracle.md` and the handoffs stay agent-written and agent-opened.
# From the moment the design and the vision exist, the orchestrator can run to
# completion without this check ever firing again. It guards project SETUP, not
# ongoing work.
#
# Required env:
#   BASE_SHA    the PR's base commit
#   PR_AUTHOR   the login that opened the pull request
# Optional env:
#   HEAD_SHA     default: HEAD
#   OWNER_LOGIN  default: read from .github/CODEOWNERS
#   OWNED_DOCS   default: "docs/DESIGN.md docs/VISION.md"

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
: "${BASE_SHA:?BASE_SHA is required (the PR base commit)}"
HEAD_SHA="${HEAD_SHA:-HEAD}"
OWNED_DOCS="${OWNED_DOCS:-docs/DESIGN.md docs/VISION.md}"

read -r -a DOCS <<< "$OWNED_DOCS"

# Does this pull request touch either document? If not, it is none of this
# check's business and it says so rather than staying silent — a check whose
# normal output is nothing is a check nobody notices has broken.
mapfile -t TOUCHED < <(
  git -C "$ROOT" diff --name-only "${BASE_SHA}...${HEAD_SHA}" -- "${DOCS[@]}"
)
if [[ ${#TOUCHED[@]} -eq 0 ]]; then
  echo "owner-authored: this pull request touches neither ${DOCS[*]} — nothing to check."
  exit 0
fi

# Who owns them? Taken from CODEOWNERS so there is one source of truth, and so
# a project that renames its owner does not have to remember this file exists.
if [[ -z "${OWNER_LOGIN:-}" ]]; then
  OWNER_LOGIN="$(awk '$1 == "/docs/DESIGN.md" { print $2; exit }' \
    "$ROOT/.github/CODEOWNERS" 2>/dev/null || true)"
fi
OWNER_LOGIN="${OWNER_LOGIN#@}"

if [[ -z "$OWNER_LOGIN" ]]; then
  echo "owner-authored: no owner found for docs/DESIGN.md in .github/CODEOWNERS," >&2
  echo "owner-authored: and none given as OWNER_LOGIN. Failing closed: this check" >&2
  echo "owner-authored: cannot be satisfied by a repository it cannot read." >&2
  exit 1
fi

# A team cannot be resolved offline, and guessing is worse than stopping.
if [[ "$OWNER_LOGIN" == */* ]]; then
  echo "owner-authored: the owner is the team '@${OWNER_LOGIN}', and membership" >&2
  echo "owner-authored: cannot be resolved from the repository. Set OWNER_LOGIN to" >&2
  echo "owner-authored: the individual who lands these documents, or drop this" >&2
  echo "owner-authored: check and rely on CODEOWNERS approval alone." >&2
  exit 1
fi

: "${PR_AUTHOR:?PR_AUTHOR is required (the login that opened the pull request)}"

if [[ "$PR_AUTHOR" != "$OWNER_LOGIN" ]]; then
  echo "owner-authored: this pull request touches:" >&2
  printf '  %s\n' "${TOUCHED[@]}" >&2
  cat >&2 <<MSG

...and was opened by '$PR_AUTHOR', not by '$OWNER_LOGIN'.

These two documents are landed by their owner and by nobody else. Not because
an agent cannot be trusted to write them — it can, and it should: writing the
branch is most of the work. Because if any agent can LAND docs/DESIGN.md, then
docs/DESIGN.oracle.md has no reason to exist. That second document is the whole
mechanism by which an agent corrects the design from evidence while nobody is
awake, and it only means something while the first one is out of reach.

An agent's job here ends at a pushed branch. $OWNER_LOGIN opens the pull
request, reads the diff, and merges it — and that reading is the point.

Nothing else is affected: plans, docs/DESIGN.oracle.md and the handoffs are all
still written and opened by agents.
MSG
  exit 1
fi

echo "owner-authored: ${#TOUCHED[@]} owned document(s), opened by '$OWNER_LOGIN'."
