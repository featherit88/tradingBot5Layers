"""Tests for the config module."""

from config import (
    DAILY_DRAWDOWN_LIMIT,
    INSTRUMENT_CONFIGS,
    MAX_OPEN_TRADES,
    MIN_CONFLUENCE_SCORE,
    PARTIAL_CLOSE_PCT,
    RISK_PER_TRADE_PCT,
    STARTING_CAPITAL,
    TRAIL_ATR_FRACTION,
    WEEKLY_DRAWDOWN_LIMIT,
    Instrument,
    Session,
)


class TestConfigValues:
    def test_risk_per_trade(self):
        assert RISK_PER_TRADE_PCT == 0.01

    def test_max_open_trades(self):
        assert MAX_OPEN_TRADES == 2

    def test_daily_drawdown(self):
        assert DAILY_DRAWDOWN_LIMIT == 0.03

    def test_weekly_drawdown(self):
        assert WEEKLY_DRAWDOWN_LIMIT == 0.06

    def test_partial_close(self):
        assert PARTIAL_CLOSE_PCT == 0.50

    def test_trail_fraction(self):
        assert TRAIL_ATR_FRACTION == 0.5

    def test_starting_capital(self):
        assert STARTING_CAPITAL == 2000.0

    def test_min_confluence(self):
        assert MIN_CONFLUENCE_SCORE == 7


class TestInstrumentConfigs:
    def test_us30_config(self):
        cfg = INSTRUMENT_CONFIGS[Instrument.US30]
        assert cfg.min_atr_5m == 0.8
        assert cfg.max_spread == 0.5
        assert cfg.stop_atr_mult == 1.2

    def test_spx_config(self):
        cfg = INSTRUMENT_CONFIGS[Instrument.SPX]
        assert cfg.min_atr_5m == 2.5
        assert cfg.max_spread == 0.4
        assert cfg.stop_atr_mult == 1.2


class TestEnums:
    def test_instruments(self):
        assert Instrument.US30.value == "US30"
        assert Instrument.SPX.value == "SPX"

    def test_sessions(self):
        assert Session.LONDON.value == "london"
        assert Session.NEW_YORK.value == "new_york"
