"""Broker connection — cTrader Open API.

Uses the ctrader-open-api package (Twisted-based TCP/TLS + protobuf).
The Twisted reactor runs in a daemon thread so the bot's synchronous
polling loop can call broker methods normally.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime

import pandas as pd

from broker._convert import (
    price_from_api,
    price_to_api,
    volume_to_lots,
)
from broker._token import (
    DEFAULT_TOKEN_PATH,
    is_token_expired,
    load_tokens,
)

log = logging.getLogger(__name__)

# ── Timeframe mapping ────────────────────────────────────────────────
# cTrader ProtoOATrendbarPeriod enum values
_TIMEFRAME_MAP: dict[str, int] = {
    "1m": 1,   # M1
    "2m": 2,   # M2
    "3m": 3,   # M3
    "4m": 4,   # M4
    "5m": 5,   # M5
    "10m": 6,  # M10
    "15m": 7,  # M15
    "30m": 8,  # M30
    "1h": 9,   # H1
    "4h": 10,  # H4
    "12h": 11, # H12
    "1d": 12,  # D1
    "1w": 13,  # W1
}

# Connection timeout for blocking waits (seconds)
_CONNECT_TIMEOUT = 30
_REQUEST_TIMEOUT = 15


@dataclass
class Tick:
    bid: float
    ask: float
    timestamp: datetime

    @property
    def spread(self) -> float:
        return self.ask - self.bid


class CTraderBroker:
    """Wrapper around the cTrader Open API.

    Provides synchronous methods that internally communicate with
    the Twisted reactor running in a background thread.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        account_id: str,
        *,
        access_token: str | None = None,
        token_path: str = DEFAULT_TOKEN_PATH,
        demo: bool = False,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.account_id = account_id
        self._access_token = access_token
        self._token_path = token_path
        self._demo = demo
        self._connected = False

        # Internal state
        self._client = None
        self._reactor_thread: threading.Thread | None = None
        self._symbol_cache: dict[str, int] = {}   # symbol_name → symbolId
        self._symbol_digits: dict[str, int] = {}   # symbol_name → digits
        self._spot_cache: dict[str, dict] = {}      # symbol → {bid, ask}
        self._balance: float = 0.0

        # Synchronization for request/response
        self._response_events: dict[str, threading.Event] = {}
        self._response_data: dict[str, object] = {}
        self._msg_counter = 0
        self._msg_lock = threading.Lock()

    # ── Connection ───────────────────────────────────────────────

    def connect(self) -> None:
        """Authenticate and connect to cTrader Open API."""
        # Load tokens from file if no access_token provided
        if self._access_token is None:
            tokens = load_tokens(self._token_path)
            if tokens is not None and not is_token_expired(tokens):
                self._access_token = tokens.access_token
                log.info("Loaded access token from %s", self._token_path)
            else:
                log.warning(
                    "No valid access token found. Provide one via access_token param "
                    "or run exchange_token.py first."
                )

        try:
            self._start_client()
        except Exception:
            log.exception("Failed to connect to cTrader")
            self._connected = False
            return

        self._connected = True
        log.info("Connected to cTrader (account %s).", self.account_id)

    def _start_client(self) -> None:
        """Start the Twisted client in a background thread."""
        try:
            from ctrader_open_api import Client, EndPoints, TcpProtocol
        except ImportError:
            log.error(
                "ctrader-open-api package not installed. "
                "Run: pip install ctrader-open-api"
            )
            return

        host = EndPoints.PROTOBUF_DEMO_HOST if self._demo else EndPoints.PROTOBUF_LIVE_HOST
        port = EndPoints.PROTOBUF_PORT

        self._client = Client(host, port, TcpProtocol)
        self._client.setConnectedCallback(self._on_connected)
        self._client.setDisconnectedCallback(self._on_disconnected)
        self._client.setMessageReceivedCallback(self._on_message)

        # Auth event — blocks until app + account auth completes
        self._auth_event = threading.Event()

        # Start reactor in daemon thread
        self._reactor_thread = threading.Thread(
            target=self._run_reactor, daemon=True, name="ctrader-reactor",
        )
        self._reactor_thread.start()

        # Wait for auth to complete
        if not self._auth_event.wait(timeout=_CONNECT_TIMEOUT):
            log.error("cTrader auth timed out after %ds", _CONNECT_TIMEOUT)
            raise TimeoutError("cTrader authentication timed out")

    def _run_reactor(self) -> None:
        """Run Twisted reactor (blocks in background thread)."""
        from twisted.internet import reactor as _reactor

        self._client.startService()
        _reactor.run(installSignalHandlers=False)

    def _on_connected(self, client) -> None:
        """Callback when TCP connection established — send app auth."""
        log.info("TCP connected to cTrader, authenticating app…")
        from ctrader_open_api.messages.OpenApiMessages_pb2 import (
            ProtoOAApplicationAuthReq,
        )

        req = ProtoOAApplicationAuthReq()
        req.clientId = self.client_id
        req.clientSecret = self.client_secret
        client.send(req)

    def _on_disconnected(self, client, reason=None) -> None:
        """Handle disconnection — attempt reconnect."""
        was_connected = self._connected
        self._connected = False
        log.warning("Disconnected from cTrader: %s", reason)

        if was_connected:
            log.info("Will attempt reconnect in 5 seconds…")
            from twisted.internet import reactor as _reactor

            _reactor.callLater(5, self._reconnect)

    def _reconnect(self) -> None:
        """Reconnect after disconnection."""
        try:
            log.info("Reconnecting to cTrader…")
            self._client.startService()
        except Exception:
            log.exception("Reconnect failed, retrying in 10s…")
            from twisted.internet import reactor as _reactor

            _reactor.callLater(10, self._reconnect)

    def _on_message(self, client, message) -> None:
        """Central message router for all cTrader responses."""
        from ctrader_open_api import Protobuf
        from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import (
            ProtoHeartbeatEvent,
        )
        from ctrader_open_api.messages.OpenApiMessages_pb2 import (
            ProtoOAAccountAuthRes,
            ProtoOAApplicationAuthRes,
            ProtoOAClosePositionRes,
            ProtoOAErrorRes,
            ProtoOAGetTrendbarsRes,
            ProtoOANewOrderRes,
            ProtoOASpotEvent,
            ProtoOASubscribeSpotsRes,
            ProtoOASymbolByIdRes,
            ProtoOASymbolsListRes,
            ProtoOATraderRes,
        )

        payload_type = message.payloadType

        # Application auth response → send account auth
        if payload_type == ProtoOAApplicationAuthRes().payloadType:
            log.info("App auth OK — authenticating account %s…", self.account_id)
            from ctrader_open_api.messages.OpenApiMessages_pb2 import (
                ProtoOAAccountAuthReq,
            )

            req = ProtoOAAccountAuthReq()
            req.ctidTraderAccountId = int(self.account_id)
            req.accessToken = self._access_token or ""
            client.send(req)
            return

        # Account auth response → start heartbeat + cache symbols
        if payload_type == ProtoOAAccountAuthRes().payloadType:
            log.info("Account auth OK.")
            self._connected = True
            self._start_heartbeat()
            self._request_symbols()
            self._auth_event.set()
            return

        # Heartbeat — just respond
        if payload_type == ProtoHeartbeatEvent().payloadType:
            client.send(ProtoHeartbeatEvent())
            return

        # Spot price update
        if payload_type == ProtoOASpotEvent().payloadType:
            decoded = Protobuf.extract(message)
            self._handle_spot_event(decoded)
            return

        # Error response
        if payload_type == ProtoOAErrorRes().payloadType:
            decoded = Protobuf.extract(message)
            log.error(
                "cTrader error: %s (code %s, msgId=%s)",
                decoded.description, decoded.errorCode, message.clientMsgId,
            )
            self._resolve_request(message.clientMsgId, decoded)
            return

        # Symbol list response
        if payload_type == ProtoOASymbolsListRes().payloadType:
            decoded = Protobuf.extract(message)
            self._handle_symbol_list(decoded)
            self._resolve_request(message.clientMsgId, decoded)
            return

        # Symbol detail response
        if payload_type == ProtoOASymbolByIdRes().payloadType:
            decoded = Protobuf.extract(message)
            self._handle_symbol_details(decoded)
            self._resolve_request(message.clientMsgId, decoded)
            return

        # Trendbar response
        if payload_type == ProtoOAGetTrendbarsRes().payloadType:
            decoded = Protobuf.extract(message)
            self._resolve_request(message.clientMsgId, decoded)
            return

        # Trader (account) response
        if payload_type == ProtoOATraderRes().payloadType:
            decoded = Protobuf.extract(message)
            self._resolve_request(message.clientMsgId, decoded)
            return

        # Order response
        if payload_type == ProtoOANewOrderRes().payloadType:
            decoded = Protobuf.extract(message)
            self._resolve_request(message.clientMsgId, decoded)
            return

        # Close position response
        if payload_type == ProtoOAClosePositionRes().payloadType:
            decoded = Protobuf.extract(message)
            self._resolve_request(message.clientMsgId, decoded)
            return

        # Subscribe spots response (ack)
        if payload_type == ProtoOASubscribeSpotsRes().payloadType:
            decoded = Protobuf.extract(message)
            self._resolve_request(message.clientMsgId, decoded)
            return

        # Fallback: resolve any pending request
        try:
            decoded = Protobuf.extract(message)
        except Exception:
            decoded = message
        self._resolve_request(message.clientMsgId, decoded)

    # ── Heartbeat ────────────────────────────────────────────────

    def _start_heartbeat(self) -> None:
        """Send heartbeat every 10 seconds via Twisted LoopingCall."""
        from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import (
            ProtoHeartbeatEvent,
        )
        from twisted.internet import task

        def send_hb():
            if self._client is not None:
                self._client.send(ProtoHeartbeatEvent())

        self._heartbeat_loop = task.LoopingCall(send_hb)
        self._heartbeat_loop.start(10.0, now=False)

    # ── Request/response synchronization ─────────────────────────

    def _next_msg_id(self) -> str:
        with self._msg_lock:
            self._msg_counter += 1
            return f"msg_{self._msg_counter}"

    def _send_request(self, request, timeout: float = _REQUEST_TIMEOUT):
        """Send a protobuf request and block until response arrives."""
        if self._client is None:
            return None

        msg_id = self._next_msg_id()
        event = threading.Event()
        self._response_events[msg_id] = event

        from twisted.internet import reactor as _reactor

        _reactor.callFromThread(self._client.send, request, clientMsgId=msg_id)

        if not event.wait(timeout=timeout):
            log.warning("Request %s timed out after %.1fs", msg_id, timeout)
            self._response_events.pop(msg_id, None)
            return None

        self._response_events.pop(msg_id, None)
        return self._response_data.pop(msg_id, None)

    def _resolve_request(self, msg_id: str, data) -> None:
        """Unblock a waiting _send_request call."""
        if msg_id and msg_id in self._response_events:
            self._response_data[msg_id] = data
            self._response_events[msg_id].set()

    # ── Symbol management ────────────────────────────────────────

    def _request_symbols(self) -> None:
        """Request the symbol list for this account."""
        from ctrader_open_api.messages.OpenApiMessages_pb2 import (
            ProtoOASymbolsListReq,
        )

        req = ProtoOASymbolsListReq()
        req.ctidTraderAccountId = int(self.account_id)
        self._client.send(req)

    def _handle_symbol_list(self, response) -> None:
        """Cache light symbol list, then request full details."""
        symbol_ids = [s.symbolId for s in response.symbol]
        if not symbol_ids:
            log.warning("No symbols returned from cTrader.")
            return

        log.info("Received %d symbols, requesting details…", len(symbol_ids))

        from ctrader_open_api.messages.OpenApiMessages_pb2 import (
            ProtoOASymbolByIdReq,
        )

        # Request in batches of 50
        for i in range(0, len(symbol_ids), 50):
            batch = symbol_ids[i : i + 50]
            req = ProtoOASymbolByIdReq()
            req.ctidTraderAccountId = int(self.account_id)
            for sid in batch:
                req.symbolId.append(sid)
            self._client.send(req)

    def _handle_symbol_details(self, response) -> None:
        """Cache symbol name → ID and digits mapping."""
        for sym in response.symbol:
            name = sym.symbolName
            self._symbol_cache[name] = sym.symbolId
            self._symbol_digits[name] = sym.digits
        log.info("Symbol cache: %d symbols loaded.", len(self._symbol_cache))

    def _get_symbol_id(self, symbol: str) -> int | None:
        """Look up cached symbol ID by name."""
        return self._symbol_cache.get(symbol)

    def _get_digits(self, symbol: str) -> int:
        """Get decimal digits for a symbol (default 2)."""
        return self._symbol_digits.get(symbol, 2)

    # ── Spot price handling ──────────────────────────────────────

    def _handle_spot_event(self, event) -> None:
        """Update spot cache from ProtoOASpotEvent."""
        # Find symbol name by ID (reverse lookup)
        sym_id = event.symbolId
        sym_name = None
        for name, sid in self._symbol_cache.items():
            if sid == sym_id:
                sym_name = name
                break

        if sym_name is None:
            return

        digits = self._get_digits(sym_name)
        entry = self._spot_cache.get(sym_name, {"bid": 0.0, "ask": 0.0})

        if event.HasField("bid"):
            entry["bid"] = price_from_api(event.bid, digits=digits)
        if event.HasField("ask"):
            entry["ask"] = price_from_api(event.ask, digits=digits)

        self._spot_cache[sym_name] = entry

    def _subscribe_spots(self, symbol: str) -> None:
        """Subscribe to live bid/ask for a symbol."""
        sym_id = self._get_symbol_id(symbol)
        if sym_id is None:
            log.warning("Cannot subscribe spots for unknown symbol: %s", symbol)
            return

        from ctrader_open_api.messages.OpenApiMessages_pb2 import (
            ProtoOASubscribeSpotsReq,
        )

        req = ProtoOASubscribeSpotsReq()
        req.ctidTraderAccountId = int(self.account_id)
        req.symbolId.append(sym_id)
        self._send_request(req)
        log.info("Subscribed to spot prices for %s (ID %d)", symbol, sym_id)

    # ── Timeframe mapping ────────────────────────────────────────

    @staticmethod
    def _map_timeframe(tf: str) -> int | None:
        """Map string timeframe to ProtoOATrendbarPeriod enum value."""
        return _TIMEFRAME_MAP.get(tf)

    # ── Public API: disconnect ───────────────────────────────────

    def disconnect(self) -> None:
        """Disconnect from cTrader and stop the reactor."""
        self._connected = False

        if hasattr(self, "_heartbeat_loop") and self._heartbeat_loop.running:
            self._heartbeat_loop.stop()

        if self._client is not None:
            try:
                from twisted.internet import reactor as _reactor

                _reactor.callFromThread(_reactor.stop)
            except Exception:
                pass
            self._client = None

        log.info("Disconnected from cTrader.")

    # ── Public API: market data ──────────────────────────────────

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        count: int = 200,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV candles.

        Args:
            symbol: e.g. "US30" or "US500"
            timeframe: "1m", "3m", or "5m"
            count: number of bars
        Returns:
            DataFrame with columns: open, high, low, close, volume, time
        """
        empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume", "time"])

        if not self._connected or self._client is None:
            log.warning("get_candles() — not connected, returning empty DataFrame")
            return empty

        sym_id = self._get_symbol_id(symbol)
        tf_enum = self._map_timeframe(timeframe)
        if sym_id is None or tf_enum is None:
            log.warning("get_candles() — unknown symbol=%s or timeframe=%s", symbol, timeframe)
            return empty

        from ctrader_open_api.messages.OpenApiMessages_pb2 import (
            ProtoOAGetTrendbarsReq,
        )

        # cTrader wants from/to timestamps in milliseconds
        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        # Request enough history: count bars * timeframe minutes * 60s * 1000ms
        tf_minutes = {"1m": 1, "3m": 3, "5m": 5}.get(timeframe, 5)
        from_ms = now_ms - (count * tf_minutes * 60 * 1000)

        req = ProtoOAGetTrendbarsReq()
        req.ctidTraderAccountId = int(self.account_id)
        req.symbolId = sym_id
        req.period = tf_enum
        req.fromTimestamp = from_ms
        req.toTimestamp = now_ms
        req.count = count

        response = self._send_request(req)
        if response is None:
            log.warning("get_candles() — request timed out")
            return empty

        if hasattr(response, "errorCode"):
            log.error("get_candles error: %s", response.description)
            return empty

        bars = list(response.trendbar)
        digits = self._get_digits(symbol)
        return self._bars_to_dataframe(bars, digits)

    def _bars_to_dataframe(self, bars: list, digits: int = 2) -> pd.DataFrame:
        """Convert list of ProtoOATrendbar to DataFrame."""
        if not bars:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume", "time"])

        rows = []
        for bar in bars:
            low = price_from_api(bar.low, digits=digits)
            delta_open = bar.deltaOpen / 100_000 if bar.deltaOpen else 0
            delta_high = bar.deltaHigh / 100_000 if bar.deltaHigh else 0
            delta_close = bar.deltaClose / 100_000 if bar.deltaClose else 0

            rows.append({
                "open": round(low + delta_open, digits),
                "high": round(low + delta_high, digits),
                "low": low,
                "close": round(low + delta_close, digits),
                "volume": bar.volume,
                "time": datetime.fromtimestamp(
                    bar.utcTimestampInMinutes * 60, tz=UTC,
                ),
            })

        return pd.DataFrame(rows)

    def get_tick(self, symbol: str) -> Tick:
        """Get latest bid/ask from spot cache."""
        # Return cached spot if available
        if symbol in self._spot_cache:
            cached = self._spot_cache[symbol]
            return Tick(
                bid=cached["bid"],
                ask=cached["ask"],
                timestamp=datetime.now(UTC),
            )

        # If connected but no cache, subscribe and return zero
        if self._connected and self._client is not None:
            self._subscribe_spots(symbol)

        return Tick(bid=0.0, ask=0.0, timestamp=datetime.now(UTC))

    # ── Public API: order execution ──────────────────────────────

    def market_order(
        self,
        symbol: str,
        direction: int,
        volume: float,
        stop_loss: float,
        take_profit: float | None = None,
        label: str = "",
    ) -> str:
        """Send a market order. Returns order/position ID string."""
        side = "BUY" if direction == 1 else "SELL"
        log.info(
            "MARKET %s %s vol=%.2f sl=%.2f tp=%s label=%s",
            side, symbol, volume, stop_loss, take_profit, label,
        )

        if not self._connected or self._client is None:
            log.warning("market_order() — not connected, returning stub ID")
            return "stub-order-id"

        sym_id = self._get_symbol_id(symbol)
        if sym_id is None:
            log.error("market_order() — unknown symbol: %s", symbol)
            return "error-unknown-symbol"

        from ctrader_open_api.messages.OpenApiMessages_pb2 import (
            ProtoOANewOrderReq,
            ProtoOAOrderType,
            ProtoOATradeSide,
        )

        req = ProtoOANewOrderReq()
        req.ctidTraderAccountId = int(self.account_id)
        req.symbolId = sym_id
        req.orderType = ProtoOAOrderType.MARKET
        req.tradeSide = ProtoOATradeSide.BUY if direction == 1 else ProtoOATradeSide.SELL
        req.volume = volume_to_lots(volume)
        req.stopLoss = price_to_api(stop_loss)
        if take_profit is not None:
            req.takeProfit = price_to_api(take_profit)
        if label:
            req.label = label

        response = self._send_request(req)
        if response is None:
            log.error("market_order() — request timed out")
            return "error-timeout"

        if hasattr(response, "errorCode"):
            log.error("market_order() error: %s", response.description)
            return f"error-{response.errorCode}"

        # Extract position ID from the execution event
        if hasattr(response, "positionId"):
            return str(response.positionId)

        return "order-submitted"

    def modify_position(
        self,
        position_id: str,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        volume: float | None = None,
    ) -> None:
        """Modify SL/TP on an open position."""
        log.info("MODIFY %s sl=%s tp=%s vol=%s", position_id, stop_loss, take_profit, volume)

        if not self._connected or self._client is None:
            log.warning("modify_position() — not connected")
            return

        from ctrader_open_api.messages.OpenApiMessages_pb2 import (
            ProtoOAAmendPositionSLTPReq,
        )

        req = ProtoOAAmendPositionSLTPReq()
        req.ctidTraderAccountId = int(self.account_id)
        req.positionId = int(position_id)
        if stop_loss is not None:
            req.stopLoss = price_to_api(stop_loss)
        if take_profit is not None:
            req.takeProfit = price_to_api(take_profit)

        response = self._send_request(req)
        if response is not None and hasattr(response, "errorCode"):
            log.error("modify_position() error: %s", response.description)

    def close_position(self, position_id: str, volume: float | None = None) -> None:
        """Close position (fully or partially)."""
        log.info("CLOSE %s vol=%s", position_id, volume)

        if not self._connected or self._client is None:
            log.warning("close_position() — not connected")
            return

        from ctrader_open_api.messages.OpenApiMessages_pb2 import (
            ProtoOAClosePositionReq,
        )

        req = ProtoOAClosePositionReq()
        req.ctidTraderAccountId = int(self.account_id)
        req.positionId = int(position_id)
        if volume is not None:
            req.volume = volume_to_lots(volume)

        response = self._send_request(req)
        if response is not None and hasattr(response, "errorCode"):
            log.error("close_position() error: %s", response.description)

    def get_balance(self) -> float:
        """Current account balance."""
        if not self._connected or self._client is None:
            log.warning("get_balance() — not connected")
            return 0.0

        from ctrader_open_api.messages.OpenApiMessages_pb2 import (
            ProtoOATraderReq,
        )

        req = ProtoOATraderReq()
        req.ctidTraderAccountId = int(self.account_id)

        response = self._send_request(req)
        if response is None:
            return 0.0

        if hasattr(response, "errorCode"):
            log.error("get_balance() error: %s", response.description)
            return 0.0

        # Balance is in cents of deposit currency
        if hasattr(response, "trader") and hasattr(response.trader, "balance"):
            return response.trader.balance / 100.0

        return 0.0
