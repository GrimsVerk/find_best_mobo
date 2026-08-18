#!/usr/bin/env bash
#
# setup-github.sh — turn the README's manual GitHub setup into one run.
#
#     scripts/setup-github.sh [options]
#
# Plain shell on purpose, next to update-from-template.sh and for the same
# reason: setup is needed regardless of which agent or editor you use, so it
# does not live under .claude/ and depends on nothing vendor-specific.
#
# WHAT IT DOES, idempotently — every step reads before it writes, so re-running
# after a partial failure finishes the job instead of duplicating it:
#
#   1. creates the GitHub repository if this project has no origin, and pushes;
#   2. sets the merge settings (allow auto-merge, allow merge commits, delete
#      branches on merge);
#   3. sets the secrets that are missing, prompting for each value silently —
#      a value never appears in an argument list, a log, or an echo;
#   4. creates (or updates) the `grimsverk-gates` ruleset: active on the
#      default branch, deletions and force-pushes blocked, pull request
#      required with 0 approvals plus Code Owners review, and the required
#      status checks for this project's language. Deliberately NOT "require
#      linear history" — it blocks merge commits, which breaks the one-line
#      `git revert -m 1` rollback the whole auto-merge design leans on.
#
# WHAT STAYS MANUAL, and each for a security reason rather than a missing
# feature:
#
#   - typing the secret VALUES. This script never fetches or stores a
#     credential; `claude setup-token` is an interactive OAuth flow, and the
#     two PATs are minted by a human in the GitHub UI because token minting is
#     a credential decision no script should make;
#   - creating the GitHub App (--app prints the exact URL and permission list;
#     the creation form itself is a click-through GitHub offers no API for);
#   - `gh auth login`'s browser grant;
#   - the choice between GitHub Pro and a public repository (see the README:
#     every gate depends on rulesets, which are Pro-only for private repos).
#
# UNVERIFIED, honestly: the ruleset is created through the REST API, which —
# unlike the UI dropdown — accepts a check context that has not reported yet.
# That claim held in documentation and has not yet been observed on a live
# repository; if a required check sits "expected" forever on your first pull
# request, run with --verify, which opens a throwaway pull request so every
# check reports once, then closes it.
#
# Options:
#   --app              also configure the GitHub App identity (APP_ID +
#                      APP_PRIVATE_KEY secrets); see the DECISIONS.md entry on
#                      why the App beats a PAT for unattended runs
#   --ssh-host <host>  after creating the repo, rewrite origin to this SSH host
#                      alias (e.g. github.com-yourname) — required when your
#                      key lives on a host alias, since the plain host has no
#                      key attached and every push fails
#   --public           create the repository public instead of private
#   --verify           open (and then close) a throwaway pull request so every
#                      PR-only check reports once and is registered in the UI
#   --skip-create      never create or push; only configure the existing repo

set -euo pipefail

APP=0; SSH_HOST=""; VISIBILITY="--private"; VERIFY=0; SKIP_CREATE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --app)         APP=1; shift ;;
    --ssh-host)    SSH_HOST="${2:-}"; shift 2 ;;
    --public)      VISIBILITY="--public"; shift ;;
    --verify)      VERIFY=1; shift ;;
    --skip-create) SKIP_CREATE=1; shift ;;
    -h|--help)
      sed -n '2,60p' "$0" | sed -n 's/^# \{0,1\}//p'
      exit 0 ;;
    *) echo "setup-github: unknown argument: $1" >&2; exit 2 ;;
  esac
done

die() { echo "setup-github: $*" >&2; exit 1; }
say() { echo "setup-github: $*"; }

GH="${GH:-gh}"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || die "not inside a git repository"
cd "$ROOT"

command -v "$GH" >/dev/null 2>&1 || die "the GitHub CLI is not installed (https://cli.github.com)"
"$GH" auth status >/dev/null 2>&1 || die "gh is not authenticated — run: gh auth login"

ANSWERS="${ANSWERS:-.copier-answers.yml}"
[[ -f "$ANSWERS" ]] || die "no $ANSWERS here — this is not a generated project"
LANGUAGE="$(sed -n 's/^language:[[:space:]]*//p' "$ANSWERS" | tr -d "\"'" | head -1)"
case "$LANGUAGE" in
  python)    BUILD_CHECK="checks" ;;
  swift-ios) BUILD_CHECK="test" ;;
  *) die "language '$LANGUAGE' in $ANSWERS is not one this script knows a build check for" ;;
esac

# ------------------------------------------------------------- 1. repository
if git remote get-url origin >/dev/null 2>&1; then
  say "origin exists; not creating a repository."
