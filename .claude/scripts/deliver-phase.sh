#!/usr/bin/env bash
#
# deliver-phase.sh — read the world, say what the delivery loop does next.
#
# The phase logic for unattended delivery lives HERE, once, and both drivers
# consume it: `deliver-loop.sh` on a local machine, and the `/deliver-loop`
# command in a Claude Code web session. One detector is what keeps the two
# modes from drifting — a phase bug is fixed in one place and both inherit it.
#
# READ-ONLY by contract. This script mutates nothing: no commits, no pushes,
# no sessions. It recomputes the project's state from the tree and the open
# pull requests every time it runs, because recomputed state cannot go stale
# and cannot be corrupted by a killed run — the driver persists almost nothing
# and trusts none of what it does persist.
#
# Output: KEY=VALUE lines, PHASE first, then BASE (the base branch this
# detection was scoped to). The phases, in detection priority:
#
#   PHASE=WAIT PR=<n> HEADREF=<ref>   an open pipeline pull request TARGETING
#                                     THIS RUN'S BASE BRANCH — nothing is
#                                     dispatched while one is open (the
#                                     one-PR-per-base rule, AGENTS.md); wait on
#                                     its checks
#   PHASE=ORACLE REASON=uncertainties UNRULED=<BL ids>
#                                     a plan filed HIGH-risk uncertainties and
#                                     no decision cites them yet — planning is
#                                     blocked until the oracle rules
#   PHASE=ORACLE REASON=evidence UNCITED=<ids>
#                                     logged evidence (escapes, backlog items,
#                                     LOW uncertainties) no decision has
#                                     metabolised, no closure in
#                                     docs/escapes.done.md has finished, and no
#                                     prior oracle run has dismissed — the
#                                     oracle looks before more work is planned
#                                     on a possibly-wrong design
#   PHASE=STEWARD ODS=<OD ids>        landed decisions added requirements no
#                                     plan covers — one steward per decision
#   PHASE=PLAN REQS=<R ids>           owner-side requirements no plan covers —
#                                     plan the next milestone
#   PHASE=ORCHESTRATE SLUG=<slug>     a landed plan with no merged feat/ pull
#                                     request, and whose front matter does not
#                                     say `status: merged` — build it
#   PHASE=ACCEPTANCE [CRITERIA=<S ids>]
#                                     everything planned and merged — check
#                                     the built system against the design's
#                                     success criteria. CRITERIA lists the
#                                     scripted criteria failing right now, as
#                                     information for the acceptance session;
#                                     the route out of a failing one is the
#                                     ORACLE phase, reached because the
#                                     acceptance pass files it as a BL-<n>
#   PHASE=SETUP REASON=<text>         coverage.sh rc 2: no design, or a design
#                                     without ids. /design is interactive and
#                                     owner-landed; no loop can do it
#
# Optional env:
#   GH              default: gh      (tests substitute a stub)
#   RUN_BASE        the base branch this run merges into. Defaults to the
#                   repository's default branch (origin/HEAD, falling back to
#                   the current branch). Every pull-request query below is
#                   scoped to it: a pull request targeting a DIFFERENT base
#                   belongs to a different run and neither holds this loop nor
#                   marks this run's plans built. Two PRs into one base is
#                   still illegal; two PRs into two separate bases is two runs.
#   PROCESSED_FILE  a file of evidence ids (one per line) a previous oracle run
#                   read and explicitly declined to act on — the driver records
#                   these from the handoff so the loop cannot thrash re-running
#                   the oracle over evidence it already dismissed
#   BACKLOG, LEDGER, DONE_LEDGER, ORACLE_DOC, PLANS_DIR, ACCEPTANCE_DIR
#                   the usual overrides

# No -e: this file is greps all the way down, and under errexit a grep that
# legitimately matches nothing aborts the whole detection mid-phase. Failures
# that matter are handled by hand.
set -uo pipefail

GH="${GH:-gh}"
BACKLOG="${BACKLOG:-docs/BACKLOG.md}"
LEDGER="${LEDGER:-docs/escapes.md}"
DONE_LEDGER="${DONE_LEDGER:-docs/escapes.done.md}"
ORACLE_DOC="${ORACLE_DOC:-docs/DESIGN.oracle.md}"
PLANS_DIR="${PLANS_DIR:-docs/plans}"
ACCEPTANCE_DIR="${ACCEPTANCE_DIR:-acceptance}"
PROCESSED_FILE="${PROCESSED_FILE:-}"

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" \
  || { echo "deliver-phase: not inside a git repository" >&2; exit 2; }
cd "$ROOT" || exit 2

