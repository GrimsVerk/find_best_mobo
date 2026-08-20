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
# One carve-out from the cap, and only one: a branch whose diff is entirely
# within the planning documents and run evidence (the paths listed at
# PLANNING_PATHS below, docs/plans/ and docs/DESIGN.md foremost). Those are the
# documents the process itself demands, they are far larger than any cap for
# typos, and no plan can ever cover them — a plan branch cannot resolve to a
# plan that does not exist yet, which is the point of the rule, not a loophole
# in it. One path outside them and the cap applies as normal.
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
#   DESIGN_DOC        the design doc (default: docs/DESIGN.md)
#   HEAD_SHA          the PR head commit (default: HEAD)
#   EXEMPT_MAX_ADDED  added-line cap for exempt branches (default: 50)

set -euo pipefail

# Keep in sync with the Planning rule in AGENTS.md.
#
# Two kinds of exemption, and the difference is what earns it.
#
# EXEMPT_PREFIXES are exempt because the change is too small to plan, so they
# are size-capped — the cap is the whole reason the exemption is not a
# self-service bypass.
#
# SYNC_PREFIXES are exempt because the change was specified and reviewed
# somewhere else: in the template repository, at the merge that produced the
# version being pulled in. No plan can ever resolve for one. They are NOT
# size-capped, because a template update is whatever size the template made it —
# instead they are guarded by the `template-sync` check, which proves the diff
# is byte-for-byte `copier update` output and nothing else. That is a stronger
# guarantee than a plan, not a weaker one, and it is why an uncapped exemption
# is safe here and would not be safe for chore/.
#
# PLANNING_PATHS are the third case, and the one the cap got wrong. The process
# demands two documents that no plan can ever cover and that no ordinary
# exemption can fit: a completed design doc runs to several hundred lines, and
# the plan template is 124 lines before anything is filled in, so every plan
# blows a 50-line cap too. A plan branch also cannot resolve to a plan that does
# not yet exist on the default branch — which is that rule's whole point.
#
# So a branch whose additions are confined to these paths keeps the exemption at
# any size. A branch adding a plan is not skipping planning; it IS the planning,
# and it is reviewed the same way every plan is: `CODEOWNERS` puts these paths
# behind the owner, so merging one is the ruling on it. The moment such a branch
# also touches code, the cap applies again — that is the case the cap exists for,
# and the check below is a whole-diff test, not a per-file one, precisely so that
# a plan cannot be used as cover for the code smuggled alongside it.
#
# Without this, the only way through was the owner bypassing the gate. That
# happened three times in one session downstream, and a gate bypassed three
# times in a day is one nobody will trust on the day it matters.
EXEMPT_PREFIXES=(chore/ docs/)
SYNC_PREFIXES=(template/)
EXEMPT_MAX_ADDED="${EXEMPT_MAX_ADDED:-50}"
DESIGN_DOC="${DESIGN_DOC:-docs/DESIGN.md}"
# The oracle's documents are planning documents for the same reason: no plan can
# cover the design that plans are written against, and a handoff naming what
# needs planning this run is not itself plannable work. docs/plans/oracle/ needs
# no entry here — it is already inside PLANS_DIR.
ORACLE_DOC="${ORACLE_DOC:-docs/DESIGN.oracle.md}"
ORACLE_DIR="${ORACLE_DIR:-docs/oracle}"
# docs/VISION.md belongs here for exactly the same reasons as the design doc: it
# is CODEOWNERS-owned, no plan can cover it, and a filled-in one runs to well
# over a hundred lines. Left out, the single document the whole oracle
# arrangement depends on was the one document that could not be written — the
# branch writing it failed the plan check at 114 added lines.
VISION_DOC="${VISION_DOC:-docs/VISION.md}"
# docs/acceptance.md and docs/architecture.md are the fourth and fifth
# instances of the same mistake, found by a review rather than by a bypass.
# Both are REQUIRED by AGENTS.md — the acceptance pass must fill one, and a
# slice is not finished until the other is accurate — and both are necessarily
# long on any project big enough for them to matter. Neither could be written:
# the acceptance branch is `docs/`-prefixed, so it met the 50-line cap meant
# for typo fixes, failed, and failed identically on all three fix attempts,
# stopping the run. The instruction the failure gives ("write a plan for it")
# is impossible to follow, because acceptance is not plannable work and a plan
# covering it would name no requirement ids.
#
# ESC-22 already recorded the general form: "a document this process REQUIRES
# and that is necessarily long needs its carve-out in the same change that
# introduces it, or it ships unwritable." These two shipped without one.
#
# Note what the carve-out does not weaken. docs/acceptance.md is
# CODEOWNERS-owned, so the owner still reviews it — and it is the single
# artifact in an unattended run whose pull request requires that review, which
# is precisely why it must be able to land at all.
ACCEPTANCE_DOC="${ACCEPTANCE_DOC:-docs/acceptance.md}"
ARCHITECTURE_DOC="${ARCHITECTURE_DOC:-docs/architecture.md}"
# docs/runs/ is the sixth instance, found by the first unattended run: the
# delivery driver lands its run report and the review gate's payloads there at
# EVERY stop, on a docs/-prefixed branch, and a real run's report is always
# longer than the cap. So the evidence the design calls "committed, on its own
# pull request, at every stop" was the one thing that could not land (ESC-40).
# A run report is by construction not plannable work — it is a record of what
# already happened, written by the machinery this process itself demands.
RUNS_DIR="${RUNS_DIR:-docs/runs}"
# docs/BACKLOG.md is the seventh, and it is not about size — it is about the
# company it keeps. AGENTS.md's Planning rule REQUIRES the unattended planner
# to file its guessed decisions as BL-<n> backlog items alongside the plan
# ("every guess is filed either way"), but the moment docs/BACKLOG.md joined a
# plan's diff the branch fell out of this carve-out and the whole plan hit the
# 50-line cap. Filing was mechanically impossible on the only branch the rule
# requires it on, which pushed first-run plans into self-ruling instead
# (ESC-41). The backlog's own shape is guarded separately by
# backlog-append-only.sh; the whole-diff test below still caps any branch that
# also touches code.
BACKLOG_DOC="${BACKLOG_DOC:-docs/BACKLOG.md}"

