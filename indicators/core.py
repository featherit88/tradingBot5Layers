"""Technical indicator calculations used by the confluence system."""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import (
    EMA_PERIODS,
    FRACTAL_BARS,
    HEIKIN_ASHI_CANDLES,
    HEIKIN_ASHI_MAX_WICK_PCT,
    MIN_SWING_PCT,
    SUPERTREND_ATR_PERIOD,
    SUPERTREND_MULTIPLIER,
    VOLUME_AVG_PERIOD,
    VOLUME_REJECT_MULT,
    VOLUME_SPIKE_MULT,
)

# ── ATR ──────────────────────────────────────────────────────────

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range."""
    high, low, close = df["high"], df["low"], df["close"]
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


# ── Supertrend ───────────────────────────────────────────────────

def supertrend(
    df: pd.DataFrame,
    atr_period: int = SUPERTREND_ATR_PERIOD,
    multiplier: float = SUPERTREND_MULTIPLIER,
) -> pd.DataFrame:
    """Return DataFrame with columns: supertrend, direction (1=bull, -1=bear)."""
    atr_vals = atr(df, atr_period)
    hl2 = (df["high"] + df["low"]) / 2

    upper = (hl2 + multiplier * atr_vals).values.copy()
    lower = (hl2 - multiplier * atr_vals).values.copy()
    close = df["close"].values

    st_dir = np.ones(len(df), dtype=int)
    st_val = np.empty(len(df))
    st_val[:] = np.nan

    for i in range(1, len(df)):
        # carry forward tighter bands
        if not (lower[i] > lower[i - 1] or close[i - 1] < lower[i - 1]):
            lower[i] = lower[i - 1]

        if not (upper[i] < upper[i - 1] or close[i - 1] > upper[i - 1]):
            upper[i] = upper[i - 1]

        if st_dir[i - 1] == 1:
            st_dir[i] = -1 if close[i] < lower[i] else 1
        else:
            st_dir[i] = 1 if close[i] > upper[i] else -1

        st_val[i] = lower[i] if st_dir[i] == 1 else upper[i]

    return pd.DataFrame({"supertrend": st_val, "direction": st_dir}, index=df.index)


# ── Market Structure (HH/HL or LL/LH) ───────────────────────────

def _swing_points(series: pd.Series, bars: int = FRACTAL_BARS, mode: str = "high") -> list[tuple[int, float]]:
    """Detect fractal swing points. Returns list of (index_pos, value)."""
    swings = []
    for i in range(bars, len(series) - bars):
        window = series.iloc[i - bars : i + bars + 1]
        val = series.iloc[i]
        if (mode == "high" and val == window.max()) or (mode == "low" and val == window.min()):
            swings.append((i, val))
    return swings


def market_structure_bullish(df: pd.DataFrame) -> bool:
    """True if latest structure shows Higher-High + Higher-Low (close confirmation)."""
    highs = _swing_points(df["high"], mode="high")
    lows = _swing_points(df["low"], mode="low")
    if len(highs) < 2 or len(lows) < 2:
        return False
    last_close = df["close"].iloc[-1]
    if last_close == 0 or pd.isna(last_close):
        return False
    hh = highs[-1][1] > highs[-2][1]
    hl = lows[-1][1] > lows[-2][1]
    swing_size = abs(highs[-1][1] - lows[-1][1]) / last_close
    return hh and hl and swing_size >= MIN_SWING_PCT


def market_structure_bearish(df: pd.DataFrame) -> bool:
    """True if latest structure shows Lower-Low + Lower-High."""
    highs = _swing_points(df["high"], mode="high")
    lows = _swing_points(df["low"], mode="low")
    if len(highs) < 2 or len(lows) < 2:
        return False
    last_close = df["close"].iloc[-1]
    if last_close == 0 or pd.isna(last_close):
        return False
    ll = lows[-1][1] < lows[-2][1]
    lh = highs[-1][1] < highs[-2][1]
    swing_size = abs(highs[-1][1] - lows[-1][1]) / last_close
    return ll and lh and swing_size >= MIN_SWING_PCT


# ── Heikin-Ashi ──────────────────────────────────────────────────

def heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """Convert OHLC to Heikin-Ashi candles."""
    ha_close = (df["open"] + df["high"] + df["low"] + df["close"]) / 4

    ha_open = np.empty(len(df))
    ha_open[0] = (df["open"].iloc[0] + df["close"].iloc[0]) / 2
    for i in range(1, len(df)):
        ha_open[i] = (ha_open[i - 1] + ha_close.iloc[i - 1]) / 2

    ha = pd.DataFrame({
        "open": ha_open,
        "close": ha_close.values,
    }, index=df.index)
    ha["high"] = np.maximum(np.maximum(ha["open"], ha["close"]), df["high"].values)
    ha["low"] = np.minimum(np.minimum(ha["open"], ha["close"]), df["low"].values)
    return ha


def ha_signal_bullish(df: pd.DataFrame, n: int = HEIKIN_ASHI_CANDLES) -> bool:
    """Last n HA candles are bullish (close > open, small upper wick, not doji)."""
    ha = heikin_ashi(df)
    tail = ha.iloc[-n:]
    for _, c in tail.iterrows():
        if c["close"] <= c["open"]:
            return False
        body = abs(c["close"] - c["open"])
        if body == 0:
            return False  # doji
        upper_wick = c["high"] - max(c["open"], c["close"])
        if upper_wick / body > HEIKIN_ASHI_MAX_WICK_PCT:
            return False
    return True


def ha_signal_bearish(df: pd.DataFrame, n: int = HEIKIN_ASHI_CANDLES) -> bool:
    """Last n HA candles are bearish."""
    ha = heikin_ashi(df)
    tail = ha.iloc[-n:]
    for _, c in tail.iterrows():
        if c["close"] >= c["open"]:
            return False
        body = abs(c["close"] - c["open"])
        if body == 0:
            return False
        lower_wick = min(c["open"], c["close"]) - c["low"]
        if lower_wick / body > HEIKIN_ASHI_MAX_WICK_PCT:
            return False
    return True


# ── VWAP ─────────────────────────────────────────────────────────

def vwap(df: pd.DataFrame) -> pd.Series:
    """Session VWAP. Expects df already sliced to session start."""
    typical = (df["high"] + df["low"] + df["close"]) / 3
    cum_tp_vol = (typical * df["volume"]).cumsum()
    cum_vol = df["volume"].cumsum()
    cum_vol = cum_vol.replace(0, float("nan"))
    return cum_tp_vol / cum_vol


# ── Volume spike ─────────────────────────────────────────────────

def volume_spike(
    df: pd.DataFrame,
    mult: float = VOLUME_SPIKE_MULT,
    period: int = VOLUME_AVG_PERIOD,
) -> bool:
    """True if latest bar volume >= mult * average, and not > reject threshold."""
    avg = df["volume"].rolling(period).mean().iloc[-1]
    cur = df["volume"].iloc[-1]
    return cur >= mult * avg and cur <= VOLUME_REJECT_MULT * avg


# ── EMA Ribbon ───────────────────────────────────────────────────

def ema_ribbon(df: pd.DataFrame, periods: tuple[int, ...] = EMA_PERIODS) -> dict[int, pd.Series]:
    """Return dict of EMA series keyed by period."""
    return {p: df["close"].ewm(span=p, adjust=False).mean() for p in periods}


def ema_ribbon_bullish(df: pd.DataFrame) -> bool:
    """5 > 8 > 13 EMA stack on latest bar."""
    ribbon = ema_ribbon(df)
    periods = sorted(ribbon.keys())
    vals = [ribbon[p].iloc[-1] for p in periods]
    return all(vals[i] > vals[i + 1] for i in range(len(vals) - 1))


def ema_ribbon_bearish(df: pd.DataFrame) -> bool:
    """5 < 8 < 13 EMA stack."""
    ribbon = ema_ribbon(df)
    periods = sorted(ribbon.keys())
    vals = [ribbon[p].iloc[-1] for p in periods]
    return all(vals[i] < vals[i + 1] for i in range(len(vals) - 1))
