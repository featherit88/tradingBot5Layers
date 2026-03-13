"""Entry filters — all must pass before confluence scoring begins."""

from __future__ import annotations

from datetime import UTC, datetime, time

import pandas as pd

from config import (
    INSTRUMENT_CONFIGS,
    NEWS_BUFFER_MINUTES,
    SESSION_WINDOWS,
    VOLUME_AVG_PERIOD,
    VOLUME_FILTER_MULT,
    Instrument,
    Session,
)
from indicators import atr


def check_atr_floor(df_5m: pd.DataFrame, instrument: Instrument) -> bool:
    """ATR(14) on 5M must be above instrument minimum."""
    current_atr = atr(df_5m, 14).iloc[-1]
    return current_atr >= INSTRUMENT_CONFIGS[instrument].min_atr_5m


def check_volume_floor(df: pd.DataFrame) -> bool:
    """Volume above 1.2x 20-bar average."""
    avg = df["volume"].rolling(VOLUME_AVG_PERIOD).mean().iloc[-1]
    return df["volume"].iloc[-1] >= VOLUME_FILTER_MULT * avg


def check_spread(current_spread: float, instrument: Instrument) -> bool:
    """Spread below instrument max."""
    return current_spread <= INSTRUMENT_CONFIGS[instrument].max_spread


def check_session(now_gmt: datetime) -> Session | None:
    """Return active session or None if outside trading windows."""
    t = now_gmt.time()
    for session, (start_str, end_str) in SESSION_WINDOWS.items():
        start = time.fromisoformat(start_str)
        end = time.fromisoformat(end_str)
        if start <= t <= end:
            return session
    return None


def check_news(now_gmt: datetime, news_times: list[datetime]) -> bool:
    """True if no news event within NEWS_BUFFER_MINUTES of now."""
    if now_gmt.tzinfo is None:
        now_gmt = now_gmt.replace(tzinfo=UTC)
    for nt in news_times:
        if nt.tzinfo is None:
            nt = nt.replace(tzinfo=UTC)
        if abs((now_gmt - nt).total_seconds()) < NEWS_BUFFER_MINUTES * 60:
            return False
    return True


def all_filters_pass(
    df_5m: pd.DataFrame,
    df_1m: pd.DataFrame,
    instrument: Instrument,
    current_spread: float,
    now_gmt: datetime,
    news_times: list[datetime],
) -> tuple[bool, Session | None]:
    """Run every entry filter. Returns (passed, active_session)."""
    session = check_session(now_gmt)
    if session is None:
        return False, None
    if not check_atr_floor(df_5m, instrument):
        return False, session
    if not check_volume_floor(df_1m):
        return False, session
    if not check_spread(current_spread, instrument):
        return False, session
    if not check_news(now_gmt, news_times):
        return False, session
    return True, session
