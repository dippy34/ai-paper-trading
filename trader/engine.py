"""The paper broker: portfolios, order validation, fills, snapshots and journals.

Each bot's books live in `bots/<bot>/` on that bot's own branch. Nothing in here
ever reads another bot's directory: a Desk only knows about the bot it was opened for.
"""

from __future__ import annotations

import copy
import json
import math
import os
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from .clock import et_date, iso_utc, now_utc, to_et, weekdays_between
from .market import MarketDataError, Quote, get_quote, is_leveraged_product, market_status, traded_today

EPS = 1e-9
QTY_DECIMALS = 4
SIDES = ("buy", "sell", "short", "cover")


class RuleError(Exception):
    """An order or action that the competition rules do not allow."""


def repo_root() -> Path:
    return Path(os.environ.get("TRADER_HOME") or Path(__file__).resolve().parent.parent)


def load_config(root: Path | None = None) -> dict:
    with open((root or repo_root()) / "config.json", encoding="utf-8") as f:
        return json.load(f)


def _read_json(path: Path, default):
    if not path.exists():
        return copy.deepcopy(default)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(path)


def money(x: float) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.2f}"


def pct(x: float | None, digits: int = 2) -> str:
    return "n/a" if x is None else f"{x:+.{digits}f}%"


def floor_qty(x: float) -> float:
    f = 10 ** QTY_DECIMALS
    return math.floor(x * f + EPS) / f


def current_git_branch(root: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root, capture_output=True, text=True, timeout=10
        )
    except Exception:  # noqa: BLE001
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


