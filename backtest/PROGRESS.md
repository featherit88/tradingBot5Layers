# backtest/ — Progress

## Done
- Module structure created
- Synthetic candle generator
- Walk-forward backtesting engine
- Performance stats output (win rate, PnL, drawdown, Sharpe, etc.)
- Improved synthetic data generator with realistic market patterns:
  - U-shaped volatility and volume profiles within sessions
  - Balanced regime switching (trend/momentum/consolidation phases)
  - Opening range consolidation + breakout dynamics
  - Session gaps between London and NY
  - Momentum bursts to flip supertrend indicators
- Fixed supertrend NaN carry-forward bug (indicator never flipped bearish)
- Both LONG and SHORT trades now generated across all seeds
- CLI improvements: argparse with --days, --seed, --capital, --json, --no-trades, --log-level (12 tests)

## In Progress
- None

## Next
- CSV import for real historical data (once broker API is live)
- Multi-instrument concurrent backtesting
- Parameter optimization / grid search
