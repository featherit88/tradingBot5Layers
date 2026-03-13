"""Tests for the filters module."""

from datetime import datetime, time, timedelta, timezone

import pandas as pd
import pytest

from config import Instrument, Session
from filters.core import (
    check_atr_floor,
    check_news,
    check_session,
    check_spread,
    check_volume_floor,
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


# ── ATR floor ──────────────────────────────────────────────────

class TestATRFloor:
    def test_passes_high_atr(self):
        # Wide range candles → high ATR
        prices = [100 + i * 5 for i in range(20)]
        df = _make_df(prices)
        assert check_atr_floor(df, Instrument.US30)

    def test_fails_low_atr(self):
        # Very tight range: high-low = 0.2 → ATR ≈ 0.2, below SPX threshold of 2.5
        rows = [{"open": 100, "high": 100.1, "low": 99.9, "close": 100, "volume": 1000}] * 20
        df = pd.DataFrame(rows)
        assert not check_atr_floor(df, Instrument.SPX)


# ── Volume floor ────────────────────────────────────────────────

class TestVolumeFloor:
    def test_passes_high_volume(self):
        df = _make_df([100] * 21, volume=1000)
        df.loc[df.index[-1], "volume"] = 1500  # 1.5x > 1.2x threshold
        assert check_volume_floor(df)

    def test_fails_low_volume(self):
        df = _make_df([100] * 21, volume=1000)
        df.loc[df.index[-1], "volume"] = 800  # 0.8x < 1.2x
        assert not check_volume_floor(df)


# ── Spread ──────────────────────────────────────────────────────

class TestSpread:
    def test_passes_within_limit(self):
        assert check_spread(0.3, Instrument.US30) is True  # 0.3 < 0.5

    def test_fails_above_limit(self):
        assert check_spread(0.6, Instrument.US30) is False  # 0.6 > 0.5

    def test_spx_tighter_limit(self):
        assert check_spread(0.35, Instrument.SPX) is True   # 0.35 < 0.4
        assert check_spread(0.45, Instrument.SPX) is False  # 0.45 > 0.4


# ── Session ─────────────────────────────────────────────────────

class TestSession:
    def test_london_session(self):
        now = datetime(2026, 3, 13, 8, 0, tzinfo=timezone.utc)  # 08:00 GMT
        result = check_session(now)
        assert result == Session.LONDON

    def test_ny_session(self):
        now = datetime(2026, 3, 13, 14, 0, tzinfo=timezone.utc)  # 14:00 GMT
        result = check_session(now)
        assert result == Session.NEW_YORK

    def test_outside_sessions(self):
        now = datetime(2026, 3, 13, 12, 0, tzinfo=timezone.utc)  # 12:00 GMT
        result = check_session(now)
        assert result is None

    def test_session_boundary_start(self):
        now = datetime(2026, 3, 13, 7, 0, tzinfo=timezone.utc)
        assert check_session(now) == Session.LONDON

    def test_session_boundary_end(self):
        now = datetime(2026, 3, 13, 10, 0, tzinfo=timezone.utc)
        assert check_session(now) == Session.LONDON


# ── News buffer ─────────────────────────────────────────────────

class TestNewsBuffer:
    def test_no_news_passes(self):
        now = datetime(2026, 3, 13, 14, 0, tzinfo=timezone.utc)
        assert check_news(now, []) is True

    def test_news_within_buffer_blocks(self):
        now = datetime(2026, 3, 13, 14, 0, tzinfo=timezone.utc)
        news = [now + timedelta(minutes=10)]  # 10 min away < 15 min buffer
        assert check_news(now, news) is False

    def test_news_outside_buffer_passes(self):
        now = datetime(2026, 3, 13, 14, 0, tzinfo=timezone.utc)
        news = [now + timedelta(minutes=20)]  # 20 min away > 15 min buffer
        assert check_news(now, news) is True

    def test_past_news_within_buffer_blocks(self):
        now = datetime(2026, 3, 13, 14, 0, tzinfo=timezone.utc)
        news = [now - timedelta(minutes=10)]  # 10 min ago < 15 min buffer
        assert check_news(now, news) is False
