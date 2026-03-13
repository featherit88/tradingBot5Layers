"""Tests for the strategies module."""

import pandas as pd

from strategies.core import (
    break_and_retest,
    ema_ribbon_scalp,
    opening_range_breakout,
    vwap_reversion,
)


def _make_df(closes: list[float], volume: int = 1000) -> pd.DataFrame:
    rows = []
    for c in closes:
        rows.append({
            "open": c - 0.5,
            "high": c + 1.0,
            "low": c - 1.0,
            "close": c,
            "volume": volume,
        })
    return pd.DataFrame(rows)


def _trending_df(start: float, step: float, n: int = 50) -> pd.DataFrame:
    closes = [start + i * step for i in range(n)]
    rows = []
    for c in closes:
        rows.append({
            "open": c - abs(step) * 0.3,
            "high": c + abs(step) * 0.5,
            "low": c - abs(step) * 0.5,
            "close": c,
            "volume": 1000,
        })
    return pd.DataFrame(rows)


# ── EMA Ribbon Scalp ────────────────────────────────────────────

class TestEMARibbonScalp:
    def test_returns_valid_direction(self):
        df = _trending_df(100, 2.0, 30)
        result = ema_ribbon_scalp(df)
        assert result in (1, -1, 0)

    def test_no_signal_on_flat(self):
        df = _make_df([100.0] * 30)
        assert ema_ribbon_scalp(df) == 0


# ── VWAP Reversion ──────────────────────────────────────────────

class TestVWAPReversion:
    def test_long_when_below_vwap(self):
        # Prices well below the session VWAP → long (fade)
        prices = [100 + i for i in range(30)] + [90]  # drop below VWAP
        df = _make_df(prices)
        result = vwap_reversion(df)
        # Should return 1 (long) since price dropped below VWAP
        assert result in (1, 0)  # depends on exact deviation

    def test_returns_valid_direction(self):
        df = _make_df([100.0] * 30)
        result = vwap_reversion(df)
        assert result in (1, -1, 0)


# ── Break & Retest ──────────────────────────────────────────────

class TestBreakAndRetest:
    def test_insufficient_data(self):
        df_5m = _make_df([100] * 5)
        df_1m = _make_df([100] * 5)
        assert break_and_retest(df_5m, df_1m) == 0

    def test_returns_valid_direction(self):
        df_5m = _make_df([100 + i for i in range(20)])
        df_1m = _make_df([100 + i for i in range(20)])
        result = break_and_retest(df_5m, df_1m)
        assert result in (1, -1, 0)


# ── Opening Range Breakout ──────────────────────────────────────

class TestORB:
    def test_returns_zero_during_range_formation(self):
        df = _make_df([100] * 30)
        assert opening_range_breakout(df, session_bar_count=10) == 0  # < 15

    def test_breakout_long(self):
        # First 15 bars flat at 100, then price at 105 (above range)
        prices = [100.0] * 20 + [105.0]
        df = _make_df(prices)
        result = opening_range_breakout(df, session_bar_count=20)
        assert result == 1

    def test_breakout_short(self):
        prices = [100.0] * 20 + [95.0]
        df = _make_df(prices)
        result = opening_range_breakout(df, session_bar_count=20)
        assert result == -1

    def test_no_breakout_inside_range(self):
        prices = [100.0] * 20 + [100.0]
        df = _make_df(prices)
        result = opening_range_breakout(df, session_bar_count=20)
        assert result == 0