ROOT="$(git rev-parse --show-toplevel)"
PLANS_DIR="${PLANS_DIR:-docs/plans}"
: "${HEAD_REF:?HEAD_REF is required (the PR head branch name)}"
: "${BASE_SHA:?BASE_SHA is required (the PR base commit)}"
HEAD_SHA="${HEAD_SHA:-HEAD}"

die() { echo "plan-resolve: $*" >&2; exit 1; }

for prefix in "${SYNC_PREFIXES[@]}"; do
  if [[ "$HEAD_REF" == "$prefix"* ]]; then
    echo "plan-resolve: branch '$HEAD_REF' is a template sync ('$prefix') — no plan" >&2
    echo "plan-resolve: applies. The template-sync check verifies it instead, and" >&2
    echo "plan-resolve: is a required check precisely because this one steps aside." >&2
    exit 0
  fi
done

for prefix in "${EXEMPT_PREFIXES[@]}"; do
  if [[ "$HEAD_REF" == "$prefix"* ]]; then
    added="$(git -C "$ROOT" diff --numstat "${BASE_SHA}...${HEAD_SHA}" \
      | awk '{ s += $1 } END { print s + 0 }')"

    # Is every path in this diff a planning document? One path outside them and
    # the answer is no — the branch is carrying something else as well, and the
    # cap is exactly the check for that.
    planning_only=1
    while IFS= read -r path; do
      [[ -z "$path" ]] && continue
      case "$path" in
        "$PLANS_DIR"/*|"$DESIGN_DOC"|"$ORACLE_DOC"|"$ORACLE_DIR"/*|"$VISION_DOC") ;;
        "$ACCEPTANCE_DOC"|"$ARCHITECTURE_DOC"|"$RUNS_DIR"/*|"$BACKLOG_DOC") ;;
        # The eighth carve-out member, and the first that is machinery rather
        # than a document (ESC-56): a driver that cannot hold App identity
        # asks the server-side opener for its pull request by committing this
        # marker as the branch's last commit (ESC-53). The opener's design
        # placed it at the repository root ON PURPOSE — outside
        # CODEOWNERS-owned .github/ — and this list was not updated to match,
        # so the marker's three lines evicted otherwise-exempt branches from
        # the carve-out and every web-lane planning pull request failed the
        # cap it was exempt from.
        ".pr-request.json") ;;
        *) planning_only=0; break ;;
      esac
    done < <(git -C "$ROOT" diff --name-only "${BASE_SHA}...${HEAD_SHA}")

    if [[ "$planning_only" -eq 1 && "$added" -gt "$EXEMPT_MAX_ADDED" ]]; then
      echo "plan-resolve: branch '$HEAD_REF' adds $added lines, all of them in \
$PLANS_DIR/, $DESIGN_DOC, $VISION_DOC, $ORACLE_DOC, $ORACLE_DIR/, \
$ACCEPTANCE_DOC, $ARCHITECTURE_DOC, $RUNS_DIR/, $BACKLOG_DOC or the opener's \
.pr-request.json marker — the planning documents themselves, the run \
evidence, and the pull-request machinery, which no plan can cover. Exempt from the size \
cap; the owner still reviews $DESIGN_DOC and $PLANS_DIR/ via CODEOWNERS, and \
$ORACLE_DOC is constrained by the oracle-decisions check instead." >&2
      exit 0
    fi

    if [[ "$added" -gt "$EXEMPT_MAX_ADDED" ]]; then
      die "branch '$HEAD_REF' claims the exempt prefix '$prefix' but adds $added
lines (cap: $EXEMPT_MAX_ADDED).

The exemption is for changes too small to plan — a typo, a doc tweak. A change
this size needs a plan: copy $PLANS_DIR/_TEMPLATE.md to $PLANS_DIR/<slug>.md,
land it, then branch with the slug in the branch name.

The cap does not apply to a branch whose additions are ENTIRELY within
$PLANS_DIR/, $DESIGN_DOC, $VISION_DOC, $ORACLE_DOC, $ORACLE_DIR/,
$ACCEPTANCE_DOC, $ARCHITECTURE_DOC, $RUNS_DIR/ or $BACKLOG_DOC — writing a
plan is not skipping planning. This
branch touches something else as well, so it is not that case. Split it: the
planning documents on one branch, the rest on its own with a plan behind it.

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
  # No -maxdepth: a steward's plans live under $PLANS_DIR/oracle/, and a depth
  # limit made them unresolvable — the branch would fail with "no plan slug
  # appears in this branch" while the plan sat right there.
done < <(find "$DIR" -name '*.md' | sort)

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
