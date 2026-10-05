# 🗃️ Data formats

Each trader's records live in `bots/<bot>/` on its own branch (`bot-risky` or `bot-safe`).
Everything is plain JSON or Markdown, so you can browse it straight on GitHub, e.g.
[`bot-risky/bots/risky`](https://github.com/dippy34/ai-paper-trading/tree/bot-risky/bots/risky).

```
bots/<bot>/
├── portfolio.json      current cash, positions, realized P&L, status
├── trades.json         every fill, oldest first
├── equity.json         snapshots (morning by the bot, close by the scorekeeper)
├── memory.md           the trader's private notes, carried day to day
└── journal/
    ├── index.json      ["2026-10-05", "2026-10-06", …]
    └── 2026-10-05.md   that day's journal entry
```

## `portfolio.json`

```json
{
  "bot": "risky",
  "name": "Rocket",
  "starting_cash": 100000.0,
  "cash": -42150.31,
  "positions": {
    "SOXL": { "opened": "2026-10-05", "qty": 1200.0, "avg_price": 41.27, "last_price": 42.05 },
    "XYZ":  { "opened": "2026-10-06", "qty": -300.0, "avg_price": 88.10, "last_price": 85.40 }
  },
  "realized_pnl": 1234.56,
  "status": "active",
  "created": "2026-10-05T06:10:00Z",
  "updated": "2026-10-06T14:31:12Z"
}
```

- `qty` is negative for short positions. `avg_price` is the average entry price (positive).
- `cash` can be negative for Rocket (margin) and goes up when shorting (short sale proceeds).
- `status` is `active` or `bankrupt`.

## `trades.json`

```json
{
  "id": 7, "bot": "risky", "ts": "2026-10-06T14:29:51Z", "date": "2026-10-06",
  "side": "buy", "symbol": "SOXL", "name": "Direxion Daily Semiconductor Bull 3X Shares",
  "qty": 400.0, "quote": 41.9, "price": 41.921, "notional": 16768.38,
  "realized_pnl": null, "position_after": 1200.0,
  "cash_after": -42150.31, "equity_after": 103900.12,
  "reason": "Semis bid after TSMC monthly sales beat; adding to the 3x position into strength."
}
```

- `side`: `buy`, `sell`, `short` or `cover`.
- `quote` is the market price. `price` is the fill after slippage.
- `realized_pnl` is set on `sell` and `cover` trades (based on average cost), otherwise `null`.

## `equity.json`

```json
{
  "ts": "2026-10-06T20:15:42Z", "date": "2026-10-06", "label": "close",
  "equity": 103512.40, "cash": -42150.31, "long_value": 171162.71, "short_value": 25500.0,
  "gross": 196662.71, "leverage": 1.9, "return_pct": 3.512, "benchmark": 771.02,
  "positions": { "SOXL": { "qty": 1200.0, "price": 42.05, "value": 50460.0 } }
}
```

- `label` is `morning` (after the bot's routine) or `close` (from the scorekeeper). There's at most one per date and label; re-running replaces it.
- `benchmark` is SPY's price at that moment. The dashboard turns it into "$100k in the S&P 500".

## `config.json` (code branch)

Competition dates, starting cash, slippage, schedule, each bot's name, emoji, branch, colors and
**hard limits**, plus the list of docs shown on the website. The engine and the dashboard both
read it.
