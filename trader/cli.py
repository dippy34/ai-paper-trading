"""Command line for the traders: `python3 -m trader <command> ...`.

Run `python3 -m trader --help` (or `<command> --help`) for usage.
"""

from __future__ import annotations

import argparse
import sys

from .engine import Desk, RuleError, load_config, money, pct
from .market import MarketDataError, get_quote, is_leveraged_product, market_status


def _desk(args, write: bool = False) -> Desk:
    desk = Desk(args.bot)
    if write:
        desk.check_branch()
    return desk


def cmd_status(args) -> None:
    print(_desk(args).status_report())


def cmd_init(args) -> None:
    desk = _desk(args, write=True)
    desk.ensure_initialized()
    print(f"Books ready in bots/{args.bot}/")


def cmd_market(args) -> None:
    ms = market_status()
    print(f"Market {'OPEN' if ms['open'] else 'CLOSED'}: {ms['reason']}")
    print(f"Session: {ms['session_start']} -> {ms['session_end']} (UTC)")


def cmd_quote(args) -> None:
    hdr = f"{'SYMBOL':<7}{'PRICE':>11}{'DAY':>8}{'5D':>8}{'1M':>8}{'3M':>8}{'VOL20':>7}{'vs50D':>8}  {'52W RANGE':<19} NAME"
    print(hdr)
    for sym in args.symbols:
        try:
            q = get_quote(sym)
        except MarketDataError as e:
            print(f"{sym.upper():<7} error: {e}")
            continue
        sma50 = q.sma(50)
        vs50 = (q.price / sma50 - 1) * 100 if sma50 else None
        rng = f"{q.week52_low or 0:,.2f}-{q.week52_high or 0:,.2f}"
        vol = q.volatility_pct()
        flags = []
        if q.instrument_type not in ("EQUITY", "ETF"):
            flags.append(f"[{q.instrument_type}: not tradable]")
        if is_leveraged_product(q):
            flags.append("[leveraged/inverse]")
        print(
            f"{q.symbol:<7}{q.price:>11,.2f}{pct(q.change_pct, 1):>8}{pct(q.ret_pct(5), 1):>8}"
            f"{pct(q.ret_pct(21), 1):>8}{pct(q.ret_pct(63), 1):>8}"
            f"{(f'{vol:.0f}%' if vol else 'n/a'):>7}{pct(vs50, 1):>8}  {rng:<19} {q.name or ''} {' '.join(flags)}"
        )
    print("\nDAY = vs yesterday's close · 5D/1M/3M = vs close 5/21/63 sessions ago · VOL20 = 20-day annualized volatility · vs50D = distance from 50-day average")


def cmd_history(args) -> None:
    q = get_quote(args.symbol, args.range)
    closes = q.closes[-args.days:]
    print(f"{q.symbol} · {q.name} · last {len(closes)} daily closes, then the latest price")
    prev = None
    for d, c in closes:
        chg = f"{(c / prev - 1) * 100:+.2f}%" if prev else ""
        print(f"{d}  {c:>12,.2f}  {chg}")
        prev = c
    chg = f"{(q.price / prev - 1) * 100:+.2f}%" if prev else ""
    print(f"{'latest':<10}  {q.price:>12,.2f}  {chg}  <- current/most recent session")


def cmd_order(args) -> None:
    desk = _desk(args, write=True)
    trade = desk.order(
        args.command, args.symbol, qty=args.qty, dollars=args.dollars, all_=getattr(args, "all", False), reason=args.reason
    )
    pnl = f" · realized P&L {money(trade['realized_pnl'])}" if trade["realized_pnl"] is not None else ""
    print(
        f"FILLED #{trade['id']}: {trade['side'].upper()} {trade['qty']:g} {trade['symbol']} @ {trade['price']:.4f} "
        f"(quote {trade['quote']:.4f}) = {money(trade['notional'])}{pnl}"
    )
    print(f"Cash now {money(trade['cash_after'])} · equity {money(trade['equity_after'])}")


def cmd_trades(args) -> None:
    desk = _desk(args)
    rows = desk.trades
    if args.today:
        rows = [t for t in rows if t["date"] == desk.today().isoformat()]
    if not rows:
        print("No trades.")
    for t in rows[-args.last:]:
        pnl = f" P&L {money(t['realized_pnl'])}" if t["realized_pnl"] is not None else ""
        print(f"#{t['id']:<4} {t['date']} {t['side'].upper():<5} {t['qty']:>10g} {t['symbol']:<6} @ {t['price']:>10.2f}{pnl}\n       why: {t['reason']}")


