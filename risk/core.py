"""Risk management: position sizing, drawdown tracking, partial closes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from config import (
    DAILY_DRAWDOWN_LIMIT,
    MAX_OPEN_TRADES,
    PARTIAL_CLOSE_PCT,
    RISK_PER_TRADE_PCT,
    TRAIL_ATR_FRACTION,
    WEEKLY_DRAWDOWN_LIMIT,
)


@dataclass
class Trade:
    instrument: str
    direction: int          # 1 long, -1 short
    entry_price: float
    stop_loss: float
    take_profit_1r: float
    size: float             # lot / contract size
    atr_at_entry: float = 0.0       # ATR(14) snapshot for trailing calc
    partial_closed: bool = False
    best_price: float = 0.0         # best favorable price since partial close
    db_id: int | None = None        # MySQL row ID for trade logging
    entry_time: datetime | None = None
    strategy: str = ""
    score: int = 0


@dataclass
class RiskManager:
    balance: float
    day_start_balance: float = 0.0
    week_start_balance: float = 0.0
    open_trades: list[Trade] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.day_start_balance == 0.0:
            self.day_start_balance = self.balance
        if self.week_start_balance == 0.0:
            self.week_start_balance = self.balance

    # ── Guards ────────────────────────────────────────────────────

    def can_open_trade(self) -> bool:
        if len(self.open_trades) >= MAX_OPEN_TRADES:
            return False
        if self.daily_drawdown_hit():
            return False
        if self.weekly_drawdown_hit():
            return False
        return True

    def daily_drawdown_hit(self) -> bool:
        return (self.day_start_balance - self.balance) / self.day_start_balance >= DAILY_DRAWDOWN_LIMIT

    def weekly_drawdown_hit(self) -> bool:
        return (self.week_start_balance - self.balance) / self.week_start_balance >= WEEKLY_DRAWDOWN_LIMIT

    # ── Position sizing ──────────────────────────────────────────

    def position_size(self, entry: float, stop: float, point_value: float) -> float:
        """Calculate lot/contract size so risk = 1% of account."""
        risk_amount = self.balance * RISK_PER_TRADE_PCT
        stop_distance = abs(entry - stop)
        if stop_distance == 0:
            return 0.0
        return risk_amount / (stop_distance * point_value)

    # ── Trade lifecycle ──────────────────────────────────────────

    def open_trade(self, trade: Trade) -> None:
        self.open_trades.append(trade)

    def close_trade(self, trade: Trade, exit_price: float, point_value: float) -> float:
        """Close full position, update balance. Returns PnL."""
        if trade not in self.open_trades:
            return 0.0
        pnl = trade.direction * (exit_price - trade.entry_price) * trade.size * point_value
        self.balance += pnl
        self.open_trades.remove(trade)
        return pnl

    def partial_close(self, trade: Trade, current_price: float, point_value: float) -> float:
        """Close 50% at 1R. Returns PnL of the closed portion."""
        if trade.partial_closed:
            return 0.0
        close_size = trade.size * PARTIAL_CLOSE_PCT
        pnl = trade.direction * (current_price - trade.entry_price) * close_size * point_value
        self.balance += pnl
        trade.size -= close_size
        trade.partial_closed = True
        trade.best_price = current_price
        return pnl

    # ── Trailing stop ──────────────────────────────────────────

    @staticmethod
    def update_trailing_stop(trade: Trade, price: float) -> None:
        """Trail the stop behind the best favorable price after partial close."""
        if not trade.partial_closed or trade.atr_at_entry <= 0:
            return
        trail_dist = TRAIL_ATR_FRACTION * trade.atr_at_entry
        if trade.direction == 1:
            if price > trade.best_price:
                trade.best_price = price
            new_sl = trade.best_price - trail_dist
            if new_sl > trade.stop_loss:
                trade.stop_loss = new_sl
        else:
            if price < trade.best_price:
                trade.best_price = price
            new_sl = trade.best_price + trail_dist
            if new_sl < trade.stop_loss:
                trade.stop_loss = new_sl

    # ── Day/week resets ──────────────────────────────────────────

    def reset_day(self) -> None:
        self.day_start_balance = self.balance

    def reset_week(self) -> None:
        self.week_start_balance = self.balance
