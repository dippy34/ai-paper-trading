"""Market data from Yahoo Finance's public chart endpoint (stdlib only).

Everything the traders know about prices comes through here, so both bots see
exactly the same market. Fills use `regularMarketPrice`, which during US market
hours is the live (or near-live) last trade.
"""

from __future__ import annotations

import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .clock import et_date, now_utc

USER_AGENT = "Mozilla/5.0 (compatible; ai-paper-trading/1.0)"
HOSTS = ("query1.finance.yahoo.com", "query2.finance.yahoo.com")

# Leveraged / inverse / volatility products. Turtle (safe) may not touch these.
# The name check in `is_leveraged_product` catches most others.
LEVERAGED_BLOCKLIST = {
    "TQQQ", "SQQQ", "QLD", "QID", "UPRO", "SPXU", "SPXL", "SPXS", "SSO", "SDS",
    "SH", "PSQ", "DOG", "DXD", "UDOW", "SDOW", "TNA", "TZA", "SOXL", "SOXS",
    "TECL", "TECS", "FAS", "FAZ", "LABU", "LABD", "NUGT", "DUST", "JNUG", "JDST",
    "TMF", "TMV", "TBT", "UVXY", "SVXY", "VXX", "VIXY", "UVIX", "SVIX", "FNGU",
    "FNGD", "BULZ", "BERZ", "TSLL", "TSLQ", "TSLZ", "NVDL", "NVDU", "NVDD", "NVDQ",
    "CONL", "MSTU", "MSTX", "MSTZ", "AMDL", "AAPU", "AMZU", "GGLL", "METU", "MSFU",
    "YINN", "YANG", "ERX", "ERY", "GUSH", "DRIP", "BOIL", "KOLD", "UCO", "SCO",
    "AGQ", "ZSL", "UGL", "GLL", "WEBL", "WEBS", "HIBL", "HIBS", "DPST", "CURE",
    "NAIL", "DFEN", "RETL", "MIDU", "URTY", "SRTY", "TWM", "RWM", "SPDN", "SPXQ",
    "QQQU", "QQQD", "ETHU", "BITX", "BITU", "SBIT",
}
# "2X Long", "-3x", "1.5x" ... plus the wording leveraged/inverse fund families use.
# Deliberately narrow: plain "ultra" or "volatility" would also hit ultra-short bond
# funds and low-volatility ETFs, which are exactly what a safe trader should hold.
LEVERAGED_NAME_PATTERN = re.compile(
    r"(?<![\w.])-?\d+(\.\d+)?x\b|\bultrapro\b|\bproshares (ultra|short)\b|\bleveraged\b"
    r"|\binverse\b|\bdaily (bull|bear)\b|\b(bull|bear) \d+(\.\d+)?x\b|\bvix\b",
    re.IGNORECASE,
)


class MarketDataError(RuntimeError):
    pass


@dataclass
class Quote:
    symbol: str
    price: float
    prev_close: float | None
    currency: str | None
    instrument_type: str | None
    name: str | None
    exchange: str | None
    market_time: int | None
    regular_start: int | None
    regular_end: int | None
    week52_high: float | None = None
    week52_low: float | None = None
    closes: list[tuple[str, float]] = field(default_factory=list)  # (YYYY-MM-DD, close)

    @property
    def change_pct(self) -> float | None:
        if not self.prev_close:
            return None
        return (self.price / self.prev_close - 1) * 100

    def ret_pct(self, sessions_back: int) -> float | None:
        """% change from the close `sessions_back` sessions ago to the current price."""
        if len(self.closes) <= sessions_back:
            return None
        base = self.closes[-1 - sessions_back][1]
        return (self.price / base - 1) * 100 if base else None

    def volatility_pct(self, window: int = 20) -> float | None:
        """Annualized volatility of daily close-to-close returns."""
        closes = [c for _, c in self.closes[-(window + 1):]]
        if len(closes) < 6:
            return None
        rets = [math.log(b / a) for a, b in zip(closes, closes[1:]) if a and b]
        if len(rets) < 5:
            return None
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        return math.sqrt(var) * math.sqrt(252) * 100

    def sma(self, window: int) -> float | None:
        closes = [c for _, c in self.closes[-window:]]
        return sum(closes) / len(closes) if len(closes) == window else None


