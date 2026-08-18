#!/usr/bin/env bash
#
# budget-probe.sh — read subscription utilization, in percentage points.
#
# Prints one line of key=value pairs and exits 0:
#
#     session=<n> week=<n> week_model=<n> reset=<string>
#
# `week` is the load-bearing one (the owner's ruling: the ceiling is a
# percentage of the WEEKLY limit). `session` is the 5-hour window, reported but
# never the ceiling — it resets mid-run, which makes a delta against it go
# negative. `week_model` is the per-model weekly cap where one exists. `reset`
# is whatever the source says about when the weekly window rolls over; the
# driver snapshots it and throws a reading away if it changed, because a
# rollover mid-run makes every delta meaningless.
#
# WHAT WAS WRONG HERE, RECORDED BECAUSE IT SHIPPED LOOKING RIGHT. The previous
# version ran `claude usage --json`. There is no `usage` subcommand: `--json` is
# rejected as an unknown option, and bare `claude usage` treats the word as a
# prompt and opens a chat. So the probe could never succeed, and every run
# silently fell back to --max-prs and --max-hours. The one ceiling the owner
# actually specified was the one that did nothing, and the two they never chose
# were the only ones running. It was honestly flagged "unverified" in this
# header for weeks; it was not unverified, it was broken, and the difference is
# what a five-second test would have shown.
#
# THREE SOURCES, in precedence order:
#
#   1. BUDGET_PROBE_CMD — an owner-supplied command printing the line above (or
#      the older `session=<n> week=<n>` form). This is the good path on a
#      machine that has a real usage reader. On Omarchy that is
#      `omarchy-agent-usage-claude --limits-only --force`, which reads
#      Anthropic's endpoint directly: no session, no tokens, no cost.
#      --force matters — the reading is cached for 15 seconds, so two probes in
#      a row otherwise return an identical number and a short iteration looks
#      like zero spend.
#
#   2. `claude -p "/usage"` — works, and costs. It starts a small session to
#      answer, and the driver probes once per iteration, so a 20-iteration run
#      spends 21 sessions measuring spend. Used only when nothing better is
#      configured, and the driver says so at start.
#
#   3. Nothing. In a web session there is no local CLI and no usage endpoint
#      within reach, so this exits 3 and the driver ASKS the owner for explicit
#      limits instead of inventing one.
#
# A NOTE ON WHAT THESE NUMBERS ARE. They are account-wide, from Anthropic's
# side: work done on another machine, or on claude.ai, lands in the same total.
# That makes them wrong for "what did this run cost" and exactly right for "how
# much of my quota may this run spend", which is the question the ceiling is
# asking. For per-run cost, read the session transcript under
# ~/.claude/projects/ — the driver reports that separately and never stops on it.
#
# Exit codes:
#   0  a reading was printed
#   3  no usage source is reachable here

set -uo pipefail

emit() { # emit <session> <week> <week_model> <reset>
  printf 'session=%s week=%s week_model=%s reset=%s\n' \
    "${1:-0}" "${2:-0}" "${3:-${2:-0}}" "${4:-unknown}"
  exit 0
}