elif [[ "$SKIP_CREATE" -eq 1 ]]; then
  die "--skip-create, but this repository has no origin to configure"
else
  NAME="$(basename "$ROOT")"
  OWNER="$("$GH" api user --jq .login)"
  say "creating $OWNER/$NAME $VISIBILITY ..."
  # NOT --remote=origin --push: that pushes against the keyless plain host in
  # the same breath, failing with no opportunity to correct the URL first.
  "$GH" repo create "$OWNER/$NAME" "$VISIBILITY" --source=.
  if [[ -n "$SSH_HOST" ]]; then
    git remote set-url origin "git@${SSH_HOST}:${OWNER}/${NAME}.git"
    say "origin rewritten to git@${SSH_HOST}:${OWNER}/${NAME}.git"
  fi
  git push -u origin "$(git branch --show-current)"
fi

REPO="$("$GH" repo view --json nameWithOwner --jq .nameWithOwner)"
[[ -n "$REPO" ]] || die "cannot resolve the repository from origin"
say "configuring $REPO"

# ---------------------------------------------------------- 2. merge settings
# allow_merge_commit is asserted, not assumed: merge commits are what make the
# one-line revert rollback work, and an org policy can have turned them off.
"$GH" api -X PATCH "repos/$REPO" \
  -F allow_auto_merge=true \
  -F allow_merge_commit=true \
  -F delete_branch_on_merge=true >/dev/null
say "merge settings: auto-merge on, merge commits on, delete-on-merge on."

# ---------------------------------------------------------------- 3. secrets
# Values are read silently and piped straight to `gh secret set` over stdin.
# printf is a shell builtin, so the value never appears in any process's
# argument list; nothing here echoes it, and set -x is not on.
have_secret() { "$GH" secret list 2>/dev/null | awk '{print $1}' | grep -qxF "$1"; }

prompt_secret() { # prompt_secret <name> <how to get the value>
  local name="$1" how="$2" value
  if have_secret "$name"; then
    say "secret $name: already set, leaving it alone."
    return 0
  fi
  echo
  echo "  $name is not set. $how"
  read -rsp "  Paste the value for $name (input hidden; empty to skip): " value
  echo
  if [[ -z "$value" ]]; then
    say "secret $name: skipped."
    return 0
  fi
  printf '%s' "$value" | "$GH" secret set "$name"
  say "secret $name: set."
}

prompt_secret CLAUDE_CODE_OAUTH_TOKEN \
  "It drives the review gate, which FAILS CLOSED without it. Get it by running: claude setup-token"
prompt_secret TEMPLATE_TOKEN \
  "A fine-grained PAT with Contents: Read-only on the TEMPLATE repository; template-sync fails closed without it when the template is private."

if [[ "$APP" -eq 1 ]]; then
  echo
  cat <<'APPHOWTO'
  GitHub App identity — the login the unattended driver opens pull requests
  as. Without it the driver opens them as YOU, and owner-authored.sh then
  compares your login to your login and passes, so docs/DESIGN.md and
  docs/VISION.md are unprotected overnight. See docs/DECISIONS.md.

  Create the App ONCE per account at

      https://github.com/settings/apps/new

    - GitHub App name .... anything unique
    - Homepage URL ....... this repository's URL is fine; nothing reads it
    - Webhook -> Active .. UNCHECK
    - Repository permissions:
        Contents ......... Read and write
        Pull requests .... Read and write
    - Where installed .... Only on this account

  Then, on the App's page: note the App ID (a number, NOT the Client ID),
  press "Generate a private key" (a .pem downloads), and press
  "Install App" -> install it on this repository. Then continue here.
APPHOWTO
  if have_secret APP_ID && have_secret APP_PRIVATE_KEY; then
    say "App secrets already set, leaving them alone."
  else
    read -rp "  App ID (empty to skip): " app_id
    if [[ -n "$app_id" ]]; then
      read -rp "  Path to the downloaded .pem private key: " pem_path
      [[ -f "$pem_path" ]] || die "no file at $pem_path"
      printf '%s' "$app_id" | "$GH" secret set APP_ID
      "$GH" secret set APP_PRIVATE_KEY < "$pem_path"

      # THE SECOND HOME, and the reason this is not a manual step. The secrets
      # above are readable only from inside Actions, which is what auto-merge
      # needs. The DRIVER runs on this machine, where repository secrets do not
      # exist, so .claude/scripts/app-token.sh reads the same two values from a
      # local file. Setting one and not the other is the failure this whole
      # block exists to prevent: the App looks configured, and every unattended
      # run still refuses.
      #
      # An earlier version of this script ended by suggesting `rm` on the .pem.
      # That advice predates the driver and was actively wrong — the path below
      # is read on every run, so deleting the key breaks the identity it just
      # finished setting up.
      abs_pem="$(cd "$(dirname "$pem_path")" && pwd)/$(basename "$pem_path")"
      mkdir -p .claude
      if [[ -f .claude/app-identity ]]; then
        say "'.claude/app-identity' already exists — leaving it alone. Check that it reads:"
        say "  APP_ID=$app_id"
        say "  APP_PRIVATE_KEY=$abs_pem"
      else
        cat > .claude/app-identity <<IDENTITY
