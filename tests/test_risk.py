"""Tests for the risk module."""

import pytest

from risk import RiskManager, Trade


def _make_trade(**overrides) -> Trade:
    defaults = dict(
        instrument="US30",
        direction=1,
        entry_price=39500.0,
        stop_loss=39450.0,
        take_profit_1r=39550.0,
        size=0.2,
        atr_at_entry=50.0,
    )
    defaults.update(overrides)
    return Trade(**defaults)


# ── Position sizing ─────────────────────────────────────────────

class TestPositionSizing:
    def test_basic_sizing(self):
        rm = RiskManager(balance=2000.0)
        # 1% of 2000 = 20, stop distance = 50, pv = 1
        size = rm.position_size(entry=39500, stop=39450, point_value=1.0)
        assert abs(size - 0.4) < 0.01  # 20 / 50 = 0.4

    def test_zero_stop_distance(self):
        rm = RiskManager(balance=2000.0)
        size = rm.position_size(entry=100, stop=100, point_value=1.0)
        assert size == 0.0


# ── Trade lifecycle ─────────────────────────────────────────────

class TestTradeLifecycle:
    def test_open_trade(self):
        rm = RiskManager(balance=2000.0)
        trade = _make_trade()
        rm.open_trade(trade)
        assert len(rm.open_trades) == 1

    def test_close_trade_profit(self):
        rm = RiskManager(balance=2000.0)
        trade = _make_trade(direction=1, entry_price=100.0, size=1.0)
        rm.open_trade(trade)
        pnl = rm.close_trade(trade, exit_price=110.0, point_value=1.0)
        assert pnl == 10.0
        assert rm.balance == 2010.0
        assert len(rm.open_trades) == 0

    def test_close_trade_loss(self):
        rm = RiskManager(balance=2000.0)
        trade = _make_trade(direction=1, entry_price=100.0, size=1.0)
        rm.open_trade(trade)
        pnl = rm.close_trade(trade, exit_price=90.0, point_value=1.0)
        assert pnl == -10.0
        assert rm.balance == 1990.0

    def test_short_trade_profit(self):
        rm = RiskManager(balance=2000.0)
        trade = _make_trade(direction=-1, entry_price=100.0, size=1.0)
        rm.open_trade(trade)
        pnl = rm.close_trade(trade, exit_price=90.0, point_value=1.0)
        assert pnl == 10.0


# ── Partial close ──────────────────────────────────────────────

class TestPartialClose:
    def test_partial_close_50pct(self):
        rm = RiskManager(balance=2000.0)
        trade = _make_trade(direction=1, entry_price=100.0, size=1.0)
        rm.open_trade(trade)
        pnl = rm.partial_close(trade, current_price=110.0, point_value=1.0)
        assert pnl == 5.0  # 50% of 1.0 * (110-100)
        assert trade.partial_closed is True
        assert trade.size == 0.5

    def test_partial_close_only_once(self):
        rm = RiskManager(balance=2000.0)
        trade = _make_trade(direction=1, entry_price=100.0, size=1.0)
        rm.open_trade(trade)
        rm.partial_close(trade, current_price=110.0, point_value=1.0)
        pnl2 = rm.partial_close(trade, current_price=120.0, point_value=1.0)
        assert pnl2 == 0.0  # second call does nothing


# ── Drawdown guards ─────────────────────────────────────────────

class TestDrawdownGuards:
    def test_daily_drawdown_not_hit(self):
        rm = RiskManager(balance=2000.0)
        assert rm.daily_drawdown_hit() is False

    def test_daily_drawdown_hit(self):
        rm = RiskManager(balance=1900.0, day_start_balance=2000.0)
        # (2000 - 1900) / 2000 = 5% > 3%
        assert rm.daily_drawdown_hit() is True

    def test_weekly_drawdown_hit(self):
        rm = RiskManager(balance=1800.0, week_start_balance=2000.0)
        # (2000 - 1800) / 2000 = 10% > 6%
        assert rm.weekly_drawdown_hit() is True

    def test_max_open_trades(self):
        rm = RiskManager(balance=2000.0)
        rm.open_trade(_make_trade())
        rm.open_trade(_make_trade())
        assert rm.can_open_trade() is False

    def test_can_open_when_under_limits(self):
        rm = RiskManager(balance=2000.0)
        assert rm.can_open_trade() is True


# ── Day/week resets ─────────────────────────────────────────────

class TestResets:
    def test_reset_day(self):
        rm = RiskManager(balance=1950.0, day_start_balance=2000.0)
        rm.reset_day()
        assert rm.day_start_balance == 1950.0

    def test_reset_week(self):
        rm = RiskManager(balance=1900.0, week_start_balance=2000.0)
        rm.reset_week()
        assert rm.week_start_balance == 1900.0


# ── Trailing stop ────────────────────────────────────────────────

