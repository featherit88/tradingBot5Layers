"""Tests for bot.db — TradeLogger against the real MySQL container."""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from mysql.connector import Error as MySQLError

from bot import TradeLogger

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def logger():
    """Create a TradeLogger connected to the real MySQL container."""
    tl = TradeLogger()
    connected = tl.connect()
    if not connected:
        pytest.skip("MySQL container not reachable — skipping DB tests")
    yield tl
    # Cleanup: delete all test data, then disconnect
    try:
        cursor = tl._conn.cursor()
        cursor.execute("DELETE FROM trades")
        cursor.execute("DELETE FROM daily_summary")
        tl._conn.commit()
        cursor.close()
    except Exception:
        pass
    tl.disconnect()


@pytest.fixture
def sample_trade_args():
    """Standard arguments for log_trade_open()."""
    return {
        "opened_at": datetime(2026, 3, 13, 14, 30, 0, tzinfo=UTC),
        "instrument": "US30",
        "direction": 1,
        "strategy": "ema_scalp",
        "score": 8,
        "entry_price": 39150.0,
        "stop_loss": 39120.0,
        "take_profit_1r": 39180.0,
        "size": 0.5,
    }


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

class TestConnection:
    """Verify connect / disconnect / reconnect behaviour."""

    def test_connect_returns_true(self, logger):
        """A fresh connect() to the running MySQL returns True."""
        # logger fixture already connected; verify state
        assert logger._conn is not None
        assert logger._conn.is_connected()

    def test_disconnect_closes_connection(self, logger):
        """After disconnect(), the connection is closed."""
        logger.disconnect()
        assert not logger._conn.is_connected()

    def test_ensure_connected_reconnects(self, logger):
        """_ensure_connected() restores a dropped connection."""
        logger.disconnect()
        assert logger._ensure_connected()
        assert logger._conn.is_connected()

    def test_connect_failure_returns_false(self):
        """If MySQL is unreachable, connect() returns False and sets _conn to None."""
        tl = TradeLogger()
        with patch("bot.db._get_connection", side_effect=MySQLError("refused")):
            result = tl.connect()
        assert result is False
        assert tl._conn is None


# ---------------------------------------------------------------------------
# Trade open
# ---------------------------------------------------------------------------

class TestLogTradeOpen:
    """Verify INSERT into trades table."""

    def test_returns_row_id(self, logger, sample_trade_args):
        """log_trade_open() returns a positive integer row ID."""
        row_id = logger.log_trade_open(**sample_trade_args)
        assert isinstance(row_id, int)
        assert row_id > 0

    def test_data_persisted_correctly(self, logger, sample_trade_args):
        """Inserted row has correct values for all columns."""
        row_id = logger.log_trade_open(**sample_trade_args)
        cursor = logger._conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM trades WHERE id = %s", (row_id,))
        row = cursor.fetchone()
        cursor.close()

        assert row is not None
        assert row["instrument"] == "US30"
        assert row["direction"] == 1
        assert row["strategy"] == "ema_scalp"
        assert row["score"] == 8
        assert row["entry_price"] == pytest.approx(39150.0)
        assert row["stop_loss"] == pytest.approx(39120.0)
        assert row["take_profit_1r"] == pytest.approx(39180.0)
        assert row["size"] == pytest.approx(0.5)
        # Close fields should be NULL
        assert row["closed_at"] is None
        assert row["exit_price"] is None
        assert row["pnl"] is None

    def test_multiple_inserts_unique_ids(self, logger, sample_trade_args):
        """Two inserts produce different row IDs."""
        id1 = logger.log_trade_open(**sample_trade_args)
        id2 = logger.log_trade_open(**sample_trade_args)
        assert id1 != id2

    def test_returns_none_when_disconnected(self, sample_trade_args):
        """If DB is unreachable, returns None without raising."""
        tl = TradeLogger()
        with patch("bot.db._get_connection", side_effect=MySQLError("refused")):
            result = tl.log_trade_open(**sample_trade_args)
        assert result is None


# ---------------------------------------------------------------------------
# Trade close
# ---------------------------------------------------------------------------

