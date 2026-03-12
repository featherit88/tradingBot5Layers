"""Confluence scoring — trade fires only at >= 7/10."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from config import (
    MIN_CONFLUENCE_SCORE,
    SCORE_HEIKIN_ASHI,
    SCORE_MARKET_STRUCTURE,
    SCORE_SUPERTREND,
    SCORE_VOLUME_SPIKE,
    SCORE_VWAP,
)
from indicators import (
    ha_signal_bearish,
    ha_signal_bullish,
    market_structure_bearish,
    market_structure_bullish,
    supertrend,
    volume_spike,
    vwap,
)


@dataclass
class ScoreBreakdown:
    market_structure: int = 0
    supertrend_score: int = 0
    heikin_ashi: int = 0
    vwap_score: int = 0
    volume: int = 0

    @property
    def total(self) -> int:
        return (
            self.market_structure
            + self.supertrend_score
            + self.heikin_ashi
            + self.vwap_score
            + self.volume
        )

    @property
    def triggered(self) -> bool:
        return self.total >= MIN_CONFLUENCE_SCORE


def compute_confluence(
    direction: int,  # 1 = long, -1 = short
    df_5m: pd.DataFrame,
    df_3m: pd.DataFrame,
    df_1m: pd.DataFrame,
) -> ScoreBreakdown:
    """Score a potential trade across all five confluence tools."""
    score = ScoreBreakdown()

    # 1) Market structure — 5M + 3M (both must agree)
    if direction == 1:
        ms_5m = market_structure_bullish(df_5m)
        ms_3m = market_structure_bullish(df_3m)
    else:
        ms_5m = market_structure_bearish(df_5m)
        ms_3m = market_structure_bearish(df_3m)
    if ms_5m and ms_3m:
        score.market_structure = SCORE_MARKET_STRUCTURE

    # 2) Supertrend — 3M + 5M (both TFs must agree)
    st_3m = supertrend(df_3m)
    st_5m = supertrend(df_5m)
    st_dir_3m = st_3m["direction"].iloc[-1]
    st_dir_5m = st_5m["direction"].iloc[-1]
    if st_dir_3m == direction and st_dir_5m == direction:
        score.supertrend_score = SCORE_SUPERTREND

    # 3) Heikin-Ashi — 3M
    if direction == 1 and ha_signal_bullish(df_3m):
        score.heikin_ashi = SCORE_HEIKIN_ASHI
    elif direction == -1 and ha_signal_bearish(df_3m):
        score.heikin_ashi = SCORE_HEIKIN_ASHI

    # 4) VWAP — 1M (price relative to VWAP)
    vwap_series = vwap(df_1m)
    price = df_1m["close"].iloc[-1]
    vwap_val = vwap_series.iloc[-1]
    if direction == 1 and price > vwap_val:
        score.vwap_score = SCORE_VWAP
    elif direction == -1 and price < vwap_val:
        score.vwap_score = SCORE_VWAP

    # 5) Volume spike — 1M
    if volume_spike(df_1m):
        score.volume = SCORE_VOLUME_SPIKE

    return score
