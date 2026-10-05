"""Offline tests for the paper broker. Run: python3 -m unittest discover -s tests"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from trader.engine import Desk, RuleError
from trader.market import MarketDataError, Quote, is_leveraged_product

ROOT = Path(__file__).resolve().parent.parent
OPEN_TIME = datetime(2026, 10, 6, 14, 30, tzinfo=timezone.utc)  # Tue 10:30 ET


def make_quote(symbol, price, itype="EQUITY", name=None, currency="USD"):
    return Quote(
        symbol=symbol, price=price, prev_close=price, currency=currency, instrument_type=itype,
        name=name or f"{symbol} Inc.", exchange="NMS", market_time=int(OPEN_TIME.timestamp()),
        regular_start=None, regular_end=None,
    )


class FakeMarket:
    def __init__(self):
        self.prices = {"SPY": 700.0, "AAA": 100.0, "BBB": 50.0, "TQQQ": 80.0, "PENNY": 0.5}
        self.types = {"TQQQ": ("ETF", "ProShares UltraPro QQQ"), "SPY": ("ETF", "SPDR S&P 500 ETF Trust")}
        self.open = True

    def quote(self, symbol, history="6mo"):
        symbol = symbol.upper()
        if symbol not in self.prices:
            raise MarketDataError(f"{symbol}: not found")
        itype, name = self.types.get(symbol, ("EQUITY", None))
        return make_quote(symbol, self.prices[symbol], itype, name)

    def status(self, now):
        return {"open": self.open, "reason": "test", "session_start": None, "session_end": None}


class DeskTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copy(ROOT / "config.json", self.tmp / "config.json")
        self.mkt = FakeMarket()
        self.now = OPEN_TIME
        os.environ["TRADER_SKIP_BRANCH_CHECK"] = "1"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def desk(self, bot):
        return Desk(
            bot, root=self.tmp, quote_fn=self.mkt.quote, now_fn=lambda: self.now,
            market_fn=self.mkt.status, traded_today_fn=lambda now: True,
        )

    # ---- basics
    def test_buy_and_sell_with_slippage_and_pnl(self):
        d = self.desk("safe")
        t = d.order("buy", "AAA", qty=100, reason="test buy of a quality name")
        self.assertAlmostEqual(t["price"], 100.05)  # 5 bps slippage
        self.assertAlmostEqual(d.state["cash"], 100000 - 10005)
        self.mkt.prices["AAA"] = 110.0
        d = self.desk("safe")  # fresh desk = fresh quotes, state reloaded from disk
        t = d.order("sell", "AAA", all_=True, reason="taking profits after the pop")
        self.assertAlmostEqual(t["price"], 110 * (1 - 0.0005))
        self.assertAlmostEqual(t["realized_pnl"], (109.945 - 100.05) * 100, places=4)
        self.assertEqual(d.state["positions"], {})

    def test_dollar_orders_round_down_to_4dp(self):
        d = self.desk("risky")
        t = d.order("buy", "BBB", dollars=1000, reason="dollar sized order test")
        self.assertEqual(t["qty"], 19.99)  # 1000 / 50.025 = 19.990004..
        self.assertLessEqual(t["notional"], 1000)

    def test_reason_required(self):
        with self.assertRaises(RuleError):
            self.desk("risky").order("buy", "AAA", qty=1, reason="")

    def test_market_closed_rejected(self):
        self.mkt.open = False
        with self.assertRaisesRegex(RuleError, "closed"):
            self.desk("risky").order("buy", "AAA", qty=1, reason="should not fill when closed")

    def test_outside_competition_rejected(self):
        self.now = datetime(2026, 11, 9, 15, 0, tzinfo=timezone.utc)
        with self.assertRaisesRegex(RuleError, "ended"):
            self.desk("risky").order("buy", "AAA", qty=1, reason="too late to the party")

    def test_penny_and_unknown_rejected(self):
        d = self.desk("risky")
        with self.assertRaisesRegex(RuleError, "penny"):
            d.order("buy", "PENNY", qty=10, reason="lottery ticket attempt")
        with self.assertRaisesRegex(RuleError, "Can't trade"):
            d.order("buy", "NOPE", qty=10, reason="symbol does not exist")

    # ---- Turtle (safe) rules
    def test_safe_cannot_short_or_use_leverage_or_leveraged_etfs(self):
        d = self.desk("safe")
        with self.assertRaisesRegex(RuleError, "long-only"):
            d.order("short", "AAA", qty=10, reason="trying to short as turtle")
        with self.assertRaisesRegex(RuleError, "leveraged"):
            d.order("buy", "TQQQ", qty=10, reason="trying 3x as turtle")

    def test_safe_position_cap_25pct(self):
        d = self.desk("safe")
        d.order("buy", "AAA", dollars=24000, reason="near the position cap")
        with self.assertRaisesRegex(RuleError, "Position limit"):
            d.order("buy", "AAA", dollars=2000, reason="this pushes over 25 percent")

    def test_safe_cannot_spend_more_than_cash(self):
        d = self.desk("safe")
        for sym, px in (("C1", 10.0), ("C2", 10.0), ("C3", 10.0), ("C4", 10.0)):
            self.mkt.prices[sym] = px
            d.order("buy", sym, dollars=24000, reason="filling the book with four names")
        self.mkt.prices["C5"] = 10.0
        with self.assertRaisesRegex(RuleError, "Not enough cash"):
            d.order("buy", "C5", dollars=10000, reason="only about 4k cash is left")

    # ---- Rocket (risky) rules
    def test_risky_can_lever_to_2x_but_not_beyond(self):
        d = self.desk("risky")
        d.order("buy", "TQQQ", dollars=150000, reason="max send on leveraged nasdaq")
        self.assertLess(d.state["cash"], 0)  # on margin
        with self.assertRaisesRegex(RuleError, "Leverage limit"):
            d.order("buy", "AAA", dollars=60000, reason="this goes past 2x gross")
        d.order("buy", "AAA", dollars=45000, reason="this fits under 2x gross")

    def test_short_and_cover(self):
        d = self.desk("risky")
        d.order("short", "AAA", qty=100, reason="betting against AAA")
        self.assertEqual(d.state["positions"]["AAA"]["qty"], -100)
        self.assertAlmostEqual(d.value()["equity"], 100000 - 100 * 100 * 0.0005, places=4)
        self.mkt.prices["AAA"] = 90.0
        d = self.desk("risky")
        t = d.order("cover", "AAA", all_=True, reason="covering into the drop")
        self.assertAlmostEqual(t["realized_pnl"], (99.95 - 90.045) * 100, places=4)
        with self.assertRaises(RuleError):
            d.order("cover", "AAA", qty=1, reason="nothing left to cover")

    def test_cannot_mix_long_and_short(self):
        d = self.desk("risky")
        d.order("buy", "AAA", qty=10, reason="long first")
        with self.assertRaisesRegex(RuleError, "Sell it first"):
            d.order("short", "AAA", qty=10, reason="flip without selling")

    def test_risk_reducing_trades_allowed_in_margin_call(self):
        d = self.desk("risky")
        d.order("buy", "AAA", dollars=199000, reason="all in with leverage")
        self.mkt.prices["AAA"] = 70.0  # -30% -> equity ~40k, gross ~139k = 3.5x
        d = self.desk("risky")
        with self.assertRaisesRegex(RuleError, "Leverage limit"):
            d.order("buy", "BBB", qty=1, reason="adding risk in a margin call")
        d.order("sell", "AAA", qty=1000, reason="deleveraging is always allowed")

    def test_bankruptcy_liquidates(self):
        d = self.desk("risky")
        d.order("buy", "AAA", dollars=199000, reason="all in with leverage")
        self.mkt.prices["AAA"] = 45.0  # equity < 0
        d = self.desk("risky")
        snap = d.snapshot("close")
        self.assertEqual(d.state["status"], "bankrupt")
        self.assertEqual(d.state["positions"], {})
        self.assertLessEqual(snap["equity"], 0)
        with self.assertRaisesRegex(RuleError, "bankrupt"):
            d.order("buy", "BBB", qty=1, reason="trying to trade after busting")

    # ---- snapshots + journal + isolation
    def test_snapshot_dedupes_per_day_and_label(self):
        d = self.desk("safe")
        d.snapshot("morning")
        d.snapshot("morning")
        d.snapshot("close")
        self.assertEqual([e["label"] for e in d.equity], ["morning", "close"])
        self.assertEqual(d.equity[0]["benchmark"], 700.0)

    def test_journal_appends_and_indexes(self):
        d = self.desk("safe")
        d.write_journal("## Market read\nCalm.")
        d.write_journal("Second thought.")
        text = (self.tmp / "bots/safe/journal/2026-10-06.md").read_text()
        self.assertIn("Trading day 2 of 24", text)
        self.assertIn("Second thought.", text)
        self.assertEqual(json.loads((self.tmp / "bots/safe/journal/index.json").read_text()), ["2026-10-06"])

    def test_bots_only_touch_their_own_folder(self):
        self.desk("risky").order("buy", "AAA", qty=1, reason="just one share to test")
        self.assertTrue((self.tmp / "bots/risky/trades.json").exists())
        self.assertFalse((self.tmp / "bots/safe").exists())

    def test_branch_guard(self):
        os.environ["TRADER_SKIP_BRANCH_CHECK"] = "0"
        try:
            d = self.desk("risky")
            d.root = ROOT  # a real git checkout that is not on bot-risky
            from trader.engine import current_git_branch
            if current_git_branch(ROOT) not in (None, "bot-risky"):
                with self.assertRaisesRegex(RuleError, "wake.sh"):
                    d.check_branch()
        finally:
            os.environ["TRADER_SKIP_BRANCH_CHECK"] = "1"


class LeveragedDetectionTest(unittest.TestCase):
    def check(self, symbol, name, expected):
        self.assertEqual(is_leveraged_product(make_quote(symbol, 10, "ETF", name)), expected, name)

    def test_names(self):
        self.check("XYZ1", "Direxion Daily Semiconductor Bull 3X Shares", True)
        self.check("XYZ2", "GraniteShares 2x Long NVDA Daily ETF", True)
        self.check("XYZ3", "ProShares Ultra S&P500", True)
        self.check("XYZ4", "ProShares Short QQQ", True)
        self.check("XYZ5", "Invesco S&P 500 Low Volatility ETF", False)
        self.check("XYZ6", "JPMorgan Ultra-Short Income ETF", False)
        self.check("XYZ7", "iShares 0-3 Month Treasury Bond ETF", False)
        self.check("XYZ8", "Vanguard Total Stock Market Index Fund ETF", False)


if __name__ == "__main__":
    unittest.main()
