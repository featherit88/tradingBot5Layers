"""Tests for the indicators module."""

import pandas as pd

from indicators import (
    atr,
    ema_ribbon,
    ema_ribbon_bearish,
    ema_ribbon_bullish,
    ha_signal_bearish,
    ha_signal_bullish,
    heikin_ashi,
    market_structure_bearish,
    market_structure_bullish,
    supertrend,
    volume_spike,
    vwap,
)


def _make_df(closes: list[float], volume: int = 1000) -> pd.DataFrame:
    """Helper: build OHLCV DataFrame from close prices."""
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
    """Helper: build a trending OHLCV DataFrame."""
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


# ── ATR ──────────────────────────────────────────────────────────

class TestATR:
    def test_returns_series(self):
        df = _make_df([100 + i for i in range(20)])
        result = atr(df, 14)
        assert isinstance(result, pd.Series)
        assert len(result) == len(df)

    def test_first_values_are_nan(self):
        df = _make_df([100 + i for i in range(20)])
        result = atr(df, 14)
        assert pd.isna(result.iloc[0])

    def test_positive_values(self):
        df = _make_df([100 + i for i in range(20)])
        result = atr(df, 14)
        valid = result.dropna()
        assert (valid > 0).all()


# ── Supertrend ──────────────────────────────────────────────────

class TestSupertrend:
    def test_output_columns(self):
        df = _make_df([100 + i * 0.5 for i in range(50)])
        result = supertrend(df)
        assert "supertrend" in result.columns
        assert "direction" in result.columns

    def test_direction_values(self):
        df = _make_df([100 + i * 0.5 for i in range(50)])
        result = supertrend(df)
        assert set(result["direction"].unique()).issubset({1, -1})

    def test_uptrend_detection(self):
        df = _trending_df(100, 2.0, 50)
        result = supertrend(df)
        # Last bar should be bullish in a strong uptrend
        assert result["direction"].iloc[-1] == 1


# ── Market Structure ────────────────────────────────────────────

class TestMarketStructure:
    def test_bullish_on_uptrend(self):
        # Zigzag with rising peaks and rising troughs (HH + HL).
        # Each swing leg is >FRACTAL_BARS(3) bars so fractal detection works.
        prices = [
            *[100, 102, 105, 108, 110, 108, 105, 103],     # peak 110, trough 103
            *[105, 108, 112, 115, 118, 115, 112, 110],     # peak 118, trough 110
            *[112, 115, 118, 120, 123],                     # peak 123 (HH confirmed)
        ]
        df = _make_df(prices)
        result = market_structure_bullish(df)
        assert result

    def test_bearish_on_downtrend(self):
        # Zigzag with declining peaks and declining troughs (LL + LH).
        prices = [
            *[200, 198, 195, 192, 190, 192, 195, 197],     # trough 190, peak 197
            *[195, 192, 188, 185, 182, 185, 188, 190],     # trough 182, peak 190
            *[188, 185, 182, 180, 177],                     # trough 177 (LL confirmed)
        ]
        df = _make_df(prices)
        result = market_structure_bearish(df)
        assert result

    def test_insufficient_data(self):
        df = _make_df([100, 101, 102])
        assert not market_structure_bullish(df)
        assert not market_structure_bearish(df)


# ── Heikin-Ashi ─────────────────────────────────────────────────

class TestHeikinAshi:
    def test_output_columns(self):
        df = _make_df([100 + i for i in range(10)])
        result = heikin_ashi(df)
        assert set(result.columns) == {"open", "high", "low", "close"}

    def test_bullish_signal_on_uptrend(self):
        # Build strong uptrend with marubozu-like bars (OHLC clustered near close).
        # HA close = (O+H+L+C)/4 will be close to original high, minimising upper wick.
        rows = []
        for i in range(30):
            c = 100 + i * 5.0
            rows.append({
                "open": c - 0.5,
                "high": c + 0.1,
                "low": c - 0.5,
                "close": c,
                "volume": 1000,
            })
        df = pd.DataFrame(rows)
        result = ha_signal_bullish(df)
        assert result is True

    def test_bearish_signal_on_downtrend(self):
        # Build strong downtrend with marubozu-like bars (OHLC clustered near close).
        # HA close = (O+H+L+C)/4 will be close to original low, minimising lower wick.
        rows = []
        for i in range(30):
            c = 200 - i * 5.0
            rows.append({
                "open": c + 0.5,
                "high": c + 0.5,
                "low": c - 0.1,
                "close": c,
                "volume": 1000,
            })
        df = pd.DataFrame(rows)
        result = ha_signal_bearish(df)
        assert result is True


# ── VWAP ────────────────────────────────────────────────────────

class TestVWAP:
    def test_returns_series(self):
        df = _make_df([100 + i for i in range(20)])
        result = vwap(df)
        assert isinstance(result, pd.Series)
        assert len(result) == len(df)

    def test_vwap_between_high_low(self):
        df = _make_df([100 + i for i in range(20)])
        result = vwap(df)
        # VWAP should be between the overall low and high
        assert result.iloc[-1] >= df["low"].min()
        assert result.iloc[-1] <= df["high"].max()


# ── Volume spike ────────────────────────────────────────────────

class TestVolumeSpike:
    def test_spike_detected(self):
        # 20 bars at vol=1000, then last bar at vol=2000 (2x > 1.3x threshold)
        df = _make_df([100] * 21, volume=1000)
        df.loc[df.index[-1], "volume"] = 2000
        assert volume_spike(df)

    def test_no_spike(self):
        df = _make_df([100] * 21, volume=1000)
        assert not volume_spike(df)

    def test_reject_extreme_spike(self):
        df = _make_df([100] * 21, volume=1000)
        df.loc[df.index[-1], "volume"] = 5000  # 5x > 3x reject threshold
        assert not volume_spike(df)


# ── EMA Ribbon ──────────────────────────────────────────────────

class TestEMARibbon:
    def test_ribbon_returns_dict(self):
        df = _make_df([100 + i for i in range(20)])
        result = ema_ribbon(df)
        assert isinstance(result, dict)
        assert 5 in result
        assert 8 in result
        assert 13 in result

    def test_bullish_ribbon_on_uptrend(self):
        df = _trending_df(100, 2.0, 30)
        assert ema_ribbon_bullish(df) is True

    def test_bearish_ribbon_on_downtrend(self):
        df = _trending_df(200, -2.0, 30)
        assert ema_ribbon_bearish(df) is True

    def test_not_bullish_on_downtrend(self):
        df = _trending_df(200, -2.0, 30)
        assert ema_ribbon_bullish(df) is False
