#!/usr/bin/env bash

set -u

# Color helpers (no-op if not a TTY)
if [ -t 1 ]; then
  RED=$(printf '\033[31m'); GREEN=$(printf '\033[32m'); BLUE=$(printf '\033[36m'); RESET=$(printf '\033[0m')
else
  RED=""; GREEN=""; BLUE=""; RESET=""
fi

step()  { printf "%s→ %s%s\n" "$BLUE" "$1" "$RESET"; }
ok()    { printf "  %s✓ %s%s\n" "$GREEN" "$1" "$RESET"; }
fail()  { printf "  %s✗ %s%s\n" "$RED" "$1" "$RESET"; exit_code=1; }

exit_code=0

# Move to repo root (script may be invoked from any cwd)
cd "$(dirname "$0")/.."

# ----------------------------------------------------------------------------
step "Verifying git repository is initialized"
if [ ! -d ".git" ]; then
  printf "  %sNot a git repo — initialise with 'git init -b main' first.%s\n" "$RED" "$RESET"
  exit 1
fi
ok "git directory present"

# ----------------------------------------------------------------------------
step "Checking that no secret files are tracked by git"
TRACKED_SECRETS=$(git ls-files | grep -E '^(\.env|secrets/|.*\.pem$|.*\.key$|seed_credentials\.csv$)' || true)
if [ -n "$TRACKED_SECRETS" ]; then
  fail "The following sensitive files are tracked:"
  printf "%s\n" "$TRACKED_SECRETS" | sed 's/^/      /'
else
  ok "No tracked secrets"
fi

# ----------------------------------------------------------------------------
step "Searching for Claude / Anthropic / AI co-authorship traces"
# `git grep` only matches tracked files, so untracked stuff (.env, .git) is skipped.
AI_HITS=$(git grep -i -n -E 'claude|anthropic|co-authored-by:[[:space:]]*claude|generated[[:space:]]+(with|by)[[:space:]]+claude' \
  -- ':!.gitignore' ':!CHANGELOG.md' 2>/dev/null || true)
if [ -n "$AI_HITS" ]; then
  fail "AI references found:"
  printf "%s\n" "$AI_HITS" | sed 's/^/      /'
else
  ok "No AI traces"
fi

# ----------------------------------------------------------------------------
step "Searching for known real credentials"
# These are credentials seen during local development that should never appear
# in any committed file. Extend this list if you discover more.
KNOWN_CREDENTIALS=(
  "alex21fd@gmail.com"
  "dowpmcdhhgtvshbb"
  "Admin-Pwd-1!"
  "Prof-Pwd-1!"
)
CRED_HITS=""
for cred in "${KNOWN_CREDENTIALS[@]}"; do
  # Skip the script itself and the CHANGELOG (which may legitimately mention things).
  hits=$(git grep -n -F "$cred" \
    -- ':!scripts/pre_publish_check.sh' ':!tests' ':!apps/backend/tests' 2>/dev/null || true)
  if [ -n "$hits" ]; then
    CRED_HITS+="$hits\n"
  fi
done
if [ -n "$CRED_HITS" ]; then
  fail "Hardcoded credentials found:"
  printf "%b\n" "$CRED_HITS" | sed 's/^/      /'
else
  ok "No hardcoded credentials"
fi

# ----------------------------------------------------------------------------
step "Verifying .gitignore covers the basics"
REQUIRED_PATTERNS=(".env" "secrets/" "*.pem" "seed_credentials.csv")
MISSING=""
for pattern in "${REQUIRED_PATTERNS[@]}"; do
  if ! grep -qF "$pattern" .gitignore 2>/dev/null; then
    MISSING+="  - $pattern\n"
  fi
done
if [ -n "$MISSING" ]; then
  fail ".gitignore is missing entries:"
  printf "%b" "$MISSING"
else
  ok ".gitignore covers .env, secrets/, *.pem, seed_credentials.csv"
fi

# ----------------------------------------------------------------------------
step "Verifying LICENSE is present"
if [ -f "LICENSE" ]; then
  ok "LICENSE present"
else
  fail "LICENSE file is missing"
fi

# ----------------------------------------------------------------------------
echo ""
if [ $exit_code -eq 0 ]; then
  printf "%s✅ Repository is safe to push to a public remote.%s\n" "$GREEN" "$RESET"
else
  printf "%s❌ Pre-publish check failed. Fix the issues above before pushing.%s\n" "$RED" "$RESET"
fi

exit $exit_code
