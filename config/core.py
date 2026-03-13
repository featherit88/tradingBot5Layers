"""All bot configuration — mirrors CLAUDE.md spec exactly."""

from dataclasses import dataclass
from enum import Enum


class Instrument(Enum):
    US30 = "US30"
    SPX = "SPX"


class Session(Enum):
    LONDON = "london"
    NEW_YORK = "new_york"


# Session windows in GMT
SESSION_WINDOWS = {
    Session.LONDON: ("07:00", "10:00"),
    Session.NEW_YORK: ("13:30", "16:30"),
}


@dataclass(frozen=True)
class InstrumentConfig:
    min_atr_5m: float          # ATR(14) floor on 5M
    max_spread: float          # max spread in points
    stop_atr_mult: float       # SL = multiplier * ATR14


INSTRUMENT_CONFIGS = {
    Instrument.US30: InstrumentConfig(min_atr_5m=0.8, max_spread=0.5, stop_atr_mult=1.2),
    Instrument.SPX:  InstrumentConfig(min_atr_5m=2.5, max_spread=0.4, stop_atr_mult=1.2),
}


# ── Confluence scoring thresholds ────────────────────────────────
SCORE_MARKET_STRUCTURE = 3
SCORE_SUPERTREND = 2
SCORE_HEIKIN_ASHI = 2
SCORE_VWAP = 1
SCORE_VOLUME_SPIKE = 1
MIN_CONFLUENCE_SCORE = 7   # out of 10

# ── Indicator parameters ─────────────────────────────────────────
SUPERTREND_ATR_PERIOD = 10
SUPERTREND_MULTIPLIER = 2.0

EMA_PERIODS = (5, 8, 13)                # EMA ribbon

FRACTAL_BARS = 3                         # market-structure fractal
MIN_SWING_PCT = 0.0015                   # 0.15 %

HEIKIN_ASHI_CANDLES = 3
HEIKIN_ASHI_MAX_WICK_PCT = 0.15

VWAP_NY_ANCHOR_GMT = "13:30"
VWAP_VALID_AFTER_GMT = "14:00"

VOLUME_SPIKE_MULT = 1.3
VOLUME_AVG_PERIOD = 20
VOLUME_REJECT_MULT = 3.0
VOLUME_FILTER_MULT = 1.2                # entry-filter level

# ── Risk management ──────────────────────────────────────────────
RISK_PER_TRADE_PCT = 0.01               # 1 %
MAX_OPEN_TRADES = 2
DAILY_DRAWDOWN_LIMIT = 0.03             # 3 %
WEEKLY_DRAWDOWN_LIMIT = 0.06            # 6 %
PARTIAL_CLOSE_PCT = 0.50                # close 50 % at 1R
TRAIL_ATR_FRACTION = 0.5                # trail stop follows at 0.5 * ATR behind best price

STARTING_CAPITAL = 2000.0               # EUR

# ── Opening-range breakout ───────────────────────────────────────
ORB_MINUTES = 15                        # first 15-min range

# ── News filter ──────────────────────────────────────────────────
NEWS_BUFFER_MINUTES = 15