# ------------------------------------------------------------ 1. owner-supplied
if [[ -n "${BUDGET_PROBE_CMD:-}" ]]; then
  if ! out="$($BUDGET_PROBE_CMD 2>/dev/null)"; then
    echo "budget-probe: BUDGET_PROBE_CMD failed" >&2; exit 3
  fi
  # Accept the full form, the older two-field form, or raw JSON from a reader
  # like omarchy-agent-usage-claude --limits-only. Deliberately permissive: the
  # alternative is an owner whose working command is rejected on formatting.
  if grep -qE '(^|[[:space:]])week=[0-9]' <<<"$out"; then
    s="$(sed -n 's/.*\bsession=\([0-9.]*\).*/\1/p' <<<"$out" | head -1)"
    w="$(sed -n 's/.*\bweek=\([0-9.]*\).*/\1/p' <<<"$out" | head -1)"
    m="$(sed -n 's/.*\bweek_model=\([0-9.]*\).*/\1/p' <<<"$out" | head -1)"
    r="$(sed -n 's/.*\breset=\([^[:space:]]*\).*/\1/p' <<<"$out" | head -1)"
    emit "${s:-0}" "$w" "${m:-$w}" "${r:-unknown}"
  fi
  if grep -q '"percent"' <<<"$out"; then
    # Labels vary ("Session (5-hour)", "Weekly (7-day)", "Fable Weekly"), so
    # match on the distinguishing word rather than the whole string — a reader
    # that renames its labels should degrade to a worse reading, not to none.
    pick() { # pick <regex over the label>
      tr -d '\n' <<<"$out" \
        | grep -oE '\{[^{}]*"label"[[:space:]]*:[[:space:]]*"[^"]*'"$1"'[^"]*"[^{}]*\}' \
        | grep -oE '"percent"[[:space:]]*:[[:space:]]*[0-9.]+' \
        | grep -oE '[0-9.]+$' | head -1
    }
    as_points() { awk -v v="${1:-}" 'BEGIN{ if (v=="") { print "" } else { print (v <= 1 ? v * 100 : v) } }'; }
    s="$(as_points "$(pick '[Ss]ession')")"
    w="$(as_points "$(pick '[Ww]eek')")"
    # The per-model weekly cap is a SECOND "week"-labelled entry; take the last.
    m="$(as_points "$(tr -d '\n' <<<"$out" \
        | grep -oE '\{[^{}]*"label"[^{}]*[Ww]eek[^{}]*\}' \
        | grep -oE '"percent"[[:space:]]*:[[:space:]]*[0-9.]+' \
        | grep -oE '[0-9.]+$' | tail -1)")"
    r="$(tr -d '\n' <<<"$out" | sed -n 's/.*"resets\?_\?[Aa]t"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)"
    [[ -n "$w" ]] && emit "${s:-0}" "$w" "${m:-$w}" "${r:-unknown}"
  fi
  echo "budget-probe: BUDGET_PROBE_CMD printed nothing this script could read" >&2
  exit 3
fi

# --------------------------------------------------------- 2. claude -p /usage
# Costs a small session per call. Correct but not free, which is why the owner
# is told to set BUDGET_PROBE_CMD when a free reader exists.
if command -v claude >/dev/null 2>&1 && [[ "${BUDGET_PROBE_ALLOW_SESSION:-1}" == "1" ]]; then
  out="$(timeout "${BUDGET_PROBE_TIMEOUT:-120}" claude -p "/usage" 2>/dev/null)" || out=""
  if [[ -n "$out" ]]; then
    # "Current session: 7% used · resets Aug 17, 9:19pm"
    # "Current week (all models): 29% used · resets Aug 20, 10:59am"
    # "Current week (Fable): 25% used · resets Aug 20, 10:59am"
    s="$(sed -n 's/.*[Cc]urrent session[^0-9]*\([0-9.]\+\)%.*/\1/p' <<<"$out" | head -1)"
    w="$(sed -n 's/.*[Cc]urrent week (all models)[^0-9]*\([0-9.]\+\)%.*/\1/p' <<<"$out" | head -1)"
    [[ -n "$w" ]] || w="$(sed -n 's/.*[Cc]urrent week[^0-9]*\([0-9.]\+\)%.*/\1/p' <<<"$out" | head -1)"
    m="$(sed -n 's/.*[Cc]urrent week ([^)]*)[^0-9]*\([0-9.]\+\)%.*/\1/p' <<<"$out" | tail -1)"
    r="$(sed -n 's/.*[Cc]urrent week (all models).*resets \(.*\)$/\1/p' <<<"$out" | head -1)"
    [[ -n "$w" ]] && emit "${s:-0}" "$w" "${m:-$w}" "${r:-unknown}"
  fi
fi

# ------------------------------------------------------------ 3. nothing here
cat >&2 <<'MSG'
budget-probe: no usage source is reachable here.

This is expected in a Claude Code web session: there is no local CLI to ask and
no usage endpoint in reach. The driver will ask you for explicit limits instead
of inventing one — that is the design, not a degradation.

On a machine with a usage reader, point BUDGET_PROBE_CMD at it and the
percentage ceiling works again. It must print either

    session=<n> week=<n> week_model=<n> reset=<anything>

or the JSON a limits reader emits. On Omarchy:

    BUDGET_PROBE_CMD='omarchy-agent-usage-claude --limits-only --force'

(--force matters: the reading is cached for 15 seconds, so without it two
probes in a row return the same number and a short iteration reads as zero.)
MSG
exit 3
