# broker — Progress

## Done
- Full interface defined (CTraderBroker, Tick)
- `_convert.py`: price/volume conversion helpers (÷100,000 for prices, ÷100,000 for volumes)
- `_token.py`: OAuth2 token load/save/refresh from JSON file with expiry checking
- `core.py`: Full CTraderBroker with Twisted reactor in background thread:
  - OAuth2 app + account authentication
  - Heartbeat every 10s via Twisted LoopingCall
  - Symbol ID + digits caching on connect
  - ProtoOAGetTrendbarsReq for candle fetching (delta-encoded OHLCV → DataFrame)
  - ProtoOASubscribeSpotsReq for live tick stream (auto-subscribe on first get_tick)
  - ProtoOANewOrderReq for market order execution
  - ProtoOAAmendPositionSLTPReq for position SL/TP modification
  - ProtoOAClosePositionReq for full/partial position close
  - ProtoOATraderReq for account balance
  - Reconnection with retry on disconnect
  - Thread-safe request/response sync (threading.Event per request)
- `exchange_token.py`: CLI script for OAuth2 code→token exchange + token refresh
- 51 unit tests (conversion, token management, broker API, candle parsing)

## In Progress
- Nothing (blocked on Spotware KYC approval)

## Next
- Rate limiting (50 req/s normal, 5 req/s historical)
- WebSocket fallback if TCP blocked
- Live integration test once credentials are active