# Written by scripts/setup-github.sh --app. Gitignored, and local to this
# machine. Read by .claude/scripts/app-token.sh on every unattended run.
APP_ID=$app_id
APP_PRIVATE_KEY=$abs_pem
IDENTITY
        chmod 600 .claude/app-identity
        say "Wrote .claude/app-identity (gitignored) — the driver's half of the identity."
      fi

      say ""
      say "KEEP the private key at $abs_pem. It is read on every run."
      say "It is a credential: keep it OUTSIDE any repository (~/.config/grimsverk/"
      say "is a good home), and chmod 600 it. Verify the whole thing with:"
      say "  .claude/scripts/app-token.sh >/dev/null && echo 'App identity OK'"
    else
      say "App identity skipped — unattended runs will refuse until it is set up."
    fi
  fi
else
  prompt_secret AUTO_MERGE_TOKEN \
    "(optional) A fine-grained PAT scoped to THIS repository with pull-requests:write and contents:write; without any merge identity, branch cleanup waits for the nightly sweep. Prefer --app."
fi

# ---------------------------------------------------------------- 4. ruleset
# One ruleset, targeting the default branch by pointer (~DEFAULT_BRANCH) so it
# survives a rename. The REST API accepts contexts that have not reported yet
# (see the header's UNVERIFIED note). Update-in-place if it already exists:
# POSTing a duplicate name creates a second ruleset, and two rulesets' rules
# UNION, which is how a stale one quietly keeps an old check required forever.
RULESET_NAME="grimsverk-gates"
RULESET_JSON="$(cat <<JSON
{
  "name": "$RULESET_NAME",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "require_code_owner_review": true,
        "dismiss_stale_reviews_on_push": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false
      } },
    { "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [
          { "context": "$BUILD_CHECK" },
          { "context": "secrets" },
          { "context": "plan" },
          { "context": "template-sync" },
          { "context": "test-the-tests" },
          { "context": "acceptance-criteria" },
          { "context": "review" }
        ]
      } }
  ]
}
JSON
)"

EXISTING_ID="$("$GH" api "repos/$REPO/rulesets" \
  --jq ".[] | select(.name == \"$RULESET_NAME\") | .id" 2>/dev/null | head -1)"
if [[ -n "$EXISTING_ID" ]]; then
  printf '%s' "$RULESET_JSON" | "$GH" api -X PUT "repos/$REPO/rulesets/$EXISTING_ID" --input - >/dev/null
  say "ruleset '$RULESET_NAME': updated in place (id $EXISTING_ID)."
else
  printf '%s' "$RULESET_JSON" | "$GH" api -X POST "repos/$REPO/rulesets" --input - >/dev/null
  say "ruleset '$RULESET_NAME': created."
fi
say "required checks: $BUILD_CHECK secrets plan template-sync test-the-tests acceptance-criteria review"

# ----------------------------------------------------------------- 5. verify
if [[ "$VERIFY" -eq 1 ]]; then
  # The chore/ prefix exempts the branch from the plan check, which would
  # otherwise fail an empty commit that has no plan. Closing rather than
  # merging: the point is registration, not a commit on main.
  say "opening a throwaway pull request so every PR-only check reports once ..."
  BRANCH="chore/register-checks-$$"
  git checkout -q -b "$BRANCH"
  git commit -q --allow-empty -m "Register the pull-request checks"
  git push -q -u origin "$BRANCH"
  PR_URL="$("$GH" pr create --title "Register the pull-request checks" \
    --body "Throwaway: registers the PR-only checks so they can be required. Close after checks report." )"
  say "watching $PR_URL — this takes as long as your CI does."
  "$GH" pr checks "$BRANCH" --watch --interval 30 || true
  "$GH" pr close "$BRANCH" --delete-branch
  git checkout -q -
  say "throwaway pull request closed; every check has now reported once."
fi

echo
say "done. Read it back before trusting it:"
say "  .github/scripts/unattended-ready.sh"