# The base branch this run merges into. Scoping every pull-request query to it
# is what lets two runs share one repository on two separate base branches:
# each detector sees only its own run's pull requests. Defaults to the
# repository's default branch, so a single-run repository behaves as before.
if [[ -z "${RUN_BASE:-}" ]]; then
  RUN_BASE="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')"
  [[ -n "$RUN_BASE" ]] || RUN_BASE="$(git branch --show-current)"
fi

# REST, never GraphQL, for every API read this script makes. A hosted web
# session's egress proxy serves REST plus only a pinned set of review GraphQL
# operations — `gh pr list` is GraphQL, so on that platform it dies with an
# error that blames the credential, which is fine (ESC-51). REST answers the
# same questions and works everywhere, so there is ONE code path, not a local
# one and a hosted one. The repository name comes from the git remote for the
# same reason: `gh repo view` is GraphQL too.
if [[ -z "${REPO:-}" ]]; then
  REPO="$(git remote get-url origin 2>/dev/null \
    | sed -E 's#^(git@[^:/]+:|https?://[^/]+/|ssh://git@[^/]+/)##; s#\.git$##')"
fi
[[ -n "$REPO" ]] \
  || { echo "deliver-phase: cannot resolve owner/repo from the origin remote" >&2; exit 2; }

# ------------------------------------------------- 1. an open pipeline PR?
# Any open pull request TARGETING THIS RUN'S BASE holds the loop: the one-PR
# rule is about the tree the checks tested being the tree the merge lands on,
# and that is violated by ANY concurrent merge into the same base, not just a
# feature's. A pull request into a DIFFERENT base lands on a different tree —
# it belongs to a different run and is deliberately not this loop's business.
OPEN_PR="$("$GH" api "repos/$REPO/pulls?state=open&base=$RUN_BASE&per_page=30" \
  --jq '.[0] | "\(.number) \(.head.ref)"' 2>/dev/null || true)"
if [[ -n "$OPEN_PR" && "$OPEN_PR" != "null null" ]]; then
  echo "PHASE=WAIT"
  echo "BASE=$RUN_BASE"
  echo "PR=${OPEN_PR%% *}"
  echo "HEADREF=${OPEN_PR#* }"
  exit 0
fi

# Ids a decision in the ledger cites anywhere. Coarse on purpose: the precise
# per-decision resolution belongs to oracle-decisions.sh at merge time; here a
# cited id just means "the oracle has seen this".
cited() {
  [[ -f "$ORACLE_DOC" ]] && grep -oE '(ESC|BL)-[0-9]+' "$ORACLE_DOC" | sort -u || true
}
CITED_IDS="$(cited)"
is_cited() { grep -qxF "$1" <<<"$CITED_IDS"; }
is_processed() {
  [[ -n "$PROCESSED_FILE" && -f "$PROCESSED_FILE" ]] \
    && grep -qxF "$1" "$PROCESSED_FILE"
}

# Ids the repository records as FINISHED, in docs/escapes.done.md. An
# append-only ledger cannot be edited to mark something done, so "closed" had
# nowhere to live that a script could read — and this detector consequently
# handed the oracle every escape a project had ever logged, including ones fixed
# months earlier with a demonstrated check.
#
# COMMITTED, which is the half that matters. The processed-evidence file above
# is gitignored: it survives on one laptop and vanishes with a reclaimed web
# container, so the same repository gave two different answers depending on
# where the driver ran. A closure is a fact in git and reads the same everywhere.
#
# It is not a free pass. escapes-append-only.sh holds this file immutable and
# refuses a closure that does not name a path that exists, so a row here is a
# claim somebody can open rather than an assertion that something is fine.
closed() {
  [[ -f "$DONE_LEDGER" ]] && grep -E '^\|' "$DONE_LEDGER" | grep -oE 'ESC-[0-9]+' | sort -u || true
}
CLOSED_IDS="$(closed)"
is_closed() { grep -qxF "$1" <<<"$CLOSED_IDS"; }