class TestTrailingStop:
    """Tests for RiskManager.update_trailing_stop()."""

    def test_no_trail_before_partial_close(self):
        """Trailing stop should NOT update if partial_closed=False."""
        trade = _make_trade(
            entry_price=40000.0, stop_loss=39950.0,
            atr_at_entry=50.0, direction=1,
        )
        trade.partial_closed = False
        trade.best_price = 40000.0
        RiskManager.update_trailing_stop(trade, price=40100.0)
        assert trade.stop_loss == 39950.0
        assert trade.best_price == 40000.0  # unchanged

    def test_no_trail_zero_atr(self):
        """Trailing stop should NOT update if atr_at_entry=0."""
        trade = _make_trade(
            entry_price=40000.0, stop_loss=39950.0,
            atr_at_entry=0.0, direction=1,
        )
        trade.partial_closed = True
        trade.best_price = 40000.0
        RiskManager.update_trailing_stop(trade, price=40100.0)
        assert trade.stop_loss == 39950.0

    def test_long_trail_updates_stop(self):
        """Long trade after partial close: price moves up => stop trails up."""
        trade = _make_trade(
            entry_price=40000.0, stop_loss=39950.0,
            atr_at_entry=50.0, direction=1,
        )
        trade.partial_closed = True
        trade.best_price = 40000.0
        # Price moves to 40100 => new_sl = 40100 - 0.5*50 = 40075
        RiskManager.update_trailing_stop(trade, price=40100.0)
        assert trade.stop_loss == pytest.approx(40075.0)

    def test_long_trail_doesnt_lower_stop(self):
        """Long trade: if price drops, stop should NOT move down."""
        trade = _make_trade(
            entry_price=40000.0, stop_loss=39950.0,
            atr_at_entry=50.0, direction=1,
        )
        trade.partial_closed = True
        trade.best_price = 40000.0
        # First move up to raise the stop
        RiskManager.update_trailing_stop(trade, price=40100.0)
        raised_stop = trade.stop_loss
        assert raised_stop == pytest.approx(40075.0)
        # Price drops — stop must not decrease
        RiskManager.update_trailing_stop(trade, price=40020.0)
        assert trade.stop_loss == raised_stop

    def test_short_trail_updates_stop(self):
        """Short trade after partial close: price moves down => stop trails down."""
        trade = _make_trade(
            entry_price=40000.0, stop_loss=40050.0,
            atr_at_entry=50.0, direction=-1,
        )
        trade.partial_closed = True
        trade.best_price = 40000.0
        # Price drops to 39900 => new_sl = 39900 + 0.5*50 = 39925
        RiskManager.update_trailing_stop(trade, price=39900.0)
        assert trade.stop_loss == pytest.approx(39925.0)

    def test_short_trail_doesnt_raise_stop(self):
        """Short trade: if price rises, stop should NOT move up."""
        trade = _make_trade(
            entry_price=40000.0, stop_loss=40050.0,
            atr_at_entry=50.0, direction=-1,
        )
        trade.partial_closed = True
        trade.best_price = 40000.0
        # First move down to lower the stop
        RiskManager.update_trailing_stop(trade, price=39900.0)
        lowered_stop = trade.stop_loss
        assert lowered_stop == pytest.approx(39925.0)
        # Price rises — stop must not increase
        RiskManager.update_trailing_stop(trade, price=39980.0)
        assert trade.stop_loss == lowered_stop

    def test_best_price_tracked_long(self):
        """Long trade: best_price updates when price makes new highs."""
        trade = _make_trade(
            entry_price=40000.0, stop_loss=39950.0,
            atr_at_entry=50.0, direction=1,
        )
        trade.partial_closed = True
        trade.best_price = 40000.0
        RiskManager.update_trailing_stop(trade, price=40050.0)
        assert trade.best_price == 40050.0
        RiskManager.update_trailing_stop(trade, price=40120.0)
        assert trade.best_price == 40120.0
        # Price drops — best_price stays at the high
        RiskManager.update_trailing_stop(trade, price=40080.0)
        assert trade.best_price == 40120.0

    def test_best_price_tracked_short(self):
        """Short trade: best_price updates when price makes new lows."""
        trade = _make_trade(
            entry_price=40000.0, stop_loss=40050.0,
            atr_at_entry=50.0, direction=-1,
        )
        trade.partial_closed = True
        trade.best_price = 40000.0
        RiskManager.update_trailing_stop(trade, price=39950.0)
        assert trade.best_price == 39950.0
        RiskManager.update_trailing_stop(trade, price=39880.0)
        assert trade.best_price == 39880.0
        # Price rises — best_price stays at the low
        RiskManager.update_trailing_stop(trade, price=39920.0)
        assert trade.best_price == 39880.0


# ── Trade dataclass fields ──────────────────────────────────────

class TestTradeFields:
    def test_trailing_fields_default(self):
        trade = _make_trade()
        assert trade.best_price == 0.0
        assert trade.atr_at_entry == 50.0
        assert trade.db_id is None
        assert trade.partial_closed is False
