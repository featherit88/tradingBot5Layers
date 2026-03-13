"""Four scalping strategies — each returns a direction (1/-1) or 0 (no signal)."""

from __future__ import annotations

import pandas as pd

from config import ORB_MINUTES
from indicators import (
    ema_ribbon,
    ema_ribbon_bearish,
    ema_ribbon_bullish,
    vwap,
)


def ema_ribbon_scalp(df_1m: pd.DataFrame) -> int:
    """Strategy 1: EMA Ribbon Scalp (1M).
    5/8/13 EMA stack, enter on pullback to 8 EMA.
    """
    if df_1m.empty:
        return 0
    if ema_ribbon_bullish(df_1m):
        ribbon = ema_ribbon(df_1m)
        low = df_1m["low"].iloc[-1]
        ema8 = ribbon[8].iloc[-1]
        if low <= ema8:  # price pulled back to 8 EMA
            return 1
    elif ema_ribbon_bearish(df_1m):
        ribbon = ema_ribbon(df_1m)
        high = df_1m["high"].iloc[-1]
        ema8 = ribbon[8].iloc[-1]
        if high >= ema8:
            return -1
    return 0


def vwap_reversion(df_3m: pd.DataFrame) -> int:
    """Strategy 2: VWAP Reversion (3M).
    Fade overextension from VWAP, TP at VWAP reclaim.
    """
    if df_3m.empty:
        return 0
    vwap_series = vwap(df_3m)
    price = df_3m["close"].iloc[-1]
    vwap_val = vwap_series.iloc[-1]
    if pd.isna(vwap_val) or vwap_val == 0:
        return 0

    deviation = (price - vwap_val) / vwap_val

    # overextended above VWAP → short (fade)
    if deviation > 0.002:
        return -1
    # overextended below VWAP → long (fade)
    if deviation < -0.002:
        return 1
    return 0


def break_and_retest(df_5m: pd.DataFrame, df_1m: pd.DataFrame) -> int:
    """Strategy 3: Break & Retest (5M).
    Structure break on 5M, wait for retest, enter with volume.
    """
    if len(df_5m) < 10:
        return 0
    if df_1m.empty:
        return 0

    # Simple structure break: latest close beyond previous swing
    prev_high = df_5m["high"].iloc[-3:-1].max()
    prev_low = df_5m["low"].iloc[-3:-1].min()
    close = df_5m["close"].iloc[-1]

    # Bullish: previous bar broke above the prior swing high,
    # current bar retests (low touches level but close stays above)
    prev_bar_broke = df_5m["close"].iloc[-2] > prev_high
    current_retests = df_5m["low"].iloc[-1] <= prev_high and close > prev_high
    if prev_bar_broke and current_retests:
        return 1

    # Bearish: previous bar broke below the prior swing low,
    # current bar retests (high touches level but close stays below)
    prev_bar_broke = df_5m["close"].iloc[-2] < prev_low
    current_retests = df_5m["high"].iloc[-1] >= prev_low and close < prev_low
    if prev_bar_broke and current_retests:
        return -1

    return 0


def opening_range_breakout(
    df_1m: pd.DataFrame,
    session_bar_count: int,
) -> int:
    """Strategy 4: Opening Range Breakout.
    First 15-min range at London/NY open.
    """
    if session_bar_count < ORB_MINUTES:
        return 0  # still forming the range

    end_idx = len(df_1m) - session_bar_count + ORB_MINUTES
    start_idx = len(df_1m) - session_bar_count
    orb_slice = df_1m.iloc[start_idx:end_idx]
    if len(orb_slice) < ORB_MINUTES:
        return 0

    orb_high = orb_slice["high"].max()
    orb_low = orb_slice["low"].min()
    price = df_1m["close"].iloc[-1]

    if price > orb_high:
        return 1
    if price < orb_low:
        return -1
    return 0
