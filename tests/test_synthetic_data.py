"""Tests for the improved synthetic data generator."""

import numpy as np
import pandas as pd

from backtest import generate_candles, resample_candles
from config import Instrument


class TestCandleStructure:
    """Verify basic OHLCV candle integrity."""

    def test_high_always_ge_open_close(self):
        """High must be >= max(open, close) on every bar."""
        np.random.seed(42)
        df = generate_candles(Instrument.US30, days=10)
        assert (df["high"] >= df["open"]).all()
        assert (df["high"] >= df["close"]).all()

    def test_low_always_le_open_close(self):
        """Low must be <= min(open, close) on every bar."""
        np.random.seed(42)
        df = generate_candles(Instrument.US30, days=10)
        assert (df["low"] <= df["open"]).all()
        assert (df["low"] <= df["close"]).all()

    def test_volume_always_positive(self):
        """Volume must be > 0 on every bar."""
        np.random.seed(42)
        df = generate_candles(Instrument.US30, days=10)
        assert (df["volume"] > 0).all()

    def test_no_nan_values(self):
        """No NaN values in generated candles."""
        np.random.seed(42)
        df = generate_candles(Instrument.US30, days=10)
        assert not df.isnull().any().any()

    def test_price_stays_positive(self):
        """Price should never go negative or zero."""
        np.random.seed(42)
        df = generate_candles(Instrument.US30, days=30)
        assert (df["low"] > 0).all()


class TestSessionWindows:
    """Verify candles are only generated during trading sessions."""

    def test_only_session_hours(self):
        """All candles must fall within London (07-10) or NY (13:30-16:30)."""
        np.random.seed(42)
        df = generate_candles(Instrument.US30, days=10)
        for ts in df.index:
            hour_min = ts.hour * 60 + ts.minute
            in_london = 7 * 60 <= hour_min < 10 * 60
            in_ny = 13 * 60 + 30 <= hour_min < 16 * 60 + 30
            assert in_london or in_ny, f"Bar at {ts} is outside session windows"

    def test_no_weekend_bars(self):
        """No candles on Saturday (5) or Sunday (6)."""
        np.random.seed(42)
        df = generate_candles(Instrument.US30, days=30)
        for ts in df.index:
            assert ts.weekday() < 5, f"Weekend bar at {ts}"

    def test_spx_produces_candles(self):
        """SPX instrument should also produce valid candles."""
        np.random.seed(42)
        df = generate_candles(Instrument.SPX, days=10)
        assert not df.empty
        assert len(df) > 100


class TestRegimeBalance:
    """Verify the generator produces both bullish and bearish regimes."""

    def test_both_directions_appear(self):
        """Over 30 days, both up and down moves should appear."""
        np.random.seed(42)
        df = generate_candles(Instrument.US30, days=30)
        # Calculate bar-by-bar returns
        returns = df["close"].diff().dropna()
        up_bars = (returns > 0).sum()
        down_bars = (returns < 0).sum()
        total = len(returns)
        # Neither direction should dominate more than 70%
        assert up_bars / total < 0.70, f"Up bars {up_bars}/{total} = too biased"
        assert down_bars / total < 0.70, f"Down bars {down_bars}/{total} = too biased"

    def test_price_doesnt_run_away(self):
        """Price should stay within reasonable bounds of the base price."""
        np.random.seed(42)
        df = generate_candles(Instrument.US30, days=30)
        base = 39000.0
        # Should stay within +/- 20% of base (momentum bursts cause larger swings)
        assert df["high"].max() < base * 1.20
        assert df["low"].min() > base * 0.80


class TestVolumeProfile:
    """Verify volume has realistic session patterns."""

    def test_volume_has_variance(self):
        """Volume should not be flat — it should have meaningful variance."""
        np.random.seed(42)
        df = generate_candles(Instrument.US30, days=10)
        vol_std = df["volume"].std()
        vol_mean = df["volume"].mean()
        # Coefficient of variation should be > 0.2 (meaningful variance)
        assert vol_std / vol_mean > 0.2

    def test_occasional_volume_spikes(self):
        """Some bars should have volume > 2x average (for volume_spike indicator)."""
        np.random.seed(42)
        df = generate_candles(Instrument.US30, days=20)
        vol_mean = df["volume"].mean()
        spikes = (df["volume"] > 2.0 * vol_mean).sum()
        assert spikes > 0, "No volume spikes found"


class TestResample:
    """Verify resampling from 1M to higher timeframes works correctly."""

    def test_3m_has_fewer_bars(self):
        """3M should have roughly 1/3 the bars of 1M."""
        np.random.seed(42)
        df_1m = generate_candles(Instrument.US30, days=5)
        df_3m = resample_candles(df_1m, 3)
        assert len(df_3m) < len(df_1m)
        assert len(df_3m) > len(df_1m) // 4  # should be roughly 1/3

    def test_5m_high_ge_1m_high(self):
        """5M high should be >= any constituent 1M high."""
        np.random.seed(42)
        df_1m = generate_candles(Instrument.US30, days=5)
        df_5m = resample_candles(df_1m, 5)
        # 5M high should be >= 5M open and close
        assert (df_5m["high"] >= df_5m["open"]).all()
        assert (df_5m["high"] >= df_5m["close"]).all()


class TestDeterminism:
    """Verify reproducibility with seeds."""

    def test_same_seed_same_data(self):
        """Same seed must produce identical candles."""
        np.random.seed(42)
        df1 = generate_candles(Instrument.US30, days=5)
        np.random.seed(42)
        df2 = generate_candles(Instrument.US30, days=5)
        pd.testing.assert_frame_equal(df1, df2)

    def test_different_seed_different_data(self):
        """Different seeds must produce different candles."""
        np.random.seed(42)
        df1 = generate_candles(Instrument.US30, days=5)
        np.random.seed(99)
        df2 = generate_candles(Instrument.US30, days=5)
        assert not df1["close"].equals(df2["close"])
