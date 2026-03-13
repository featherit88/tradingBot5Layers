# broker

**Purpose:** Connection to cTrader API for market data and order execution.

## Public API

| Export | Type | Description |
|---|---|---|
| `Tick` | dataclass | bid, ask, timestamp, spread property |
| `CTraderBroker` | class | Wrapper around cTrader Open API |

### CTraderBroker constructor

```python
CTraderBroker(
    client_id, client_secret, account_id,
    *, access_token=None, token_path="docker/ctrader_tokens.json", demo=False,
)
```

### CTraderBroker methods

| Method | Description |
|---|---|
| `connect()` | Authenticate (app + account), start heartbeat, cache symbols |
| `disconnect()` | Stop heartbeat, stop reactor, close connection |
| `get_candles(symbol, timeframe, count)` | Fetch OHLCV bars via ProtoOAGetTrendbarsReq |
| `get_tick(symbol)` | Get latest bid/ask from spot cache (auto-subscribes) |
| `market_order(symbol, direction, volume, sl, tp, label)` | Send market order, returns position ID |
| `modify_position(id, sl, tp, volume)` | Modify SL/TP via ProtoOAAmendPositionSLTPReq |
| `close_position(id, volume)` | Close position (full or partial) |
| `get_balance()` | Get account balance via ProtoOATraderReq |

### Internal modules

| Module | Purpose |
|---|---|
| `_convert.py` | Price/volume conversion (API integers ↔ floats) |
| `_token.py` | OAuth2 token persistence (load/save/expiry check) |
| `exchange_token.py` | CLI: exchange auth code for tokens, or refresh existing tokens |

## Token setup (one-time)

```bash
docker compose -f docker/docker-compose.yml exec bot python -m broker.exchange_token
```

## Dependencies

- `ctrader-open-api>=0.9` (Twisted-based TCP/TLS + protobuf)
- `protobuf==3.20.1`
- `requests>=2.28` (for OAuth2 token exchange)
