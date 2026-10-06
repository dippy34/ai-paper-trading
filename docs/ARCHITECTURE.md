# 🛠️ How it works

```
             every weekday 10:17 AM ET (same cron, two Routines)
                 │                                   │
                 ▼                                   ▼
   ┌───────────────────────────┐       ┌───────────────────────────┐
   │ 🚀 Rocket's Claude session │       │ 🐢 Turtle's Claude session │
   │  own chat, own memory      │       │  own chat, own memory      │
   │  web search for research   │       │  web search for research   │
   └─────────────┬─────────────┘       └─────────────┬─────────────┘
                 │ python3 -m trader … --bot risky     │ … --bot safe
                 ▼                                     ▼
   ┌───────────────────────────────────────────────────────────────┐
   │ trader/ (paper broker): Yahoo prices · fills · limits · P&L    │
   └─────────────┬─────────────────────────────────────┬───────────┘
                 │ git push                              │ git push
                 ▼                                       ▼
        branch bot-risky                         branch bot-safe
        bots/risky/…                             bots/safe/…
                 ▲                                       ▲
                 │  🔔 Scorekeeper (GitHub Action, no AI) │
                 └──── weekday after the close: marks ────┘
                       both books at closing prices
                 │                                       │
                 └──────────────┬────────────────────────┘
                                ▼  (read in the browser)
            🌐 Dashboard: GitHub Pages, served from the code branch
               index.html + assets/ + docs; bot data from both branches
```

## The pieces

| Piece | Where | What it does |
|---|---|---|
| **Traders** | two Claude Code cloud sessions | One persistent session per bot. Its extra system prompt ([Rocket](../prompts/risky-system.md), [Turtle](../prompts/safe-system.md)) sets identity and isolation; [the routine](ROUTINE.md) says what to do each day. |
| **Alarm clock** | two Claude Code *Routines* (scheduled triggers) | Identical cron `CRON_TZ=America/New_York 17 10 * * 1-5`. Each fires [a wake-up message](../prompts/wake-up.md) into its own trader's session. |
| **Paper broker** | [`trader/`](../trader/engine.py) | Pure Python standard library. Prices from Yahoo Finance's chart API. Validates orders against the rules, fills them, tracks cash, positions, average cost and realized P&L, records snapshots and journals. |
| **Git glue** | [`scripts/wake.sh`](../scripts/wake.sh), [`scripts/sleep.sh`](../scripts/sleep.sh) | Wake: switch to your own branch, pull, merge the latest shared code, fill in any missing closing scores (below), print the desk. Sleep: snapshot, commit only `bots/<bot>/`, push with retries. |
| **Scorekeeper** | [`.github/workflows/scorekeeper.yml`](../.github/workflows/scorekeeper.yml) | Weekdays after the 4 PM ET close (21:15 UTC, with backup runs at 22:20 and 23:40 UTC): checks out each bot branch, records a `close` snapshot, pushes. Skips holidays. These are the official daily scores. |
| **Closing-score backfill** | `python3 -m trader backfill`, run by `wake.sh` | GitHub's scheduler can run late or skip jobs, so every morning each bot also records any missing `close` snapshots for past trading days, using Yahoo's official daily closing prices. A book only changes during its own routine, so yesterday's closing book is today's book at yesterday's closes, the same number the scorekeeper would have recorded. These snapshots are marked `"source": "backfill"`. |
| **Tests** | [`tests/`](../tests/test_engine.py), [`.github/workflows/tests.yml`](../.github/workflows/tests.yml) | Offline unit tests for fills, limits, shorts, leverage, bankruptcy and journaling. |
| **Dashboard** | [`index.html`](../index.html), [`assets/`](../assets/app.js) | Static site, no build step. Loads `config.json` and the docs from itself, and each bot's data from `raw.githubusercontent.com/<repo>/refs/heads/<bot branch>/bots/<bot>/…`. Refreshes every 5 minutes. |

## Branches

| Branch | Contains | Written by |
|---|---|---|
| `claude/intelligent-fermi-jjukha` (the default/code branch) | code, docs, dashboard, config. **No bot data, ever.** | humans and Claude |
| `bot-risky` | the code (merged in daily) plus `bots/risky/` | 🚀 Rocket and the scorekeeper |
| `bot-safe` | the code (merged in daily) plus `bots/safe/` | 🐢 Turtle and the scorekeeper |

Each bot branch is created by that bot on its first wake-up. Because bot data never lands on the
code branch, merging the code branch into a bot branch can't leak anything from the other bot.

## A day in the life

| Time (ET) | What happens |
|---|---|
| 9:30 AM | Opening bell |
| **10:17 AM** | Both Routines fire. Each trader wakes, reads its memory, researches, trades, journals, updates memory and pushes. The engine records a `morning` snapshot. |
| 4:00 PM | Closing bell |
| ~4:15 to 8 PM | 🔔 Scorekeeper Action records each bot's `close` snapshot. It runs up to three times as a safety net, since GitHub sometimes delays or skips scheduled jobs. If it never runs, the next morning's wake-up backfills that day's close. |
| any time | The dashboard picks up new commits within about 5 minutes. |

See [Data formats](DATA.md) for what's in each file and [Operations](OPERATIONS.md) for running it.
