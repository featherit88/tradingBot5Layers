"""Broker connection stub — cTrader Open API.

Replace the placeholder methods with real cTrader API calls once
your IC Markets cTrader account and API credentials are ready.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import pandas as pd

log = logging.getLogger(__name__)


@dataclass
class Tick:
    bid: float
    ask: float
    timestamp: datetime

    @property
    def spread(self) -> float:
        return self.ask - self.bid


class CTraderBroker:
    """Thin wrapper around the cTrader Open API."""

    def __init__(self, client_id: str, client_secret: str, account_id: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.account_id = account_id
        self._connected = False

    # ── Connection ───────────────────────────────────────────────

    def connect(self) -> None:
        """Authenticate and open websocket to cTrader."""
        # TODO: implement real cTrader Open API auth flow
        log.info("Connecting to cTrader (account %s)...", self.account_id)
        self._connected = True
        log.info("Connected.")

    def disconnect(self) -> None:
        self._connected = False
        log.info("Disconnected from cTrader.")

    # ── Market data ──────────────────────────────────────────────

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        count: int = 200,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV candles.

        Args:
            symbol: e.g. "US30" or "US500" (SPX)
            timeframe: "1m", "3m", or "5m"
            count: number of bars
        Returns:
            DataFrame with columns: open, high, low, close, volume, time
        """
        # TODO: replace with ProtoOAGetTrendbarsReq
        log.warning("get_candles() is a stub — returning empty DataFrame")
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume", "time"])

    def get_tick(self, symbol: str) -> Tick:
        """Get latest bid/ask."""
        # TODO: subscribe to spot prices via ProtoOASubscribeSpotsReq
        log.warning("get_tick() is a stub")
        return Tick(bid=0.0, ask=0.0, timestamp=datetime.now(UTC))

    # ── Order execution ──────────────────────────────────────────

    def market_order(
        self,
        symbol: str,
        direction: int,
        volume: float,
        stop_loss: float,
        take_profit: float | None = None,
        label: str = "",
    ) -> str:
        """Send a market order. Returns order ID string."""
        side = "BUY" if direction == 1 else "SELL"
        log.info(
            "MARKET %s %s vol=%.2f sl=%.2f tp=%s label=%s",
            side, symbol, volume, stop_loss, take_profit, label,
        )
        # TODO: ProtoOANewOrderReq
        return "stub-order-id"

    def modify_position(
        self,
        position_id: str,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        volume: float | None = None,
    ) -> None:
        """Modify SL/TP or partial close."""
        log.info("MODIFY %s sl=%s tp=%s vol=%s", position_id, stop_loss, take_profit, volume)
        # TODO: ProtoOAAmendPositionSLTPReq / ProtoOAClosePositionReq

    def close_position(self, position_id: str, volume: float | None = None) -> None:
        """Close position (fully or partially)."""
        log.info("CLOSE %s vol=%s", position_id, volume)
        # TODO: ProtoOAClosePositionReq

    def get_balance(self) -> float:
        """Current account balance."""
        # TODO: ProtoOATraderReq
        log.warning("get_balance() is a stub")
        return 0.0
