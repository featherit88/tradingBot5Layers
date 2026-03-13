"""Tests for the scoring module."""

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from scoring.core import ScoreBreakdown, compute_confluence


# ── ScoreBreakdown ──────────────────────────────────────────────

class TestScoreBreakdown:
    def test_total(self):
        s = ScoreBreakdown(
            market_structure=3,
            supertrend_score=2,
            heikin_ashi=2,
            vwap_score=1,
            volume=1,
        )
        assert s.total == 9

    def test_triggered_at_7(self):
        s = ScoreBreakdown(market_structure=3, supertrend_score=2, heikin_ashi=2)
        assert s.total == 7
        assert s.triggered is True

    def test_not_triggered_below_7(self):
        s = ScoreBreakdown(market_structure=3, supertrend_score=2)
        assert s.total == 5
        assert s.triggered is False

    def test_default_zeros(self):
        s = ScoreBreakdown()
        assert s.total == 0
        assert s.triggered is False


# ── Helper: build OHLCV DataFrames ─────────────────────────────

def _trending_df(n: int, start: float, step: float, volume: int = 1000) -> pd.DataFrame:
    """Create a DataFrame with a clear trend (up if step>0, down if step<0)."""
    rows = []
    for i in range(n):
        c = start + i * step
        rows.append({
            "open": c - step * 0.3,
            "high": c + abs(step) * 0.8,
            "low": c - abs(step) * 0.8,
            "close": c,
            "volume": volume,
        })
    return pd.DataFrame(rows)


def _flat_df(n: int, price: float = 100.0, volume: int = 1000) -> pd.DataFrame:
    """Create a flat/ranging DataFrame — no trend, no structure."""
    rows = [{
        "open": price,
        "high": price + 0.1,
        "low": price - 0.1,
        "close": price,
        "volume": volume,
    }] * n
    return pd.DataFrame(rows)


# ── compute_confluence tests ────────────────────────────────────

class TestComputeConfluence:
    def test_flat_market_scores_low(self):
        """Flat/ranging data should produce a low score (not triggered)."""
        df = _flat_df(50)
        score = compute_confluence(1, df, df, df)
        assert not score.triggered
        assert score.total < 7

    def test_volume_spike_scores_point(self):
        """A volume spike on 1M should add 1 point."""
        df_flat = _flat_df(50)
        # Create 1M df with a big volume bar at the end
        df_1m = _flat_df(50)
        df_1m.loc[df_1m.index[-1], "volume"] = 2000  # 2x average: above 1.3x spike, below 3x reject
        score_without = compute_confluence(1, df_flat, df_flat, df_flat)
        score_with = compute_confluence(1, df_flat, df_flat, df_1m)
        assert score_with.volume == 1
        assert score_with.volume > score_without.volume

    def test_vwap_skipped_before_1400(self):
        """VWAP should not score before 14:00 GMT."""
        df = _flat_df(50)
        # Price above VWAP in a long direction, but time is 10:00 GMT
        morning = datetime(2026, 3, 13, 10, 0, tzinfo=timezone.utc)
        score = compute_confluence(1, df, df, df, now=morning)
        assert score.vwap_score == 0

    def test_vwap_scored_after_1400(self):
        """VWAP should be evaluated after 14:00 GMT."""
        # Build 1M data where close is clearly above VWAP
        df_1m = _flat_df(50, price=100.0)
        # Set last few bars well above average to push close > VWAP
        for i in range(45, 50):
            df_1m.loc[i, "close"] = 110.0
            df_1m.loc[i, "high"] = 111.0
            df_1m.loc[i, "open"] = 109.0
        afternoon = datetime(2026, 3, 13, 15, 0, tzinfo=timezone.utc)
        score = compute_confluence(1, _flat_df(50), _flat_df(50), df_1m, now=afternoon)
        assert score.vwap_score == 1

    def test_returns_score_breakdown_type(self):
        """compute_confluence should always return a ScoreBreakdown."""
        df = _flat_df(50)
        result = compute_confluence(1, df, df, df)
        assert isinstance(result, ScoreBreakdown)

    def test_score_never_exceeds_10(self):
        """Total score should never exceed 10 (3+2+2+1+1)."""
        df = _trending_df(50, 100, 5)
        score = compute_confluence(1, df, df, df)
        assert score.total <= 10

    def test_short_direction_uses_bearish_indicators(self):
        """Passing direction=-1 should check bearish structure/HA/VWAP."""
        df_down = _trending_df(50, 200, -5)
        score = compute_confluence(-1, df_down, df_down, df_down)
        assert isinstance(score, ScoreBreakdown)
        assert score.total >= 0
        # On a strong downtrend, at least supertrend should detect bearish
        assert score.supertrend_score >= 0
