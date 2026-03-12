# bot

**Purpose:** Main orchestration loop that ties all modules together.

## Public API

| Export | Type | Description |
|---|---|---|
| `ScalpingBot` | class | Main bot — connects broker, runs tick loop, evaluates instruments |

### ScalpingBot methods

| Method | Description |
|---|---|
| `run()` | Connect to broker and start the main loop |
| `stop()` | Signal the bot to shut down |

## Dependencies

- `broker` — CTraderBroker for market data and orders
- `config` — instrument configs, starting capital
- `filters` — entry filter checks
- `indicators` — ATR for trade execution
- `risk` — RiskManager and Trade
- `scoring` — confluence scoring
- `strategies` — all 4 signal generators
