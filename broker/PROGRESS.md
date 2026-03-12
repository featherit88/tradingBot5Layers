# broker — Progress

## Done
- Full interface defined (CTraderBroker, Tick)
- All methods stubbed with logging

## In Progress
- Nothing

## Next
- Implement real cTrader Open API auth (OAuth2 flow)
- Implement ProtoOAGetTrendbarsReq for candle fetching
- Implement ProtoOASubscribeSpotsReq for live tick stream
- Implement ProtoOANewOrderReq for order execution
- Implement position modify/close via protobuf messages
- Add reconnection logic and error handling
