#!/usr/bin/env bash
# ⏰ Morning sync for one trader.
#   bash scripts/wake.sh <risky|safe>
# Gets you onto YOUR branch (and only yours), pulls in the latest shared code,
# then prints your desk. Safe to run more than once.
set -uo pipefail
BOT="${1:?usage: bash scripts/wake.sh <risky|safe>}"
cd "$(dirname "$0")/.."

BRANCH="$(python3 -m trader branch --bot "$BOT")" || exit 1
CODE_BRANCH="$(python3 -m trader config code_branch)" || exit 1

git config user.name  >/dev/null || git config user.name  "$BOT-trader"
git config user.email >/dev/null || git config user.email "$BOT-trader@users.noreply.github.com"

# Only ever fetch your own branch and the shared code branch.
REMOTE_HAS_BRANCH=0
git fetch -q origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH" 2>/dev/null && REMOTE_HAS_BRANCH=1
git fetch -q origin "+refs/heads/$CODE_BRANCH:refs/remotes/origin/$CODE_BRANCH" 2>/dev/null || true

# Park anything left over from an interrupted earlier run on the current branch.
CURRENT="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"
if [ "$CURRENT" = "$BRANCH" ] && [ -n "$(git status --porcelain -- "bots/$BOT")" ]; then
  git add -- "bots/$BOT" && git commit -q -m "$BOT: save leftovers from an interrupted run" || true
fi

if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git checkout -q "$BRANCH" || { echo "!! could not switch to $BRANCH (uncommitted changes?)"; git status --short; exit 1; }
  if [ "$REMOTE_HAS_BRANCH" = 1 ]; then
    git pull -q --rebase origin "$BRANCH" || { git rebase --abort 2>/dev/null; echo "!! pull failed; continuing with local copy"; }
  fi
elif [ "$REMOTE_HAS_BRANCH" = 1 ]; then
  git checkout -q -b "$BRANCH" "origin/$BRANCH"
else
  echo "First day on the job: creating branch $BRANCH from $CODE_BRANCH"
  git checkout -q -b "$BRANCH" "origin/$CODE_BRANCH" 2>/dev/null || git checkout -q -b "$BRANCH"
fi

# Pick up engine/doc fixes from the shared code branch (it never contains bot data).
if git show-ref --verify --quiet "refs/remotes/origin/$CODE_BRANCH"; then
  git merge -q --no-edit "origin/$CODE_BRANCH" -m "Merge latest shared code into $BRANCH" 2>/dev/null \
    || { git merge --abort 2>/dev/null; echo "!! could not merge latest code; continuing with current code"; }
fi

python3 -m trader init --bot "$BOT" >/dev/null || true

echo "On branch: $(git rev-parse --abbrev-ref HEAD)"
echo
python3 -m trader status --bot "$BOT"
