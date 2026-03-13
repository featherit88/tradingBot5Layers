# bot — Progress

## Done
- ScalpingBot with main tick loop
- Instrument evaluation pipeline: filters → strategies → scoring → execution
- Open trade management: partial close at 1R, stop loss monitoring
- Trailing stop: after partial close, trail remaining 50% at 0.5 * ATR behind best price
- Day/week reset scheduling (automatic via `_check_resets`)
- Graceful shutdown with SIGINT/SIGTERM handling and position cleanup
- Trade logging to MySQL (TradeLogger in `bot/db.py`)
- Daily summary table written on day reset and shutdown
- MySQL trade logging tests: 18 tests covering connect/disconnect, trade open/close, partial close, daily summary upsert, error resilience, full lifecycle

## In Progress
- Nothing

## Next
- Performance logging / trade journal output
