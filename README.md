# 🚀 vs 🐢 AI Paper Trading Showdown

Two AI traders. One month. $100,000 of paper money each.

- **🚀 Rocket** trades **super risky**: leverage up to 2x, short selling, 3x ETFs, concentrated moonshots.
- **🐢 Turtle** trades **safe**: long only, no leverage, diversified, capital preservation first.

Every weekday at **10:17 AM New York time** both wake up **at the same moment**, run **the same
daily routine** (research → trade → journal → update memory), and go back to sleep. They
**can't exchange knowledge**: separate Claude sessions, separate memories, separate git branches.

### 🌐 Live dashboard: **https://dippy34.github.io/ai-paper-trading/**

The scoreboard, account-value chart against the S&P 500, open positions, every trade with its
reasoning, side-by-side daily journals, each bot's private memory, and all of these docs.

---

## The contest

| | |
|---|---|
| Dates | Mon **Oct 5** to Thu **Nov 5, 2026** (24 trading days) |
| Starting cash | $100,000 each (paper money) |
| Market | US stocks and ETFs, live prices from Yahoo Finance, 0.05% slippage |
| Wake-up | weekdays 10:17 AM ET, both at once (two Claude Code Routines) |
| Official score | closing-price mark every trading day by the 🔔 scorekeeper (a GitHub Action) |
| Winner | higher account value at the Nov 5 close |

| | 🚀 Rocket (risky) | 🐢 Turtle (safe) |
|---|---|---|
| Shorting | ✅ | ❌ |
| Leverage | up to 2.0x | none |
| Leveraged/inverse ETFs | ✅ | ❌ |
| Max per position | no cap | 25% |

## Documentation

| Doc | What's inside |
|---|---|
| [Competition rules](docs/RULES.md) | Exact rules, limits, leverage math, isolation |
| [Daily routine](docs/ROUTINE.md) | The step-by-step routine both AIs follow every morning |
| [🚀 Rocket's persona](personas/risky.md) · [🐢 Turtle's persona](personas/safe.md) | Personality, strategy, house rules |
| [How it works](docs/ARCHITECTURE.md) | Sessions, Routines, the paper broker, branches, scorekeeper, dashboard |
| [Data formats](docs/DATA.md) | What's in `portfolio.json`, `trades.json`, `equity.json`, journals |
| [Operations & setup](docs/OPERATIONS.md) | Turning on the website, checking on the bots, pausing, troubleshooting |
| [Prompts](prompts/) | The exact system prompts, orientation and wake-up messages the AIs receive |

## Where the data lives

The traders' books are on their own branches, so neither ever has the other's data on disk:

- 🚀 [`bot-risky` → `bots/risky/`](https://github.com/dippy34/ai-paper-trading/tree/bot-risky/bots/risky)
- 🐢 [`bot-safe` → `bots/safe/`](https://github.com/dippy34/ai-paper-trading/tree/bot-safe/bots/safe)

(These branches appear after each bot's first wake-up.)

## For humans poking at the code

```bash
python3 -m unittest discover -s tests       # offline tests, no network needed
python3 -m trader quote NVDA SPY            # live quotes with momentum stats
python3 -m trader --help                    # everything the bots can do
python3 -m http.server 8000                 # preview the dashboard at http://localhost:8000
```

No dependencies: Python 3.10+ standard library only. The dashboard is static HTML/CSS/JS.

*Paper trading only. Nothing here is investment advice, and no real money is involved.*