class TestLogTradeClose:
    """Verify UPDATE on trade close."""

    def test_updates_close_fields(self, logger, sample_trade_args):
        """log_trade_close() fills closed_at, exit_price, pnl, exit_reason, balance_after."""
        row_id = logger.log_trade_open(**sample_trade_args)
        close_time = datetime(2026, 3, 13, 15, 0, 0, tzinfo=UTC)

        logger.log_trade_close(
            trade_id=row_id,
            closed_at=close_time,
            exit_price=39180.0,
            pnl=15.0,
            exit_reason="tp_1r",
            balance_after=2015.0,
        )

        cursor = logger._conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM trades WHERE id = %s", (row_id,))
        row = cursor.fetchone()
        cursor.close()

        assert row["exit_price"] == pytest.approx(39180.0)
        assert row["pnl"] == pytest.approx(15.0)
        assert row["exit_reason"] == "tp_1r"
        assert row["balance_after"] == pytest.approx(2015.0)
        assert row["closed_at"] is not None

    def test_close_nonexistent_trade_no_error(self, logger):
        """Closing a trade ID that doesn't exist should not raise."""
        close_time = datetime(2026, 3, 13, 15, 0, 0, tzinfo=UTC)
        logger.log_trade_close(
            trade_id=999999,
            closed_at=close_time,
            exit_price=39100.0,
            pnl=-20.0,
            exit_reason="stop_loss",
            balance_after=1980.0,
        )
        # No exception = pass

    def test_close_resilient_when_disconnected(self):
        """log_trade_close() gracefully handles no DB connection."""
        tl = TradeLogger()
        with patch("bot.db._get_connection", side_effect=MySQLError("refused")):
            tl.log_trade_close(
                trade_id=1,
                closed_at=datetime(2026, 3, 13, 15, 0, 0, tzinfo=UTC),
                exit_price=39100.0,
                pnl=-20.0,
                exit_reason="stop_loss",
                balance_after=1980.0,
            )
        # No exception = pass


# ---------------------------------------------------------------------------
# Partial close
# ---------------------------------------------------------------------------

class TestLogPartialClose:
    """Verify UPDATE for partial close at 1R."""

    def test_updates_partial_fields(self, logger, sample_trade_args):
        """log_partial_close() fills partial_closed_at, partial_exit_price, partial_pnl, remaining_size."""
        row_id = logger.log_trade_open(**sample_trade_args)
        partial_time = datetime(2026, 3, 13, 14, 45, 0, tzinfo=UTC)

        logger.log_partial_close(
            trade_id=row_id,
            closed_at=partial_time,
            exit_price=39180.0,
            pnl=7.5,
            remaining_size=0.25,
        )

        cursor = logger._conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM trades WHERE id = %s", (row_id,))
        row = cursor.fetchone()
        cursor.close()

        assert row["partial_exit_price"] == pytest.approx(39180.0)
        assert row["partial_pnl"] == pytest.approx(7.5)
        assert row["remaining_size"] == pytest.approx(0.25)
        assert row["partial_closed_at"] is not None
        # Full close fields still NULL
        assert row["closed_at"] is None
        assert row["exit_price"] is None

    def test_partial_then_full_close(self, logger, sample_trade_args):
        """A trade can be partially closed, then fully closed — both records coexist."""
        row_id = logger.log_trade_open(**sample_trade_args)

        logger.log_partial_close(
            trade_id=row_id,
            closed_at=datetime(2026, 3, 13, 14, 45, 0, tzinfo=UTC),
            exit_price=39180.0,
            pnl=7.5,
            remaining_size=0.25,
        )
        logger.log_trade_close(
            trade_id=row_id,
            closed_at=datetime(2026, 3, 13, 15, 10, 0, tzinfo=UTC),
            exit_price=39200.0,
            pnl=12.5,
            exit_reason="trailing_stop",
            balance_after=2020.0,
        )

        cursor = logger._conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM trades WHERE id = %s", (row_id,))
        row = cursor.fetchone()
        cursor.close()

        # Both partial and full close fields populated
        assert row["partial_exit_price"] == pytest.approx(39180.0)
        assert row["exit_price"] == pytest.approx(39200.0)
        assert row["pnl"] == pytest.approx(12.5)
        assert row["exit_reason"] == "trailing_stop"


# ---------------------------------------------------------------------------
# Daily summary
# ---------------------------------------------------------------------------