def _get_json(path: str, timeout: float = 15.0) -> dict:
    last_err: Exception | None = None
    for attempt in range(3):
        for host in HOSTS:
            url = f"https://{host}{path}"
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    try:
                        return json.loads(e.read().decode("utf-8"))
                    except Exception:  # noqa: BLE001
                        raise MarketDataError(f"Symbol not found ({url})") from e
                last_err = e
            except Exception as e:  # noqa: BLE001 - network hiccups, retry
                last_err = e
        time.sleep(1.5 * (attempt + 1))
    raise MarketDataError(f"Could not reach Yahoo Finance: {last_err}")


def get_quote(symbol: str, history: str = "6mo") -> Quote:
    try:
        return _get_quote(symbol, history)
    except MarketDataError:
        raise
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise MarketDataError(f"{symbol}: unexpected data from Yahoo ({e})") from e


def _get_quote(symbol: str, history: str) -> Quote:
    symbol = symbol.strip().upper()
    if not symbol or any(c in symbol for c in "/?#& "):
        raise MarketDataError(f"Bad symbol: {symbol!r}")
    path = f"/v8/finance/chart/{urllib.parse.quote(symbol)}?range={history}&interval=1d&includePrePost=false"
    data = _get_json(path).get("chart", {})
    if data.get("error") or not data.get("result"):
        err = (data.get("error") or {}).get("description") or "no data"
        raise MarketDataError(f"{symbol}: {err}")
    res = data["result"][0]
    meta = res.get("meta", {})
    price = meta.get("regularMarketPrice")
    if price is None:
        raise MarketDataError(f"{symbol}: no price available")
    closes: list[tuple[str, float]] = []
    ts = res.get("timestamp") or []
    raw_closes = ((res.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    for t, c in zip(ts, raw_closes):
        if c is not None:
            closes.append((et_date(datetime.fromtimestamp(t, tz=timezone.utc)).isoformat(), float(c)))
    # Yahoo's last daily bar is "today" while the market is open; drop it so
    # closes[] only holds completed sessions and prev_close is yesterday's close.
    market_time = meta.get("regularMarketTime")
    if closes and market_time:
        today = et_date(datetime.fromtimestamp(market_time, tz=timezone.utc)).isoformat()
        if closes[-1][0] == today:
            closes = closes[:-1]
    prev_close = closes[-1][1] if closes else meta.get("chartPreviousClose")
    period = (meta.get("currentTradingPeriod") or {}).get("regular") or {}
    return Quote(
        symbol=meta.get("symbol", symbol).upper(),
        price=float(price),
        prev_close=float(prev_close) if prev_close else None,
        currency=meta.get("currency"),
        instrument_type=meta.get("instrumentType"),
        name=meta.get("longName") or meta.get("shortName"),
        exchange=meta.get("exchangeName"),
        market_time=market_time,
        regular_start=period.get("start"),
        regular_end=period.get("end"),
        week52_high=meta.get("fiftyTwoWeekHigh"),
        week52_low=meta.get("fiftyTwoWeekLow"),
        closes=closes,
    )


def is_leveraged_product(q: Quote) -> bool:
    if q.symbol in LEVERAGED_BLOCKLIST:
        return True
    return q.instrument_type == "ETF" and bool(LEVERAGED_NAME_PATTERN.search(q.name or ""))


def market_status(now: datetime | None = None, quote_fn=get_quote) -> dict:
    """Is the US stock market in its regular session right now?

    Uses SPY's `currentTradingPeriod`, which Yahoo rolls to the current (or next)
    real trading session, so weekends and exchange holidays come out closed.
    """
    now = now or now_utc()
    try:
        spy = quote_fn("SPY", "5d")
    except MarketDataError as e:
        return {"open": False, "reason": f"market data unavailable: {e}", "session_start": None, "session_end": None}
    start, end = spy.regular_start, spy.regular_end
    ts = now.timestamp()
    is_open = bool(start and end and start <= ts < end)
    if is_open:
        reason = "regular session in progress"
    elif start and ts < start:
        reason = "before the opening bell"
    else:
        reason = "after the closing bell (or not a trading day)"
    fmt = lambda t: datetime.fromtimestamp(t, tz=timezone.utc).isoformat() if t else None  # noqa: E731
    return {"open": is_open, "reason": reason, "session_start": fmt(start), "session_end": fmt(end), "spy": spy.price}


def traded_today(now: datetime | None = None, quote_fn=get_quote) -> bool:
    """True if SPY printed a regular-session trade today (ET) — i.e. today was a trading day."""
    now = now or now_utc()
    spy = quote_fn("SPY", "5d")
    if not spy.market_time:
        return False
    return et_date(datetime.fromtimestamp(spy.market_time, tz=timezone.utc)) == et_date(now)
