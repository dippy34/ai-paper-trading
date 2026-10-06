# 🧰 Operations & setup

## One-time setup: turn on the website

The dashboard is served by GitHub Pages straight from the code branch, so there's no build step.

1. On GitHub open **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to **Deploy from a branch**.
3. Pick the branch **`claude/intelligent-fermi-jjukha`** and the folder **`/ (root)`**, then **Save**.
4. After a minute or two the site is live at **https://dippy34.github.io/ai-paper-trading/**.

Bot data is read live from the bot branches, so the site updates by itself within about 5
minutes of every push. You don't need to re-deploy.

## What's running

<!-- live-setup:start -->
| What | Where |
|---|---|
| 🚀 Rocket's session | [claude.ai/code/session_01U9zbeWfan3sEEZTWSPqUV8](https://claude.ai/code/session_01U9zbeWfan3sEEZTWSPqUV8) (model: Claude Sonnet 5.5) |
| 🐢 Turtle's session | [claude.ai/code/session_0189dsoghfKJ16fM8GKZyeNj](https://claude.ai/code/session_0189dsoghfKJ16fM8GKZyeNj) (model: Claude Sonnet 5.5) |
| ⏰ Rocket's Routine | `trig_015FPdvK83NpbYveGBJQx9YR`: `CRON_TZ=America/New_York 17 10 * * 1-5` → Rocket's session |
| ⏰ Turtle's Routine | `trig_012zh4M41qugfzxPL4XYLRci`: `CRON_TZ=America/New_York 17 10 * * 1-5` → Turtle's session |
| 🔔 Scorekeeper | GitHub Action [`scorekeeper.yml`](../.github/workflows/scorekeeper.yml), weekdays 21:15 UTC (backups 22:20 and 23:40 UTC) |

Both traders run the same model so the comparison is fair, and each has its own persistent
session (its own memory of past days). The Routines live in your claude.ai account under **Routines**.
<!-- live-setup:end -->

Each wake-up is a normal Claude Code session turn, so it counts toward your Claude plan's usage
like any other session.

## Checking on the bots

- **Dashboard:** the scoreboard and journals tell you if a bot ran today.
- **Watch them think:** open a trader's session on claude.ai/code. Each daily run is one turn in
  that conversation, so you can read its research and reasoning.
- **Raw data:** browse the `bot-risky` and `bot-safe` branches on GitHub.
- **Scorekeeper runs:** the repo's **Actions** tab, workflow *Scorekeeper (closing bell)*.

## Common tasks

| I want to… | Do this |
|---|---|
| Pause a bot | Disable its Routine on claude.ai (Routines list) or ask Claude to disable it. Its book stays as-is. |
| Make a bot run right now | Use **Run now** on its Routine, or send its session a message like "Run your daily routine now." Orders only fill while the market is open. |
| Record a closing snapshot by hand | Actions → *Scorekeeper (closing bell)* → **Run workflow**. |
| Fix an engine bug mid-contest | Push the fix to the code branch. Each bot merges the latest code at its next wake-up (`scripts/wake.sh`). |
| Change the rules | Edit `config.json` on the code branch (limits, dates, slippage). Be fair: change both bots or neither. |
| See exactly what the AIs were told | [`prompts/`](../prompts/): system prompts, the orientation and the wake-up messages. |

## Troubleshooting

- **A bot didn't show up today.** Open its session and check the last turn. If it failed
  mid-routine, send "Run your daily routine now" while the market is open. The routine is safe
  to re-run: snapshots and journal entries for the same day update rather than duplicate.
- **No closing score on the evening itself.** GitHub sometimes runs scheduled jobs late or not
  at all. Nothing is lost: each bot's next wake-up backfills the missing close from Yahoo's
  official daily closes. You can also run the scorekeeper by hand from the Actions tab.
- **The scorekeeper can't push.** The workflow requests `contents: write`. If your account or
  organization blocks that, go to **Settings → Actions → General → Workflow permissions** and
  choose **Read and write permissions**.
- **The site says "asleep" after a wake-up.** The bot branch is created on the bot's first push,
  and raw GitHub files are cached for up to 5 minutes. Refresh in a few minutes.
- **Yahoo Finance is down.** Orders are rejected with a market-data error. Snapshots fall back
  to the last known prices and list the stale ones. Bots are told to note it in the journal
  and carry on.

## Ending the contest

The last trading day is **Thu Nov 5, 2026**. The engine refuses all orders after that date. The
bots wake once more on **Fri Nov 6** so `wake.sh` records the official Nov 5 closing score (if the
scorekeeper hasn't already) and they write a sign-off. After that, disable (or delete) the two
wake-up Routines. A follow-up check is scheduled to do this automatically on Nov 6.

## Developing locally

```bash
python3 -m unittest discover -s tests     # offline tests
python3 -m trader --help                  # CLI reference
python3 -m http.server 8000               # preview the dashboard (reads live bot branches)
```

To preview the dashboard with bot data from local files instead, copy a `bots/` folder next to
`index.html` and open `http://localhost:8000/?source=local`. Commands that write books refuse to
run unless you're on that bot's branch. Set `TRADER_HOME=/some/tmp/dir` (containing a copy of
`config.json`) to experiment safely.
