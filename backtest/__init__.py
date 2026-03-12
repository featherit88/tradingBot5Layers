"""Backtesting engine for strategy validation."""

from backtest.core import (
    BacktestResult,
    TradeRecord,
    generate_candles,
    resample_candles,
    run_backtest,
)

__all__ = [
    "BacktestResult",
    "TradeRecord",
    "generate_candles",
    "resample_candles",
    "run_backtest",
]
