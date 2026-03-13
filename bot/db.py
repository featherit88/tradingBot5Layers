"""Trade persistence — logs trades and daily summaries to MySQL."""

from __future__ import annotations

import logging
import os
from datetime import datetime

import mysql.connector
from mysql.connector import Error

log = logging.getLogger("bot.db")


def _get_connection():
    """Create a new MySQL connection from environment variables."""
    return mysql.connector.connect(
        host=os.environ.get("MYSQL_HOST", "db"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        database=os.environ.get("MYSQL_DATABASE", "scalping_bot"),
        user=os.environ.get("MYSQL_USER", "scalping"),
        password=os.environ.get("MYSQL_PASSWORD", "scalping_pw"),
    )


class TradeLogger:
    """Logs trade opens, closes, and daily summaries to MySQL."""

    def __init__(self) -> None:
        self._conn = None

    def connect(self) -> bool:
        """Establish database connection. Returns True on success."""
        try:
            self._conn = _get_connection()
            log.info("Connected to MySQL database")
            return True
        except Error as e:
            log.warning("Could not connect to MySQL: %s — trading continues without DB logging", e)
            self._conn = None
            return False

    def disconnect(self) -> None:
        if self._conn and self._conn.is_connected():
            self._conn.close()
            log.info("Disconnected from MySQL")

    def _ensure_connected(self) -> bool:
        """Reconnect if connection was lost."""
        if self._conn and self._conn.is_connected():
            return True
        return self.connect()

    def log_trade_open(
        self,
        opened_at: datetime,
        instrument: str,
        direction: int,
        strategy: str,
        score: int,
        entry_price: float,
        stop_loss: float,
        take_profit_1r: float,
        size: float,
    ) -> int | None:
        """Insert a new trade row when a position opens. Returns the row ID."""
        if not self._ensure_connected():
            return None
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """INSERT INTO trades
                   (opened_at, instrument, direction, strategy, score,
                    entry_price, stop_loss, take_profit_1r, size)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (opened_at, instrument, direction, strategy, score,
                 entry_price, stop_loss, take_profit_1r, size),
            )
            self._conn.commit()
            trade_id = cursor.lastrowid
            cursor.close()
            log.debug("Logged trade open id=%d %s %s", trade_id, instrument, strategy)
            return trade_id
        except Error as e:
            log.warning("Failed to log trade open: %s", e)
            return None

    def log_trade_close(
        self,
        trade_id: int,
        closed_at: datetime,
        exit_price: float,
        pnl: float,
        exit_reason: str,
        balance_after: float,
    ) -> None:
        """Update a trade row when the position closes."""
        if not self._ensure_connected():
            return
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """UPDATE trades
                   SET closed_at = %s, exit_price = %s, pnl = %s,
                       exit_reason = %s, balance_after = %s
                   WHERE id = %s""",
                (closed_at, exit_price, pnl, exit_reason, balance_after, trade_id),
            )
            self._conn.commit()
            cursor.close()
            log.debug("Logged trade close id=%d pnl=%.2f reason=%s", trade_id, pnl, exit_reason)
        except Error as e:
            log.warning("Failed to log trade close: %s", e)

    def log_partial_close(
        self,
        trade_id: int,
        closed_at: datetime,
        exit_price: float,
        pnl: float,
        remaining_size: float,
    ) -> None:
        """Record a partial close (at 1R) on an existing trade row."""
        if not self._ensure_connected():
            return
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """UPDATE trades
                   SET partial_closed_at = %s, partial_exit_price = %s,
                       partial_pnl = %s, remaining_size = %s
                   WHERE id = %s""",
                (closed_at, exit_price, pnl, remaining_size, trade_id),
            )
            self._conn.commit()
            cursor.close()
            log.debug(
                "Logged partial close id=%d price=%.2f pnl=%.2f remaining=%.2f",
                trade_id, exit_price, pnl, remaining_size,
            )
        except Error as e:
            log.warning("Failed to log partial close: %s", e)

    def log_daily_summary(
        self,
        trade_date: datetime,
        starting_balance: float,
        ending_balance: float,
        total_trades: int,
        wins: int,
        losses: int,
        total_pnl: float,
        max_drawdown_pct: float,
    ) -> None:
        """Insert or update the daily summary row."""
        if not self._ensure_connected():
            return
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """INSERT INTO daily_summary
                   (trade_date, starting_balance, ending_balance,
                    total_trades, wins, losses, total_pnl, max_drawdown_pct)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE
                    ending_balance = VALUES(ending_balance),
                    total_trades = VALUES(total_trades),
                    wins = VALUES(wins),
                    losses = VALUES(losses),
                    total_pnl = VALUES(total_pnl),
                    max_drawdown_pct = VALUES(max_drawdown_pct)""",
                (trade_date, starting_balance, ending_balance,
                 total_trades, wins, losses, total_pnl, max_drawdown_pct),
            )
            self._conn.commit()
            cursor.close()
        except Error as e:
            log.warning("Failed to log daily summary: %s", e)
