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


# ── Validation ──────────────────────────────────────────────────

def validate_config() -> list[str]:
    """Check all config invariants. Returns a list of error messages (empty = valid)."""
    errors: list[str] = []

    # Score sum must be reachable
    max_score = (
        SCORE_MARKET_STRUCTURE + SCORE_SUPERTREND
        + SCORE_HEIKIN_ASHI + SCORE_VWAP + SCORE_VOLUME_SPIKE
    )
    if max_score < MIN_CONFLUENCE_SCORE:
        errors.append(
            f"MIN_CONFLUENCE_SCORE ({MIN_CONFLUENCE_SCORE}) > max possible score ({max_score})"
        )

    # Risk percentages
    if RISK_PER_TRADE_PCT <= 0 or RISK_PER_TRADE_PCT > 1.0:
        errors.append(f"RISK_PER_TRADE_PCT ({RISK_PER_TRADE_PCT}) must be in (0, 1.0]")

    if DAILY_DRAWDOWN_LIMIT >= WEEKLY_DRAWDOWN_LIMIT:
        errors.append(
            f"DAILY_DRAWDOWN_LIMIT ({DAILY_DRAWDOWN_LIMIT}) must be < "
            f"WEEKLY_DRAWDOWN_LIMIT ({WEEKLY_DRAWDOWN_LIMIT})"
        )

    if PARTIAL_CLOSE_PCT <= 0 or PARTIAL_CLOSE_PCT > 1.0:
        errors.append(f"PARTIAL_CLOSE_PCT ({PARTIAL_CLOSE_PCT}) must be in (0, 1.0]")

    if STARTING_CAPITAL <= 0:
        errors.append(f"STARTING_CAPITAL ({STARTING_CAPITAL}) must be > 0")

    if MAX_OPEN_TRADES < 1:
        errors.append(f"MAX_OPEN_TRADES ({MAX_OPEN_TRADES}) must be >= 1")

    # Volume: spike threshold must be below reject threshold
    if VOLUME_SPIKE_MULT >= VOLUME_REJECT_MULT:
        errors.append(
            f"VOLUME_SPIKE_MULT ({VOLUME_SPIKE_MULT}) must be < "
            f"VOLUME_REJECT_MULT ({VOLUME_REJECT_MULT})"
        )

    # Indicator params
    if SUPERTREND_ATR_PERIOD < 1:
        errors.append(f"SUPERTREND_ATR_PERIOD ({SUPERTREND_ATR_PERIOD}) must be >= 1")

    # Completeness: every enum member must have a config/window
    for inst in Instrument:
        if inst not in INSTRUMENT_CONFIGS:
            errors.append(f"Instrument {inst.value} missing from INSTRUMENT_CONFIGS")

    for sess in Session:
        if sess not in SESSION_WINDOWS:
            errors.append(f"Session {sess.value} missing from SESSION_WINDOWS")

    return errors
