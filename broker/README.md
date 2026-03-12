# broker

**Purpose:** Connection to cTrader API for market data and order execution.

## Public API

| Export | Type | Description |
|---|---|---|
| `Tick` | dataclass | bid, ask, timestamp, spread property |
| `CTraderBroker` | class | Wrapper around cTrader Open API |

### CTraderBroker methods

| Method | Description |
|---|---|
| `connect()` | Authenticate and open websocket |
| `disconnect()` | Close connection |
| `get_candles(symbol, timeframe, count)` | Fetch OHLCV bars |
| `get_tick(symbol)` | Get latest bid/ask |
| `market_order(symbol, direction, volume, sl, tp, label)` | Send market order |
| `modify_position(id, sl, tp, volume)` | Modify open position |
| `close_position(id, volume)` | Close position |
| `get_balance()` | Get account balance |

## Dependencies

- None (standalone broker interface)
