# 📜 Competition rules

## The setup

| | |
|---|---|
| **Contestants** | 🚀 **Rocket** (risky) vs 🐢 **Turtle** (safe), two independent AI traders (Claude) |
| **Bankroll** | $100,000 of paper money each |
| **Dates** | Monday Oct 5 to Thursday Nov 5, 2026 (24 trading days) |
| **Wake-up** | every weekday at 10:17 AM ET, both at the same moment |
| **Official score** | account value at the closing price of each trading day, recorded by the scorekeeper |
| **Winner** | the higher account value at the **Nov 5, 2026 close** |
| **Benchmark** | the S&P 500 (SPY), as if $100k had been put into it at the first snapshot |

## Same for both traders

- **Same routine.** Both follow [the daily routine](ROUTINE.md) step for step and use the same tools.
- **Same market.** Both use the same price feed (Yahoo Finance) and the same paper broker
  (`python3 -m trader`).
- **Instruments:** US-listed stocks and ETFs priced in US dollars, at least $1 per share.
  No options, crypto, futures, FX or OTC/penny stocks.
- **Orders:** market orders only, during the regular session (9:30 AM to 4:00 PM ET). They fill
  instantly at Yahoo's live price **plus 0.05% when buying or covering, minus 0.05% when selling
  or shorting** (slippage). No commissions.
- **Fractional shares** are allowed, to 4 decimal places. Size orders by `--qty` or `--dollars`.
- **Every order needs a written reason.** It's shown on the public trade log.
- **Not modeled** (it's a game): margin interest, short borrow fees, dividends, and corporate
  actions such as splits.

## Different by design

| | 🚀 Rocket (risky) | 🐢 Turtle (safe) |
|---|---|---|
| Goal | maximum return, bust risk accepted | protect capital, steady growth |
| Short selling | ✅ | ❌ |
| Margin / leverage | up to **2.0x** gross exposure | ❌ none (cash can't go negative) |
| Leveraged / inverse / VIX ETFs | ✅ | ❌ |
| Max in one position | no cap | **25%** of equity (checked when buying) |
| Self-imposed house rules | stay ≥100% invested, thesis and exit for every trade | −5% drawdown budget, review losers at −7%, keep ≥10% cash or T-bills, hold ≥5 positions |

Hard limits are **enforced by the engine**: an order that breaks one is rejected with an
explanation. House rules are each trader's own discipline, and they're judged on them in their
journals. Full personas: [Rocket](../personas/risky.md) · [Turtle](../personas/safe.md).

### Leverage, precisely

- *Equity* = cash + value of longs − value of shorts.
- *Gross exposure* = value of longs + value of shorts.
- An order that **adds** exposure is rejected if gross exposure afterwards would exceed
  `max leverage × equity`. Orders that **reduce** exposure are always allowed, so a trader can
  always get out of trouble.
- If market moves push Rocket above 2.0x, nothing is force-sold, but no new risk can be added
  until it's back under the limit.
- **Bankruptcy:** if a snapshot finds equity at or below $0, every position is liquidated at the
  market price, the trader is marked 💀 *bankrupt*, and it can't trade again.

## No knowledge exchange 🚧

The two traders are isolated from each other in four ways:

1. **Separate brains.** Each is its own Claude session with its own conversation history.
   Neither can see the other's chat.
2. **Separate storage.** Each trader's books, journal and memory live on its own git branch
   (`bot-risky`, `bot-safe`). The shared code branch never contains bot data, so a trader's
   working copy only ever holds its own files.
3. **Separate tools.** The engine opens exactly one bot's folder per command and refuses to write
   if you're checked out on another bot's branch.
4. **Explicit rules.** Each trader's system prompt and the [routine](ROUTINE.md#isolation-rules-)
   forbid looking at the other's branch, the dashboard, or anything else that could leak what
   the other is doing.

The dashboard is the only place where both sets of books meet, and the traders aren't allowed to look at it.
