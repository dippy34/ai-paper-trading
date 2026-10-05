#!/usr/bin/env bash
# 😴 End-of-routine for one trader.
#   bash scripts/sleep.sh <risky|safe>
# Marks your book to market, commits ONLY your own folder, and pushes your branch.
set -uo pipefail
BOT="${1:?usage: bash scripts/sleep.sh <risky|safe>}"
cd "$(dirname "$0")/.."

BRANCH="$(python3 -m trader branch --bot "$BOT")" || exit 1
CURRENT="$(git rev-parse --abbrev-ref HEAD)"
if [ "$CURRENT" != "$BRANCH" ]; then
  echo "!! You're on '$CURRENT', not '$BRANCH'. Run: bash scripts/wake.sh $BOT"
  exit 1
fi

python3 -m trader snapshot --bot "$BOT" --label morning || echo "!! snapshot failed (market data?) - committing what we have"

git add -- "bots/$BOT"
if git diff --cached --quiet; then
  echo "Nothing new to commit."
else
  git commit -q -m "$(python3 -m trader summary --bot "$BOT" 2>/dev/null || echo "$BOT: daily routine")"
fi

for i in 1 2 3 4 5; do
  if git push -q -u origin "$BRANCH"; then
    echo "Pushed $BRANCH. Good night! 💤"
    exit 0
  fi
  echo "push failed (attempt $i), retrying..."
  git pull -q --rebase origin "$BRANCH" 2>/dev/null || git rebase --abort 2>/dev/null
  sleep $((2 ** i))
done
echo "!! Could not push $BRANCH after 5 tries. Your commit is saved locally; the next wake.sh will retry."
exit 1