def cmd_journal(args) -> None:
    desk = _desk(args, write=True)
    if args.file:
        text = open(args.file, encoding="utf-8").read()
    elif args.text:
        text = args.text
    else:
        text = sys.stdin.read()
    path = desk.write_journal(text)
    print(f"Journal saved: {path.relative_to(desk.root)}")


def cmd_snapshot(args) -> None:
    desk = _desk(args, write=True)
    snap = desk.snapshot(args.label, only_trading_day=args.only_trading_day)
    if snap is None:
        print("No snapshot: not a trading day (or outside the competition window).")
        return
    print(f"Snapshot ({snap['label']}) {snap['date']}: equity {money(snap['equity'])} ({snap['return_pct']:+.2f}%)")


def cmd_summary(args) -> None:
    print(_desk(args).summary_line())


def cmd_branch(args) -> None:
    print(load_config()["bots"][args.bot]["branch"])


def cmd_config(args) -> None:
    cfg = load_config()
    val = cfg
    for part in args.key.split("."):
        val = val[part]
    print(val)


def build_parser() -> argparse.ArgumentParser:
    bots = list(load_config()["bots"])
    p = argparse.ArgumentParser(prog="python3 -m trader", description="AI paper trading desk.")
    sub = p.add_subparsers(dest="command", required=True)

    def with_bot(sp):
        sp.add_argument("--bot", required=True, choices=bots, help="which trader you are")
        return sp

    with_bot(sub.add_parser("status", help="your portfolio, limits and the market clock")).set_defaults(fn=cmd_status)
    with_bot(sub.add_parser("init", help="create your books if they don't exist yet")).set_defaults(fn=cmd_init)
    sub.add_parser("market", help="is the market open?").set_defaults(fn=cmd_market)

    sp = sub.add_parser("quote", help="price + momentum stats for one or more symbols")
    sp.add_argument("symbols", nargs="+")
    sp.set_defaults(fn=cmd_quote)

    sp = sub.add_parser("history", help="recent daily closes for a symbol")
    sp.add_argument("symbol")
    sp.add_argument("--days", type=int, default=30)
    sp.add_argument("--range", default="6mo", help="Yahoo range, e.g. 1mo 6mo 1y")
    sp.set_defaults(fn=cmd_history)

    for side, helptext in (
        ("buy", "buy shares (go long / add to a long)"),
        ("sell", "sell shares you own"),
        ("short", "sell short (Rocket only)"),
        ("cover", "buy back a short"),
    ):
        sp = with_bot(sub.add_parser(side, help=helptext))
        sp.add_argument("symbol")
        size = sp.add_mutually_exclusive_group(required=True)
        size.add_argument("--qty", type=float, help="number of shares (fractional ok, 4 decimals)")
        size.add_argument("--dollars", type=float, help="dollar amount to trade")
        if side in ("sell", "cover"):
            size.add_argument("--all", action="store_true", help="close the whole position")
        sp.add_argument("--reason", required=True, help="why (public, shows on the trade log)")
        sp.set_defaults(fn=cmd_order)

    sp = with_bot(sub.add_parser("trades", help="your trade history"))
    sp.add_argument("--today", action="store_true")
    sp.add_argument("--last", type=int, default=50)
    sp.set_defaults(fn=cmd_trades)

    sp = with_bot(sub.add_parser("journal", help="save today's journal entry (markdown)"))
    src = sp.add_mutually_exclusive_group()
    src.add_argument("--file", help="read the entry from a file")
    src.add_argument("--text", help="the entry text")
    sp.set_defaults(fn=cmd_journal)

    sp = with_bot(sub.add_parser("snapshot", help="mark to market and record equity"))
    sp.add_argument("--label", default="manual", help="morning | close | manual")
    sp.add_argument("--only-trading-day", action="store_true", help="skip on weekends/holidays/outside the competition")
    sp.set_defaults(fn=cmd_snapshot)

    with_bot(sub.add_parser("summary", help="one-line summary (used for commit messages)")).set_defaults(fn=cmd_summary)
    with_bot(sub.add_parser("branch", help="print this bot's git branch")).set_defaults(fn=cmd_branch)

    sp = sub.add_parser("config", help="print a config value, e.g. `config code_branch`")
    sp.add_argument("key")
    sp.set_defaults(fn=cmd_config)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.fn(args)
    except RuleError as e:
        print(f"REJECTED: {e}", file=sys.stderr)
        return 2
    except MarketDataError as e:
        print(f"MARKET DATA ERROR: {e}", file=sys.stderr)
        return 3
    return 0