class Desk:
    """One bot's trading desk."""

    def __init__(
        self,
        bot: str,
        root: Path | None = None,
        quote_fn: Callable[..., Quote] = get_quote,
        now_fn: Callable[[], datetime] = now_utc,
        market_fn: Callable[..., dict] | None = None,
        traded_today_fn: Callable[..., bool] | None = None,
    ):
        self.root = root or repo_root()
        self.config = load_config(self.root)
        if bot not in self.config["bots"]:
            raise RuleError(f"Unknown bot {bot!r}. Choose one of: {', '.join(self.config['bots'])}")
        self.bot = bot
        self.meta = self.config["bots"][bot]
        self.comp = self.config["competition"]
        self.rules = self.meta["rules"]
        self.quote_fn = quote_fn
        self.now_fn = now_fn
        self.market_fn = market_fn or (lambda now: market_status(now, quote_fn=quote_fn))
        self.traded_today_fn = traded_today_fn or (lambda now: traded_today(now, quote_fn=quote_fn))
        self.dir = self.root / "bots" / bot
        self._quotes: dict[str, Quote] = {}
        self.load()

    # ------------------------------------------------------------------ storage
    @property
    def paths(self) -> dict[str, Path]:
        return {
            "portfolio": self.dir / "portfolio.json",
            "trades": self.dir / "trades.json",
            "equity": self.dir / "equity.json",
            "journal_dir": self.dir / "journal",
            "journal_index": self.dir / "journal" / "index.json",
            "memory": self.dir / "memory.md",
        }

    def load(self) -> None:
        p = self.paths
        self.state = _read_json(
            p["portfolio"],
            {
                "bot": self.bot,
                "name": self.meta["name"],
                "starting_cash": float(self.comp["starting_cash"]),
                "cash": float(self.comp["starting_cash"]),
                "positions": {},
                "realized_pnl": 0.0,
                "status": "active",
                "created": iso_utc(self.now_fn()),
                "updated": iso_utc(self.now_fn()),
            },
        )
        self.trades: list[dict] = _read_json(p["trades"], [])
        self.equity: list[dict] = _read_json(p["equity"], [])

    def save(self) -> None:
        p = self.paths
        self.state["updated"] = iso_utc(self.now_fn())
        _write_json(p["portfolio"], self.state)
        _write_json(p["trades"], self.trades)
        _write_json(p["equity"], self.equity)
        if not p["memory"].exists():
            p["memory"].write_text(
                f"# {self.meta['emoji']} {self.meta['name']}'s memory\n\n"
                "_Private notes I carry from day to day: open theses, watchlist, lessons learned._\n",
                encoding="utf-8",
            )

    def ensure_initialized(self) -> None:
        if not self.paths["portfolio"].exists() or not self.paths["memory"].exists():
            self.save()

    def check_branch(self) -> None:
        """Refuse to write books while checked out on someone else's branch."""
        branch = current_git_branch(self.root)
        if branch and branch != self.meta["branch"] and os.environ.get("TRADER_SKIP_BRANCH_CHECK") != "1":
            raise RuleError(
                f"You're on git branch '{branch}', but {self.meta['name']}'s books live on '{self.meta['branch']}'. "
                f"Run `bash scripts/wake.sh {self.bot}` first."
            )

    # ------------------------------------------------------------------ prices
    def quote(self, symbol: str, history: str = "6mo") -> Quote:
        symbol = symbol.upper()
        if symbol not in self._quotes:
            self._quotes[symbol] = self.quote_fn(symbol, history)
        return self._quotes[symbol]

    def price_of(self, symbol: str) -> tuple[float, bool]:
        """(price, is_live). Falls back to the last known price if the feed fails."""
        try:
            return self.quote(symbol).price, True
        except MarketDataError:
            pos = self.state["positions"].get(symbol, {})
            return float(pos.get("last_price") or pos.get("avg_price") or 0.0), False

    def value(self, state: dict | None = None, overrides: dict[str, float] | None = None) -> dict:
        state = state if state is not None else self.state
        overrides = overrides or {}
        positions = {}
        long_value = short_value = 0.0
        stale = []
        for sym, pos in sorted(state["positions"].items()):
            if sym in overrides:
                price, live = overrides[sym], True
            else:
                price, live = self.price_of(sym)
            if not live:
                stale.append(sym)
            qty = pos["qty"]
            val = qty * price
            cost = qty * pos["avg_price"]
            positions[sym] = {
                "qty": qty,
                "avg_price": pos["avg_price"],
                "price": price,
                "value": val,
                "unrealized_pnl": val - cost,
                "unrealized_pct": ((price / pos["avg_price"] - 1) * 100 * (1 if qty > 0 else -1)) if pos["avg_price"] else None,
            }
            if val >= 0:
                long_value += val
            else:
                short_value += -val
        equity = state["cash"] + long_value - short_value
        gross = long_value + short_value
        for p in positions.values():
            p["weight_pct"] = (abs(p["value"]) / equity * 100) if equity > 0 else None
        return {
            "cash": state["cash"],
            "long_value": long_value,
            "short_value": short_value,
            "gross": gross,
            "equity": equity,
            "leverage": (gross / equity) if equity > 0 else None,
            "positions": positions,
            "stale": stale,
        }

    # ------------------------------------------------------------------ calendar
    def today(self) -> date:
        return et_date(self.now_fn())

    def competition_phase(self, d: date | None = None) -> str:
        d = d or self.today()
        start = date.fromisoformat(self.comp["start_date"])
        end = date.fromisoformat(self.comp["end_date"])
        if d < start:
            return "not_started"
        if d > end:
            return "finished"
        return "live"

    def day_number(self, d: date | None = None) -> tuple[int, int]:
        d = d or self.today()
        start = date.fromisoformat(self.comp["start_date"])
        end = date.fromisoformat(self.comp["end_date"])
        return weekdays_between(start, min(d, end)), weekdays_between(start, end)

    # ------------------------------------------------------------------ trading
    def order(
        self,
        side: str,
        symbol: str,
        qty: float | None = None,
        dollars: float | None = None,
        all_: bool = False,
        reason: str = "",
    ) -> dict:
        side = side.lower()
        if side not in SIDES:
            raise RuleError(f"Unknown side {side!r}")
        symbol = symbol.strip().upper()
        reason = (reason or "").strip()
        if len(reason) < 10:
            raise RuleError("Every trade needs a real --reason (at least a sentence). It goes on the public trade log.")
        if sum(x is not None and x is not False for x in (qty, dollars, all_ or None)) != 1:
            raise RuleError("Give exactly one of --qty, --dollars or --all.")
        if all_ and side not in ("sell", "cover"):
            raise RuleError("--all only works with sell or cover.")

        now = self.now_fn()
        phase = self.competition_phase()
        if phase == "not_started":
            raise RuleError(f"The competition starts on {self.comp['start_date']}.")
        if phase == "finished":
            raise RuleError(f"The competition ended on {self.comp['end_date']}. No more trading.")
        if self.state["status"] != "active":
            raise RuleError(f"{self.meta['name']} is {self.state['status']} and can't trade anymore.")
        ms = self.market_fn(now)
        if not ms["open"]:
            raise RuleError(f"Market is closed ({ms['reason']}). Orders only fill during the regular session.")

        try:
            q = self.quote(symbol)
        except MarketDataError as e:
            raise RuleError(f"Can't trade {symbol}: {e}") from e
        if q.currency != "USD":
            raise RuleError(f"{symbol} trades in {q.currency}; only US-dollar listings are allowed.")
        if q.instrument_type not in ("EQUITY", "ETF"):
            raise RuleError(f"{symbol} is a {q.instrument_type}; only stocks and ETFs are allowed.")
        if q.price < float(self.comp["min_price"]):
            raise RuleError(f"{symbol} is under ${self.comp['min_price']:.2f}; penny stocks are off limits.")
        if not self.rules["allow_leveraged_etfs"] and is_leveraged_product(q):
            raise RuleError(f"{symbol} ({q.name}) is a leveraged/inverse/volatility product. Not allowed for {self.meta['name']}.")
        if side == "short" and not self.rules["allow_short"]:
            raise RuleError(f"{self.meta['name']} is long-only. No short selling.")

        pos = self.state["positions"].get(symbol)
        held = pos["qty"] if pos else 0.0
        slip = float(self.comp["slippage_bps"]) / 10_000
        fill = q.price * (1 + slip) if side in ("buy", "cover") else q.price * (1 - slip)

        if side == "buy" and held < -EPS:
            raise RuleError(f"You're short {symbol}. Use `cover` to buy it back.")
        if side == "short" and held > EPS:
            raise RuleError(f"You're long {symbol}. Sell it first if you want to flip short.")
        if side == "sell" and held <= EPS:
            raise RuleError(f"You don't own any {symbol}.")
        if side == "cover" and held >= -EPS:
            raise RuleError(f"You're not short {symbol}.")

        if all_:
            n = abs(held)
        elif dollars is not None:
            if dollars <= 0:
                raise RuleError("--dollars must be positive.")
            n = floor_qty(dollars / fill)
            if side in ("sell", "cover") and n > abs(held):
                n = abs(held)
        else:
            n = floor_qty(float(qty))
        if n <= EPS:
            raise RuleError("Order size rounds to zero shares.")
        if side in ("sell", "cover") and n > abs(held) + EPS:
            raise RuleError(f"You only have {abs(held):g} shares of {symbol} to {side}.")

        before = self.value()
        new = copy.deepcopy(self.state)
        realized = None
        notional = n * fill
        if side == "buy":
            new_qty = held + n
            avg = ((held * pos["avg_price"]) if pos else 0.0) + notional
            new["cash"] -= notional
            new["positions"][symbol] = {**(pos or {"opened": self.today().isoformat()}), "qty": new_qty, "avg_price": avg / new_qty}
        elif side == "short":
            new_qty = held - n
            avg = ((abs(held) * pos["avg_price"]) if pos else 0.0) + notional
            new["cash"] += notional
            new["positions"][symbol] = {**(pos or {"opened": self.today().isoformat()}), "qty": new_qty, "avg_price": avg / abs(new_qty)}
        elif side == "sell":
            new_qty = held - n
            realized = (fill - pos["avg_price"]) * n
            new["cash"] += notional
            new["positions"][symbol] = {**pos, "qty": new_qty}
        else:  # cover
            new_qty = held + n
            realized = (pos["avg_price"] - fill) * n
            new["cash"] -= notional
            new["positions"][symbol] = {**pos, "qty": new_qty}
        if abs(new_qty) <= EPS:
            del new["positions"][symbol]
        else:
            new["positions"][symbol]["last_price"] = q.price
        if realized is not None:
            new["realized_pnl"] += realized

        after = self.value(new, overrides={symbol: q.price})
        if side in ("buy", "short"):  # risk-increasing orders must respect the limits
            self._check_limits(symbol, before, after, notional)

        trade = {
            "id": len(self.trades) + 1,
            "bot": self.bot,
            "ts": iso_utc(now),
            "date": self.today().isoformat(),
            "side": side,
            "symbol": symbol,
            "name": q.name,
            "qty": n,
            "quote": round(q.price, 4),
            "price": round(fill, 4),
            "notional": round(notional, 2),
            "realized_pnl": None if realized is None else round(realized, 2),
            "position_after": round(new_qty, QTY_DECIMALS) if abs(new_qty) > EPS else 0,
            "cash_after": round(after["cash"], 2),
            "equity_after": round(after["equity"], 2),
            "reason": reason,
        }
        self.state = new
        self.trades.append(trade)
        self.save()
        return trade

    def _check_limits(self, symbol: str, before: dict, after: dict, notional: float) -> None:
        max_gross = float(self.rules["max_gross_leverage"])
        if after["equity"] <= 0:
            raise RuleError("That trade would leave you with zero or negative equity.")
        if max_gross <= 1.0 + EPS and after["cash"] < -0.005:
            raise RuleError(
                f"Not enough cash: this costs {money(notional)} but you only have {money(before['cash'])}. "
                f"{self.meta['name']} can't borrow."
            )
        limit = max_gross * after["equity"]
        if after["gross"] > limit + 0.01 and after["gross"] > before["gross"] + EPS:
            room = max(0.0, max_gross * before["equity"] - before["gross"])
            raise RuleError(
                f"Leverage limit: gross exposure would be {money(after['gross'])} "
                f"({after['gross'] / after['equity']:.2f}x equity), max is {max_gross:.1f}x. "
                f"You have about {money(room)} of room."
            )
        cap = self.rules.get("max_position_pct")
        if cap:
            pos_val = abs(after["positions"][symbol]["value"])
            if pos_val > cap * after["equity"] + 0.01:
                room = max(0.0, cap * after["equity"] - abs(before["positions"].get(symbol, {}).get("value", 0.0)))
                raise RuleError(
                    f"Position limit: {symbol} would be {pos_val / after['equity'] * 100:.1f}% of equity; "
                    f"max is {cap * 100:.0f}%. You can add about {money(room)} more."
                )

    def buying_power(self, val: dict | None = None) -> float:
        val = val or self.value()
        if val["equity"] <= 0:
            return 0.0
        max_gross = float(self.rules["max_gross_leverage"])
        if max_gross <= 1.0 + EPS:
            return max(0.0, val["cash"])
        return max(0.0, max_gross * val["equity"] - val["gross"])

    # ------------------------------------------------------------------ snapshots
    def snapshot(self, label: str, only_trading_day: bool = False) -> dict | None:
        now = self.now_fn()
        today = self.today()
        if only_trading_day:
            if self.competition_phase(today) != "live":
                return None
            if not self.traded_today_fn(now):
                return None
        val = self.value()
        if val["equity"] <= 0 and self.state["status"] == "active":
            self._liquidate(val, now)
            val = self.value()
        for sym, p in val["positions"].items():
            if sym not in val["stale"]:
                self.state["positions"][sym]["last_price"] = p["price"]
        try:
            spy = self.quote(self.comp["benchmark"]).price
        except MarketDataError:
            spy = None
        start = float(self.state["starting_cash"])
        snap = {
            "ts": iso_utc(now),
            "date": today.isoformat(),
            "label": label,
            "equity": round(val["equity"], 2),
            "cash": round(val["cash"], 2),
            "long_value": round(val["long_value"], 2),
            "short_value": round(val["short_value"], 2),
            "gross": round(val["gross"], 2),
            "leverage": None if val["leverage"] is None else round(val["leverage"], 3),
            "return_pct": round((val["equity"] / start - 1) * 100, 3),
            "benchmark": spy,
            "positions": {
                s: {"qty": p["qty"], "price": round(p["price"], 4), "value": round(p["value"], 2)}
                for s, p in val["positions"].items()
            },
        }
        # One snapshot per (date, label): re-running replaces rather than duplicates.
        self.equity = [e for e in self.equity if not (e["date"] == snap["date"] and e["label"] == label)]
        self.equity.append(snap)
        self.equity.sort(key=lambda e: e["ts"])
        self.save()
        return snap

    def _liquidate(self, val: dict, now: datetime) -> None:
        for sym, p in val["positions"].items():
            qty = p["qty"]
            side = "sell" if qty > 0 else "cover"
            realized = (p["price"] - p["avg_price"]) * qty
            self.state["cash"] += qty * p["price"]
            self.state["realized_pnl"] += realized
            self.trades.append({
                "id": len(self.trades) + 1, "bot": self.bot, "ts": iso_utc(now), "date": self.today().isoformat(),
                "side": side, "symbol": sym, "name": None, "qty": abs(qty), "quote": p["price"], "price": p["price"],
                "notional": round(abs(qty * p["price"]), 2), "realized_pnl": round(realized, 2), "position_after": 0,
                "cash_after": round(self.state["cash"], 2), "equity_after": round(self.state["cash"], 2),
                "reason": "FORCED LIQUIDATION: equity hit zero. Game over.",
            })
        self.state["positions"] = {}
        self.state["status"] = "bankrupt"

    # ------------------------------------------------------------------ journal
    def write_journal(self, text: str) -> Path:
        text = text.strip()
        if not text:
            raise RuleError("Journal entry is empty.")
        now = self.now_fn()
        d = self.today()
        p = self.paths
        path = p["journal_dir"] / f"{d.isoformat()}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        stamp = to_et(now).strftime("%-I:%M %p ET")
        if path.exists():
            body = path.read_text(encoding="utf-8").rstrip() + f"\n\n---\n\n_Update at {stamp}_\n\n{text}\n"
        else:
            day, total = self.day_number(d)
            title = f"# {self.meta['emoji']} {self.meta['name']} · {to_et(now).strftime('%A, %B %-d, %Y')}"
            sub = f"_Trading day {day} of {total} · written at {stamp}_" if self.competition_phase(d) == "live" else f"_Written at {stamp}_"
            body = f"{title}\n\n{sub}\n\n{text}\n"
        path.write_text(body, encoding="utf-8")
        index = _read_json(p["journal_index"], [])
        if d.isoformat() not in index:
            index.append(d.isoformat())
        index.sort()
        _write_json(p["journal_index"], index)
        self.ensure_initialized()
        return path

    # ------------------------------------------------------------------ reports
    def status_report(self) -> str:
        now = self.now_fn()
        today = self.today()
        ms = self.market_fn(now)
        val = self.value()
        start = float(self.state["starting_cash"])
        day, total = self.day_number(today)
        phase = self.competition_phase(today)
        m = self.meta
        r = self.rules
        lines = [
            f"{m['emoji']}  {m['name'].upper()} ({self.bot}) · {to_et(now).strftime('%a %b %-d %Y, %-I:%M %p ET')}",
            f"Competition: {phase.replace('_', ' ')}"
            + (f" · trading day {day} of {total} (ends {self.comp['end_date']})" if phase == "live" else ""),
            f"Market: {'OPEN' if ms['open'] else 'CLOSED'} ({ms['reason']})",
            f"Status: {self.state['status']}",
            "",
            f"Equity        {money(val['equity']):>16}   {pct((val['equity'] / start - 1) * 100)} vs {money(start)} start",
            f"Cash          {money(val['cash']):>16}",
            f"Long value    {money(val['long_value']):>16}",
            f"Short value   {money(val['short_value']):>16}",
            f"Gross / lev   {money(val['gross']):>16}   {val['leverage'] or 0:.2f}x (max {r['max_gross_leverage']:.1f}x)",
            f"Realized P&L  {money(self.state['realized_pnl']):>16}",
            f"Buying power  {money(self.buying_power(val)):>16}",
        ]
        if r.get("max_position_pct"):
            lines.append(f"Position cap  {r['max_position_pct'] * 100:.0f}% of equity per holding ({money(r['max_position_pct'] * val['equity'])})")
        lines.append("")
        if val["positions"]:
            lines.append(f"{'SYMBOL':<8}{'QTY':>12}{'AVG':>11}{'PRICE':>11}{'VALUE':>14}{'P&L':>13}{'P&L%':>9}{'WEIGHT':>8}")
            for sym, p in val["positions"].items():
                lines.append(
                    f"{sym:<8}{p['qty']:>12,.4g}{p['avg_price']:>11,.2f}{p['price']:>11,.2f}"
                    f"{p['value']:>14,.2f}{p['unrealized_pnl']:>13,.2f}{pct(p['unrealized_pct'], 1):>9}"
                    f"{(p['weight_pct'] or 0):>7.1f}%"
                )
            if val["stale"]:
                lines.append(f"(stale prices for: {', '.join(val['stale'])})")
        else:
            lines.append("No open positions. 100% cash.")
        todays = [t for t in self.trades if t["date"] == today.isoformat()]
        lines.append("")
        lines.append(f"Trades today: {len(todays)} · all-time: {len(self.trades)}")
        for t in todays:
            lines.append(f"  #{t['id']} {t['side'].upper():<5} {t['qty']:g} {t['symbol']} @ {t['price']:.2f}")
        if self.equity:
            last = self.equity[-1]
            lines.append(f"Last snapshot: {last['date']} ({last['label']}) equity {money(last['equity'])}")
        return "\n".join(lines)

    def summary_line(self) -> str:
        val = self.value()
        start = float(self.state["starting_cash"])
        today = self.today().isoformat()
        n = sum(1 for t in self.trades if t["date"] == today)
        return (
            f"{self.meta['emoji']} {self.meta['name']} {today}: equity {money(val['equity'])} "
            f"({pct((val['equity'] / start - 1) * 100)}), {n} trade{'s' if n != 1 else ''} today"
        )
