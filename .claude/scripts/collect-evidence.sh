#!/usr/bin/env bash
#
# collect-evidence.sh — gather what a run produced, into the repository.
#
#     .claude/scripts/collect-evidence.sh --run-dir docs/runs/<timestamp> \
#                                         --since <RFC3339>
#
# WHAT WAS WRONG. An unattended run produced a run log that was GITIGNORED, and
# in web mode it lived in a container that is reclaimed. The review gate's
# output was retained nowhere: it assembled a payload, sent it to a model,
# printed the reply to a job log nobody opens, and threw both away. So the
# evidence that would tell the next run what went wrong was destroyed by
# default, and the loop the owner described — run, learn, fix the template, run
# again — had nothing to learn from.
#
# The owner's ruling on where it goes, and it overruled a recommendation to
# leave the bulky payloads in expiring artifacts:
#
#   "its good to think of repo space, but it is just in the beginning, i would
#   rather risk gathering too much data and deal with space issues, than getting
#   stuck without the info to get out of it. so save it in the repo."
#
# A space problem is visible, bounded and fixable later. Missing evidence is
# none of those. If it does become a problem the fix is a RETENTION RULE — prune
# payloads older than N runs, keep every verdict — and never a return to
# discarding them, because discarding them is the defect being repaired.
#
# ONCE PER RUN, NOT ONCE PER PULL REQUEST, and that is deliberate rather than
# lazy: a review job that committed its own output would push to the branch it
# is reviewing and retrigger itself. The driver already opens pull requests and
# already runs once per stop, so it is the right place.
#
# THE HONEST LIMIT. A run that dies hard, or is killed, may end without
# collecting. The run report survives that — the driver writes it as it goes —
# but the review payloads for the last in-flight pull request may not.
#
# Required:
#   --run-dir <path>   where to write (the driver passes docs/runs/<timestamp>)
# Optional:
#   --since <RFC3339>  only collect review runs that started at or after this;
#                      without it, every completed review run is considered,
#                      which on an established repository is a lot
#   --workflow <name>  default: review.yml
#   --limit <n>        default: 100, the runs to consider
# Env:
#   GH                 the GitHub CLI (tests substitute a stub)
#   RUN_BASE           the run's base branch. Review runs are listed
#                      repo-wide, so on a twin-run repository this is what
#                      keeps the OTHER lane's payloads out of this lane's
#                      evidence (ESC-54): a non-default base keeps only
#                      branches carrying its `--<base>` suffix, the default
#                      base skips branches carrying any such suffix. Unset,
#                      it defaults to the default branch.
#
# Exits 0 even when it collects nothing. This is a RECORDER, and a recorder that
# fails a run because there was nothing to record has inverted its own job.

set -uo pipefail

GH="${GH:-gh}"
RUN_DIR=""
SINCE=""
WORKFLOW="review.yml"
LIMIT=100

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-dir)  RUN_DIR="${2:-}"; shift 2 ;;
    --since)    SINCE="${2:-}"; shift 2 ;;
    --workflow) WORKFLOW="${2:-}"; shift 2 ;;
    --limit)    LIMIT="${2:-}"; shift 2 ;;
    -h|--help)  sed -n '2,/^[^#]/p' "$0" | sed -n 's/^# \{0,1\}//p'; exit 0 ;;
    *) echo "collect-evidence: unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$RUN_DIR" ]] || { echo "collect-evidence: --run-dir is required" >&2; exit 2; }

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" \
  || { echo "collect-evidence: not inside a git repository" >&2; exit 2; }
cd "$ROOT" || exit 2

REVIEWS="$RUN_DIR/reviews"
mkdir -p "$REVIEWS"

# ------------------------------------------------------------- worker logs
# The per-session logs under .claude/orchestration-logs/ are the only record of
# what each dispatched worker actually did, and they are gitignored where they
# are written — the same defect the run report had, fixed for the report and
# not for the logs feeding it (ESC-42). On the first unattended run every
# diagnosis — the frontmatter failure, the abandoned commit, the refused
# permissions — came from these files, and on a reclaimed web container all of
# it would have been gone. So they are copied beside the reviews, bounded to
# this run by --since where one is given.
WORKERS_SRC=".claude/orchestration-logs"
if [[ -d "$WORKERS_SRC" ]]; then
  WORKERS_DEST="$RUN_DIR/workers"
  # --since is RFC3339 (2026-08-18T22:26:21Z). `touch -t` takes CCYYMMDDhhmm.SS
  # and both are fixed-width UTC, so the conversion is character surgery — no
  # GNU date, per the portability rule the timestamp comparison below follows.
  MARKER=""
  if [[ "$SINCE" =~ ^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2}) ]]; then
    MARKER="$(mktemp)"
    TZ=UTC touch -t \
      "${BASH_REMATCH[1]}${BASH_REMATCH[2]}${BASH_REMATCH[3]}${BASH_REMATCH[4]}${BASH_REMATCH[5]}.${BASH_REMATCH[6]}" \
      "$MARKER" 2>/dev/null || { rm -f "$MARKER"; MARKER=""; }
  fi
  COPIED_LOGS=0
  while IFS= read -r logfile; do
    [[ -n "$logfile" ]] || continue
    mkdir -p "$WORKERS_DEST"
    cp "$logfile" "$WORKERS_DEST/" 2>/dev/null && COPIED_LOGS=$((COPIED_LOGS + 1))
  done < <(
    if [[ -n "$MARKER" ]]; then
      find "$WORKERS_SRC" -maxdepth 1 -name '*.log' -newer "$MARKER" 2>/dev/null
    else
      find "$WORKERS_SRC" -maxdepth 1 -name '*.log' 2>/dev/null
    fi
  )
  [[ -n "$MARKER" ]] && rm -f "$MARKER"
  echo "collect-evidence: $COPIED_LOGS worker log(s) into ${WORKERS_DEST}."
