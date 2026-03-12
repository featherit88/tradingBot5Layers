"""Risk management: position sizing, drawdown tracking, partial closes."""

from __future__ import annotations

from dataclasses import dataclass, field

from config import (
    DAILY_DRAWDOWN_LIMIT,
    MAX_OPEN_TRADES,
    PARTIAL_CLOSE_PCT,
    RISK_PER_TRADE_PCT,
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
    partial_closed: bool = False


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
        pnl = trade.direction * (exit_price - trade.entry_price) * trade.size * point_value
        self.balance += pnl
        if trade in self.open_trades:
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
        return pnl

    # ── Day/week resets ──────────────────────────────────────────

    def reset_day(self) -> None:
        self.day_start_balance = self.balance

    def reset_week(self) -> None:
        self.week_start_balance = self.balance
