"""Tests for the config module."""

from unittest.mock import patch

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
    validate_config,
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


# ---------------------------------------------------------------------------
# validate_config()
# ---------------------------------------------------------------------------

class TestValidateConfig:
    """Tests for the validate_config() startup check."""

    def test_current_config_is_valid(self):
        """The shipped config must pass validation without errors."""
        errors = validate_config()
        assert errors == []

    def test_scores_cannot_exceed_max(self):
        """MIN_CONFLUENCE_SCORE must be <= sum of all score components."""
        with patch("config.core.MIN_CONFLUENCE_SCORE", 15):
            errors = validate_config()
        assert any("confluence" in e.lower() for e in errors)

    def test_daily_drawdown_must_be_less_than_weekly(self):
        """Daily drawdown limit must be < weekly drawdown limit."""
        with patch("config.core.DAILY_DRAWDOWN_LIMIT", 0.10):
            errors = validate_config()
        assert any("daily" in e.lower() and "weekly" in e.lower() for e in errors)

    def test_risk_per_trade_must_be_positive(self):
        """Risk per trade must be > 0."""
        with patch("config.core.RISK_PER_TRADE_PCT", 0.0):
            errors = validate_config()
        assert any("risk_per_trade" in e.lower() for e in errors)

    def test_risk_per_trade_must_be_at_most_100pct(self):
        """Risk per trade must be <= 1.0."""
        with patch("config.core.RISK_PER_TRADE_PCT", 1.5):
            errors = validate_config()
        assert any("risk_per_trade" in e.lower() for e in errors)

    def test_partial_close_between_0_and_1(self):
        """Partial close pct must be in (0, 1]."""
        with patch("config.core.PARTIAL_CLOSE_PCT", 0.0):
            errors = validate_config()
        assert any("partial_close" in e.lower() for e in errors)

    def test_starting_capital_must_be_positive(self):
        """Starting capital must be > 0."""
        with patch("config.core.STARTING_CAPITAL", -100.0):
            errors = validate_config()
        assert any("starting_capital" in e.lower() for e in errors)

    def test_volume_spike_must_be_less_than_reject(self):
        """Volume spike multiplier must be < reject multiplier."""
        with patch("config.core.VOLUME_SPIKE_MULT", 5.0):
            errors = validate_config()
        assert any("volume" in e.lower() for e in errors)

    def test_every_instrument_has_config(self):
        """Every Instrument enum member must have an InstrumentConfig."""
        with patch("config.core.INSTRUMENT_CONFIGS", {}):
            errors = validate_config()
        assert any("instrument" in e.lower() for e in errors)

    def test_every_session_has_window(self):
        """Every Session enum member must have a window in SESSION_WINDOWS."""
        with patch("config.core.SESSION_WINDOWS", {}):
            errors = validate_config()
        assert any("session" in e.lower() for e in errors)

    def test_max_open_trades_positive(self):
        """MAX_OPEN_TRADES must be >= 1."""
        with patch("config.core.MAX_OPEN_TRADES", 0):
            errors = validate_config()
        assert any("max_open_trades" in e.lower() for e in errors)

    def test_supertrend_atr_period_positive(self):
        """SUPERTREND_ATR_PERIOD must be >= 1."""
        with patch("config.core.SUPERTREND_ATR_PERIOD", 0):
            errors = validate_config()
        assert any("supertrend" in e.lower() for e in errors)