# --------------------------------- 2. HIGH uncertainties with no ruling yet?
# Items in the backlog's uncertainties section: an id plus the word HIGH on
# the item's first line. A HIGH uncertainty blocks planning by design — it is
# the one guess the planner was not allowed to proceed on.
UNRULED=""
if [[ -f "$BACKLOG" ]]; then
  while IFS= read -r line; do
    id="$(grep -oE 'BL-[0-9]+' <<<"$line" | head -1 || true)"
    [[ -n "$id" ]] || continue
    grep -qE '\bHIGH\b' <<<"$line" || continue
    is_cited "$id" && continue
    UNRULED="$UNRULED $id"
  done < <(awk '/^## Uncertainties awaiting oracle ruling/{insec=1; next}
                insec && /^## /{insec=0} insec' "$BACKLOG")
fi
if [[ -n "${UNRULED# }" ]]; then
  echo "PHASE=ORACLE"
  echo "BASE=$RUN_BASE"
  echo "REASON=uncertainties"
  echo "UNRULED=${UNRULED# }"
  exit 0
fi

# --------------------------------------------- 3. evidence nobody has read?
# Every real id in the ledgers, minus what a decision cites, minus what a
# prior run explicitly dismissed. The oracle rules on a possibly-wrong design
# BEFORE more work is planned against it — that ordering is the role's point.
UNCITED=""
IDS_TMP="$(mktemp)"
{
  [[ -f "$LEDGER"  ]] && grep -E '^\|' "$LEDGER" | grep -oE 'ESC-[0-9]+' || true
  [[ -f "$BACKLOG" ]] && grep -oE 'BL-[0-9]+' "$BACKLOG" || true
} | sort -u > "$IDS_TMP" || true
while IFS= read -r id; do
  [[ -n "$id" ]] || continue
  is_cited "$id" && continue
  is_closed "$id" && continue
  is_processed "$id" && continue
  UNCITED="$UNCITED $id"
done < "$IDS_TMP"
rm -f "$IDS_TMP"
if [[ -n "${UNCITED# }" ]]; then
  echo "PHASE=ORACLE"
  echo "BASE=$RUN_BASE"
  echo "REASON=evidence"
  echo "UNCITED=${UNCITED# }"
  exit 0
fi

# ------------------------------------------------------- 4. coverage gaps?
COV_RC=0
COV_OUT="$(.github/scripts/coverage.sh 2>&1)" || COV_RC=$?
case "$COV_RC" in
  2)
    echo "PHASE=SETUP"
    echo "BASE=$RUN_BASE"
    echo "REASON=$(head -1 <<<"$COV_OUT")"
    exit 0 ;;
  1)
    GAPS="$(sed -n 's/^.*requirement(s) with no plan: //p' <<<"$COV_OUT" | head -1)"
    # Oracle-added requirements (R1000 and up) are planned by a steward from
    # their decision; owner requirements are planned as a milestone. Stewards
    # first: those decisions exist because the design was WRONG, and building
    # more against the uncorrected shape is the waste the oracle exists to
    # stop.
    STEWARD_ODS=""
    PLAN_REQS=""
    for req in $GAPS; do
      n="${req#R}"
      if [[ "$n" =~ ^[0-9]+$ ]] && [[ "$n" -ge 1000 ]]; then
        od="$(grep -B100 -- "- \*\*Requirements added:\*\*.*\b$req\b" "$ORACLE_DOC" 2>/dev/null \
              | grep -oE '^## OD-[0-9]+' | tail -1 | sed 's/^## //' || true)"
        [[ -n "$od" ]] && ! grep -qF "$od" <<<"$STEWARD_ODS" && STEWARD_ODS="$STEWARD_ODS $od"
      else
        PLAN_REQS="$PLAN_REQS $req"
      fi
    done
    if [[ -n "${STEWARD_ODS# }" ]]; then
      echo "PHASE=STEWARD"
      echo "BASE=$RUN_BASE"
      echo "ODS=${STEWARD_ODS# }"
      exit 0
    fi
    echo "PHASE=PLAN"
    echo "BASE=$RUN_BASE"
    echo "REQS=${PLAN_REQS# }"
    exit 0 ;;
esac

# ------------------------------------- 5. planned and merged, but unbuilt?
# A plan is BUILT when a feat/ pull request carrying its slug has merged INTO
# THIS RUN'S BASE. The feat/ prefix matters: the plan's own docs/ pull request
# also carries the slug, and counting it would mark every plan built the moment
# it landed. The --base scope matters just as much: a twin run on another base
# branch merges the same slugs, and counting ITS merges would mark this run's
# plans built with the work simply absent here.
# REST has no state=merged filter: closed pull requests include unmerged ones,
# and merged is the merged_at field being set. --paginate replaces --limit 200.
MERGED_REFS="$("$GH" api --paginate "repos/$REPO/pulls?state=closed&base=$RUN_BASE&per_page=100" \
  --jq '.[] | select(.merged_at != null) | .head.ref' 2>/dev/null || true)"
