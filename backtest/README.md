# backtest/

**Purpose**: Simulates the bot's trading logic against historical candle data to validate strategies and confluence scoring before live deployment.

## Public API

| Export | Description |
|---|---|
| `run_backtest()` | Run a full backtest on given candle data, returns `BacktestResult` |
| `BacktestResult` | Dataclass with trades, stats, and equity curve |
| `generate_candles()` | Generate synthetic OHLCV candle data for testing |

## Dependencies

- `config/` — instrument configs, scoring thresholds, risk parameters
- `indicators/` — all technical indicator calculations
- `filters/` — entry gate checks
- `scoring/` — confluence scoring
- `strategies/` — trade signal generators
- `risk/` — position sizing and drawdown tracking
