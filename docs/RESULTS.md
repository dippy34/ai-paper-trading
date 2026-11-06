# 🏆 Final results

**🐢 Turtle wins.** After 24 trading days (Mon Oct 5 to Thu Nov 5, 2026), the safe trader
finished up and the risky one finished down more than a fifth. The S&P 500 fell about 5% over
the same stretch, so slow and steady beat both the rocket and the index.

| Official score at the Nov 5 close | Account value | Return | vs S&P 500 |
|---|---|---|---|
| 🐢 **Turtle** (safe) | **$101,108.11** | **+1.11%** | **+6.2 points** |
| S&P 500 (SPY), $100k bought at the first snapshot | $94,902.70 | −5.10% | |
| 🚀 Rocket (risky) | $77,969.83 | −22.03% | −16.9 points |

Turtle wins by **$23,138.28**. Both final scores were recorded live by the
[scorekeeper](ARCHITECTURE.md#the-pieces) after the Nov 5 close. SPY went from $772.37 at the
first snapshot (Oct 5, after the morning trades) to $733.00 at the final close.

## Scorecard

| | 🚀 Rocket | 🐢 Turtle |
|---|---|---|
| Final value | $77,969.83 | $101,108.11 |
| Peak | $104,611.34 (Oct 6, morning) | $102,594.24 (Nov 4 close) |
| Max drawdown from peak | **−25.5%** | **−1.4%** |
| Best day (close to close) | +2.84% (Nov 4) | +1.33% (Nov 4) |
| Worst day | −7.66%, −$7,770 (Oct 8) | −1.45% (Nov 5) |
| Up closes | 10 of 24 | 17 of 24 |
| Highest leverage | 1.75x (cap 2.0x) | 0.91x invested (no borrowing allowed) |
| Trades | 17 (7 buys, 6 sells, 2 shorts, 2 covers) | 16 (13 buys, 3 sells) |
| Dollars traded | $679,674 | $113,957 |
| Positions closed at a profit | 0 of 8 | 0 of 3 |
| Realized P&L | −$14,855.60 | −$1,036.95 |
| Unrealized P&L at the end | −$7,174.56 | +$2,145.06 |
| Last trade | Oct 16 | Nov 5 |

Neither bot closed a single trade at a profit. Turtle won with what it *didn't* sell: its
defensive holdings were still up double digits at the bell.

## 🚀 Rocket: two acts and no encore

**Act 1, Oct 5 to 16: stock picking with leverage.** Day 1 put $160k to work at 1.6x leverage
across NVDA, AMD, SOXL (3x semiconductors) and TQQQ (3x Nasdaq), four positions that were really
one AI-and-chips bet. It peaked at **$104,611 (+4.6%)** on the morning of Oct 6. Then chips
cracked: **Oct 8 cost $7,770 (−7.7%) in one session** while the S&P slipped just 0.4%. Rocket
rotated into PLTR, XLE and shorts on MS and QQQ, and took a loss on every exit. The worst was
NVDA at **−$4,400**. By Oct 16 it was down to about $85k.

**Act 2, Oct 16 to Nov 5: one leveraged bet, no trades.** On Oct 16 Rocket closed everything and
bought **$144,000 of SPY at about 1.7x**, then held it for the last 15 sessions without trading
again. The S&P slid 5% from its entry, and at 1.7x that cost the account roughly 8½% more
(−$7,175 on the position). It never came close to the engine's bankruptcy line.

> "My instinct is to *do something* every morning, and that instinct cost me most of my losses."
> 🚀 Rocket, final reflection

## 🐢 Turtle: boring, on purpose

Turtle spent day 1 buying in small pieces: S&P 500 (VOO), T-bills (SGOV), Berkshire (BRK-B),
healthcare (XLV), Procter & Gamble (PG) and Coca-Cola (KO). It kept 20 to 35% in cash and T-bills
all month, and never had more than 91% of the account invested. With the Fed hiking and 10-year
yields near 24-year highs, the defensive picks did the work:

| Holding | Gain at the final close |
|---|---|
| PG | +14.9% (+$746) |
| BRK-B | +13.4% (+$805) |
| KO | +11.4% (+$457) |
| XLV | +11.1% (+$666) |
| XLF (added Oct 22) | +1.9% (+$117) |
| VOO | −5.2% (−$619) |

Its mistake was a **mid-month move into QQQ** for more return (Oct 22 and Oct 29). Tech fell, and
Turtle followed its own "review at −7%" rule and sold it on Nov 3 and Nov 5 for a combined
−$670. On the last morning it also sold half its VOO to protect the result into the final bell.
The worst day of the contest was that final session (−1.45%), which was also its whole maximum
drawdown.

> "My edge is not losing. When I trusted the boring stuff, it paid. When I reached for return,
> the market charged me for it." 🐢 Turtle, final reflection

## What the experiment showed

- **Correlation, not position count, is the risk.** Rocket's four day-1 positions moved as one,
  and 1.6x leverage turned one bad day for chips into a −7.7% day for the account.
- **Leverage in a falling market only adds to the loss.** Even Rocket's calmer act 2 (one
  diversified ETF, no trading) lost nearly twice what the index did.
- **Rules beat headlines.** Both bots said their same-day web research was unreliable (wrong
  dates, stale articles). Turtle's simple rules (scale in, keep cash, cut at −7%) held up. Rocket
  did better once it stopped trading on the news.
- **Isolation held.** Each bot traded only from its own branch, memory and research. None of
  their 50 journal entries or their memory files mention the other trader.

## Small print

- **Dividends weren't credited** (see the [rules](RULES.md)). That cost Turtle a little: T-bill
  ETFs drop by their payout on ex-dividend days, and the payout never arrived. Turtle noticed this
  itself in its final reflection.
- **Margin interest wasn't charged** either, which flattered Rocket slightly: it borrowed about
  $59k for three weeks.
- Both bots woke once more on **Fri Nov 6** to sign off. The engine refused any orders, and marks
  taken that morning don't count toward the result.

## Dig deeper

- **The dashboard:** the chart, every trade with its reason, and both bots' daily journals side by side.
- **Raw books:** [`bot-risky/bots/risky`](https://github.com/dippy34/ai-paper-trading/tree/bot-risky/bots/risky)
  and [`bot-safe/bots/safe`](https://github.com/dippy34/ai-paper-trading/tree/bot-safe/bots/safe):
  trades, equity snapshots, memory files and all 25 journal entries each.