#
# WHICH STRING IDENTIFIES A PLAN. The front-matter `slug:` field, not the
# filename. plan-resolve.sh — the check that decides which plan a branch
# implements — reads the field, and this used to read `basename`, so the two
# halves of the system identified the same object by different names and
# nothing reconciled them. A plan filed as `sync.md` with `slug:
# milestone-4-sync-transport` was matched against an earlier merged
# `feat/sync-index-1` by prefix, marked built, and never orchestrated. No pull
# request was ever opened for it, so no gate ever got the chance to notice:
# coverage.sh reported its requirements covered, the loop walked to ACCEPTANCE,
# and the run exited 0 with the work simply absent.
#
# The match is also anchored at both ends now. `^feat/.*${slug}` let any slug
# that is a substring of a merged branch count as built — the exact collision
# plan-resolve.sh treats as a hard error ("a slug that is a substring of
# another, like 'auth' and 'auth-tokens', will always collide"), which it can
# only do for branches somebody actually opened. Here the whole point is that
# nobody opens one, so the guard has to live on this side too.
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  [[ "$(basename "$f")" == _* ]] && continue
  # The authoritative slug, read the same way plan-resolve.sh reads it. Fall
  # back to the filename only when a plan has no field at all — plan-lint.sh
  # fails such a plan on its own pull request, so this is a courtesy, not a
  # path anything should rely on.
  slug="$(awk '
    NR==1 && $0 ~ /^---[[:space:]]*$/ { infm=1; next }
    infm && $0 ~ /^---[[:space:]]*$/  { exit }
    infm && $0 ~ /^slug:/ { sub(/^slug:[[:space:]]*/, ""); gsub(/["'"'"']/, ""); print; exit }
  ' "$f" 2>/dev/null | head -1)"
  [[ -n "$slug" ]] || slug="$(basename "$f" .md)"

  # A plan that DECLARES its work landed is built, whatever the branch names
  # say. `status: merged` is already in the plan template's vocabulary
  # (draft | in-flight | merged) and this is what it was for.
  #
  # Without it, a RETROSPECTIVE plan — one written to record work that shipped
  # before the plan existed — can never be satisfied: no `feat/<slug>` branch
  # will ever be merged for it, so the detector asks for an orchestrator to
  # build what is already there, forever. The same is true of any plan whose
  # work landed on a branch that did not follow the convention.
  #
  # It is a declaration and not a proof, which is the honest description. What
  # makes it safe to trust is where it lives: docs/plans/ is CODEOWNERS-owned,
  # so setting this word is the owner's, and the review gate reads the diff that
  # sets it. The steward's docs/plans/oracle/ is deliberately NOT owned — a plan
  # there that declared itself built without building anything would be an
  # escape, and the ratchet applies.
  status="$(awk '
    NR==1 && $0 ~ /^---[[:space:]]*$/ { infm=1; next }
    infm && $0 ~ /^---[[:space:]]*$/  { exit }
    infm && $0 ~ /^status:/ { sub(/^status:[[:space:]]*/, ""); sub(/[[:space:]]*#.*$/, ""); gsub(/["'"'"']/, ""); print; exit }
  ' "$f" 2>/dev/null | head -1)"
  [[ "$status" == "merged" ]] && continue

  # Anchored: the branch is `feat/<slug>` or `feat/<slug>-<something>`, never
  # `feat/<slug-as-a-substring-of-a-different-name>`.
  if ! grep -qE "^feat/${slug}([/-][^/]*)?$" <<<"$MERGED_REFS"; then
    echo "PHASE=ORCHESTRATE"
    echo "BASE=$RUN_BASE"
    echo "SLUG=$slug"
    exit 0
  fi
done < <(find "$PLANS_DIR" -name '*.md' 2>/dev/null | sort)

# ---------------------------------------------------------------- 6. done
# ...and say which scripted success criteria are currently failing, so the
# acceptance session is told what it is walking into rather than discovering it.
#
# Reported, never branched on. A failing criterion does not become its own
# phase: the route out of one is the ORACLE phase above, reached because the
# acceptance pass FILES the failure as a BL-<n>. Making it a phase here would
# put the loop in charge of deciding a criterion is unmeetable, which is exactly
# the judgement docs/acceptance.md exists to keep away from the pipeline.
echo "PHASE=ACCEPTANCE"
echo "BASE=$RUN_BASE"
FAILING=""
if [[ -d "$ACCEPTANCE_DIR" ]]; then
  while IFS= read -r s; do
    [[ -z "$s" ]] && continue
    bash "$s" >/dev/null 2>&1 || FAILING="$FAILING $(basename "$s" .sh)"
  done < <(find "$ACCEPTANCE_DIR" -maxdepth 1 -name 'S[0-9]*.sh' 2>/dev/null | sort)
fi
[[ -n "${FAILING# }" ]] && echo "CRITERIA=${FAILING# }"
exit 0