class TestLogDailySummary:
    """Verify INSERT / upsert into daily_summary table."""

    def test_inserts_summary_row(self, logger):
        """First call for a date inserts a new row."""
        trade_date = datetime(2026, 3, 13, tzinfo=UTC)
        logger.log_daily_summary(
            trade_date=trade_date,
            starting_balance=2000.0,
            ending_balance=2050.0,
            total_trades=5,
            wins=3,
            losses=2,
            total_pnl=50.0,
            max_drawdown_pct=1.5,
        )

        cursor = logger._conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM daily_summary WHERE trade_date = %s", (trade_date.date(),))
        row = cursor.fetchone()
        cursor.close()

        assert row is not None
        assert row["starting_balance"] == pytest.approx(2000.0)
        assert row["ending_balance"] == pytest.approx(2050.0)
        assert row["total_trades"] == 5
        assert row["wins"] == 3
        assert row["losses"] == 2
        assert row["total_pnl"] == pytest.approx(50.0)
        assert row["max_drawdown_pct"] == pytest.approx(1.5)

    def test_upsert_updates_existing_row(self, logger):
        """Second call for the same date updates (ON DUPLICATE KEY UPDATE)."""
        trade_date = datetime(2026, 3, 13, tzinfo=UTC)

        # First insert
        logger.log_daily_summary(
            trade_date=trade_date,
            starting_balance=2000.0,
            ending_balance=2020.0,
            total_trades=2,
            wins=1,
            losses=1,
            total_pnl=20.0,
            max_drawdown_pct=0.5,
        )

        # Upsert with updated values
        logger.log_daily_summary(
            trade_date=trade_date,
            starting_balance=2000.0,
            ending_balance=2050.0,
            total_trades=5,
            wins=3,
            losses=2,
            total_pnl=50.0,
            max_drawdown_pct=1.5,
        )

        cursor = logger._conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM daily_summary WHERE trade_date = %s", (trade_date.date(),))
        rows = cursor.fetchall()
        cursor.close()

        # Only one row for that date
        assert len(rows) == 1
        assert rows[0]["ending_balance"] == pytest.approx(2050.0)
        assert rows[0]["total_trades"] == 5
        assert rows[0]["total_pnl"] == pytest.approx(50.0)

    def test_resilient_when_disconnected(self):
        """log_daily_summary() handles no DB connection gracefully."""
        tl = TradeLogger()
        with patch("bot.db._get_connection", side_effect=MySQLError("refused")):
            tl.log_daily_summary(
                trade_date=datetime(2026, 3, 13, tzinfo=UTC),
                starting_balance=2000.0,
                ending_balance=2000.0,
                total_trades=0,
                wins=0,
                losses=0,
                total_pnl=0.0,
                max_drawdown_pct=0.0,
            )
        # No exception = pass


# ---------------------------------------------------------------------------
# Full lifecycle
# ---------------------------------------------------------------------------

class TestFullLifecycle:
    """End-to-end: open → partial → close a trade, verify final DB state."""

    def test_long_trade_lifecycle(self, logger):
        """Open a long trade, partial close at 1R, full close with trailing stop."""
        # Open
        row_id = logger.log_trade_open(
            opened_at=datetime(2026, 3, 13, 14, 30, 0, tzinfo=UTC),
            instrument="US30",
            direction=1,
            strategy="break_retest",
            score=9,
            entry_price=39200.0,
            stop_loss=39160.0,
            take_profit_1r=39240.0,
            size=1.0,
        )
        assert row_id is not None

        # Partial close at 1R
        logger.log_partial_close(
            trade_id=row_id,
            closed_at=datetime(2026, 3, 13, 14, 42, 0, tzinfo=UTC),
            exit_price=39240.0,
            pnl=20.0,
            remaining_size=0.5,
        )

        # Full close with trailing stop
        logger.log_trade_close(
            trade_id=row_id,
            closed_at=datetime(2026, 3, 13, 15, 5, 0, tzinfo=UTC),
            exit_price=39280.0,
            pnl=40.0,
            exit_reason="trailing_stop",
            balance_after=2060.0,
        )

        # Verify final state
        cursor = logger._conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM trades WHERE id = %s", (row_id,))
        row = cursor.fetchone()
        cursor.close()

        assert row["direction"] == 1
        assert row["strategy"] == "break_retest"
        assert row["partial_exit_price"] == pytest.approx(39240.0)
        assert row["partial_pnl"] == pytest.approx(20.0)
        assert row["remaining_size"] == pytest.approx(0.5)
        assert row["exit_price"] == pytest.approx(39280.0)
        assert row["pnl"] == pytest.approx(40.0)
        assert row["exit_reason"] == "trailing_stop"
        assert row["balance_after"] == pytest.approx(2060.0)

    def test_short_trade_stopped_out(self, logger):
        """Open a short trade that hits stop loss — no partial close."""
        row_id = logger.log_trade_open(
            opened_at=datetime(2026, 3, 13, 8, 0, 0, tzinfo=UTC),
            instrument="SPX",
            direction=-1,
            strategy="vwap_reversion",
            score=7,
            entry_price=5200.0,
            stop_loss=5215.0,
            take_profit_1r=5185.0,
            size=0.3,
        )

        logger.log_trade_close(
            trade_id=row_id,
            closed_at=datetime(2026, 3, 13, 8, 12, 0, tzinfo=UTC),
            exit_price=5215.0,
            pnl=-4.5,
            exit_reason="stop_loss",
            balance_after=1995.5,
        )

        cursor = logger._conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM trades WHERE id = %s", (row_id,))
        row = cursor.fetchone()
        cursor.close()

        assert row["direction"] == -1
        assert row["pnl"] == pytest.approx(-4.5)
        assert row["exit_reason"] == "stop_loss"
        # No partial close happened
        assert row["partial_closed_at"] is None
        assert row["partial_exit_price"] is None
