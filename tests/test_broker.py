"""Tests for CTraderBroker — mocked cTrader client."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from broker import CTraderBroker, Tick


class TestTick:
    def test_spread(self):
        t = Tick(bid=39500.0, ask=39500.3, timestamp=datetime.now(UTC))
        assert abs(t.spread - 0.3) < 1e-9

    def test_zero_spread(self):
        t = Tick(bid=100.0, ask=100.0, timestamp=datetime.now(UTC))
        assert t.spread == 0.0


class TestBrokerInit:
    def test_init_stores_credentials(self):
        b = CTraderBroker(
            client_id="cid",
            client_secret="csec",
            account_id="12345",
        )
        assert b.client_id == "cid"
        assert b.client_secret == "csec"
        assert b.account_id == "12345"
        assert b._connected is False

    def test_init_with_access_token(self):
        b = CTraderBroker(
            client_id="cid",
            client_secret="csec",
            account_id="12345",
            access_token="tok",
        )
        assert b._access_token == "tok"

    def test_init_defaults(self):
        b = CTraderBroker(
            client_id="cid",
            client_secret="csec",
            account_id="12345",
        )
        assert b._access_token is None
        assert b._symbol_cache == {}
        assert b._spot_cache == {}


class TestBrokerDisconnect:
    def test_disconnect_sets_flag(self):
        b = CTraderBroker("c", "s", "a")
        b._connected = True
        b.disconnect()
        assert b._connected is False


class TestBrokerGetCandlesEmpty:
    """When not connected, get_candles returns empty DataFrame."""

    def test_returns_empty_when_not_connected(self):
        b = CTraderBroker("c", "s", "a")
        df = b.get_candles("US30", "1m", 200)
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_returns_expected_columns(self):
        b = CTraderBroker("c", "s", "a")
        df = b.get_candles("US30", "1m")
        expected = {"open", "high", "low", "close", "volume", "time"}
        assert set(df.columns) == expected


class TestBrokerGetTickFallback:
    """When not connected, get_tick returns zero tick."""

    def test_returns_zero_tick(self):
        b = CTraderBroker("c", "s", "a")
        tick = b.get_tick("US30")
        assert tick.bid == 0.0
        assert tick.ask == 0.0

    def test_returns_tick_from_spot_cache(self):
        b = CTraderBroker("c", "s", "a")
        b._connected = True
        b._spot_cache["US30"] = {"bid": 39500.0, "ask": 39500.3}
        tick = b.get_tick("US30")
        assert tick.bid == 39500.0
        assert tick.ask == 39500.3


class TestBrokerMarketOrderNotConnected:
    """When not connected, market_order returns stub ID."""

    def test_returns_stub_id(self):
        b = CTraderBroker("c", "s", "a")
        result = b.market_order("US30", 1, 0.1, 39400.0)
        assert result == "stub-order-id"


class TestBrokerGetBalanceNotConnected:
    def test_returns_zero(self):
        b = CTraderBroker("c", "s", "a")
        assert b.get_balance() == 0.0


class TestBrokerSymbolCache:
    """Test symbol ID lookup from cache."""

    def test_get_symbol_id_from_cache(self):
        b = CTraderBroker("c", "s", "a")
        b._symbol_cache = {"US30": 12345, "US500": 67890}
        assert b._get_symbol_id("US30") == 12345
        assert b._get_symbol_id("US500") == 67890

    def test_get_symbol_id_missing(self):
        b = CTraderBroker("c", "s", "a")
        b._symbol_cache = {"US30": 12345}
        assert b._get_symbol_id("EURUSD") is None


class TestBrokerTimeframeMapping:
    def test_known_timeframes(self):
        b = CTraderBroker("c", "s", "a")
        assert b._map_timeframe("1m") is not None
        assert b._map_timeframe("3m") is not None
        assert b._map_timeframe("5m") is not None

    def test_unknown_timeframe_returns_none(self):
        b = CTraderBroker("c", "s", "a")
        assert b._map_timeframe("99m") is None


class TestBrokerBuildCandleDf:
    """Test candle response → DataFrame conversion."""

    def test_empty_bars_returns_empty_df(self):
        b = CTraderBroker("c", "s", "a")
        df = b._bars_to_dataframe([], digits=1)
        assert df.empty
        assert set(df.columns) == {"open", "high", "low", "close", "volume", "time"}

    def test_single_bar_conversion(self):
        b = CTraderBroker("c", "s", "a")
        # Simulate a trendbar: low=39500.0 (API: 3950000000)
        # deltaOpen=50000 (0.5), deltaHigh=100000 (1.0), deltaClose=75000 (0.75)
        bar = MagicMock()
        bar.low = 3950000000
        bar.deltaOpen = 50000
        bar.deltaHigh = 100000
        bar.deltaClose = 75000
        bar.volume = 150000  # in lots * 100
        bar.utcTimestampInMinutes = 29580000  # some timestamp

        df = b._bars_to_dataframe([bar], digits=1)
        assert len(df) == 1
        assert df.iloc[0]["low"] == 39500.0
        assert df.iloc[0]["open"] == 39500.5
        assert df.iloc[0]["high"] == 39501.0
        assert df.iloc[0]["close"] == pytest.approx(39500.75, abs=0.1)