fi

if ! command -v "$GH" >/dev/null 2>&1; then
  echo "collect-evidence: '$GH' is not on PATH — no review evidence collected."
  exit 0
fi

# Completed runs of the review workflow, newest first. `--json` rather than
# scraping the table: the columns move between gh releases and a recorder that
# silently records nothing is the failure this script exists to fix.
# TSV through gh's own --jq rather than a JSON parse here: this repository is
# bash, and adding a python dependency to a recorder would be a new way for the
# recorder to be absent.
RUNS="$("$GH" run list --workflow "$WORKFLOW" --limit "$LIMIT" \
        --json databaseId,createdAt,headSha,headBranch,conclusion,status \
        --jq '.[] | [.databaseId, .createdAt, .headSha, .headBranch, .conclusion, .status] | @tsv' \
        2>/dev/null || true)"
if [[ -z "$RUNS" ]]; then
  echo "collect-evidence: no runs of $WORKFLOW to collect."
  exit 0
fi

COLLECTED=0
SKIPPED=0
INDEX="$REVIEWS/index.md"
{
  echo "# Review evidence — $(basename "$RUN_DIR")"
  echo
  echo "One directory per review the gate performed during this run. Each holds"
  echo "\`payload.txt\` (exactly what the reviewer was shown), \`reply.txt\`"
  echo "(exactly what it said), \`verdict.txt\` and \`meta.txt\`."
  echo
  echo "These are kept because the review gate is the only load-bearing gate"
  echo "with no fixtures, and it was also the only one that left no trace to"
  echo "build fixtures from."
  echo
  echo "| Branch | Commit | Verdict | Directory |"
  echo "| --- | --- | --- | --- |"
} > "$INDEX"

# Lane scoping (ESC-54). Review runs are listed REPO-WIDE, but a run
# directory belongs to ONE run: on a twin-run repository, collecting without
# a filter imports the other lane's review payloads into this lane's
# evidence — observed live, from the machinery rather than a roaming worker.
# The driver's convention is the filter: branches pushed for a non-default
# base carry the `--<sanitized base>` suffix, so a lane keeps only its own
# suffix, and the default lane skips anything carrying one.
DEFAULT_BRANCH="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')"
LANE_SUFFIX=""
if [[ -n "${RUN_BASE:-}" && "$RUN_BASE" != "$DEFAULT_BRANCH" ]]; then
  LANE_SUFFIX="--$(printf '%s' "$RUN_BASE" | tr -c 'A-Za-z0-9._-' '-')"
fi

while IFS=$'\t' read -r id created sha branch conclusion status; do
  [[ -z "$id" ]] && continue
  [[ "$status" == "completed" ]] || { SKIPPED=$((SKIPPED + 1)); continue; }
  if [[ -n "$LANE_SUFFIX" ]]; then
    [[ "$branch" == *"$LANE_SUFFIX" ]] || { SKIPPED=$((SKIPPED + 1)); continue; }
  elif [[ "$branch" =~ --[A-Za-z0-9._-]+$ ]]; then
    # Carries some lane's suffix, and this run is the default lane's.
    SKIPPED=$((SKIPPED + 1)); continue
  fi
  # String comparison on RFC3339 timestamps is a real ordering as long as both
  # are UTC with the same shape, which is what the GitHub API returns and what
  # the driver passes. No date arithmetic, so nothing depends on GNU date.
  if [[ -n "$SINCE" && "$created" < "$SINCE" ]]; then continue; fi

  dest="$REVIEWS/${branch//\//-}-${sha:0:12}"
  if [[ -d "$dest" ]]; then continue; fi
  mkdir -p "$dest"
  if ! "$GH" run download "$id" --dir "$dest" >/dev/null 2>&1; then
    # An expired or artifact-less run. Record that it happened rather than
    # leaving a silent gap — "no evidence" and "no run" look identical
    # otherwise, and only one of them is a problem.
    {
      echo "# No artifact for review run $id"
      echo
      echo "branch:     $branch"
      echo "commit:     $sha"
      echo "created:    $created"
      echo "conclusion: ${conclusion:-unknown}"
      echo
      echo "The run happened; its artifact could not be downloaded (expired,"
      echo "never uploaded, or the job died before the upload step). This file"
      echo "exists so the gap is visible rather than indistinguishable from"
      echo "a review that never ran."
    } > "$dest/MISSING.md"
    SKIPPED=$((SKIPPED + 1))
  fi

  # gh puts each artifact in its own subdirectory; flatten the single expected
  # one so the paths in index.md are the paths that exist.
  inner="$(find "$dest" -mindepth 2 -maxdepth 2 -name 'verdict.txt' -printf '%h\n' 2>/dev/null | head -1)"
  if [[ -n "$inner" ]]; then
    mv "$inner"/* "$dest"/ 2>/dev/null || true
    rmdir "$inner" 2>/dev/null || true
  fi

  verdict="$(cat "$dest/verdict.txt" 2>/dev/null || echo "${conclusion:-unknown}")"
  printf '| `%s` | `%s` | %s | [`%s`](%s) |\n' \
    "$branch" "${sha:0:12}" "$verdict" "$(basename "$dest")" "$(basename "$dest")" >> "$INDEX"
  COLLECTED=$((COLLECTED + 1))
done <<<"$RUNS"

{
  echo
  echo "Collected $COLLECTED review(s); $SKIPPED skipped or unavailable."
} >> "$INDEX"

echo "collect-evidence: $COLLECTED review(s) into $REVIEWS ($SKIPPED skipped)."
exit 0
