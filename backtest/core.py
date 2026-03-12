"""Backtesting engine — walk-forward simulation using the bot's exact logic."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone

import numpy as np
import pandas as pd

from config import (
    INSTRUMENT_CONFIGS,
    ORB_MINUTES,
    STARTING_CAPITAL,
    Instrument,
    Session,
    SESSION_WINDOWS,
)
from filters import all_filters_pass
from indicators import atr
from risk import RiskManager, Trade
from scoring import compute_confluence
from strategies import (
    break_and_retest,
    ema_ribbon_scalp,
    opening_range_breakout,
    vwap_reversion,
)

log = logging.getLogger("backtest")

POINT_VALUE = {
    Instrument.US30: 1.0,
    Instrument.SPX: 1.0,
}


# ── Synthetic data generator ──────────────────────────────────────


def generate_candles(
    instrument: Instrument,
    days: int = 20,
    timeframe_minutes: int = 1,
    start_date: datetime | None = None,
) -> pd.DataFrame:
    """Generate realistic synthetic OHLCV data for backtesting.

    Produces candles only during London (07:00-10:00) and NY (13:30-16:30)
    sessions to match the bot's trading windows.
    """
    if start_date is None:
        start_date = datetime(2026, 1, 5, 7, 0, tzinfo=timezone.utc)  # a Monday

    # Base price and volatility per instrument
    base_prices = {Instrument.US30: 39000.0, Instrument.SPX: 5200.0}
    tick_sizes = {Instrument.US30: 1.0, Instrument.SPX: 0.25}

    base = base_prices[instrument]
    tick = tick_sizes[instrument]

    # Session windows as (start_hour, start_min, end_hour, end_min)
    sessions = [
        (7, 0, 10, 0),    # London
        (13, 30, 16, 30),  # New York
    ]

    rows: list[dict] = []
    price = base

    # Regime: trending phases with random direction switches
    regime_dir = 1  # 1 = uptrend, -1 = downtrend
    regime_bars = 0
    regime_length = int(np.random.uniform(30, 120))  # bars per regime

    for day in range(days):
        current_date = start_date + timedelta(days=day)
        # Skip weekends
        if current_date.weekday() >= 5:
            continue

        for s_h, s_m, e_h, e_m in sessions:
            session_start = current_date.replace(hour=s_h, minute=s_m, second=0)
            session_end = current_date.replace(hour=e_h, minute=e_m, second=0)
            t = session_start

            while t < session_end:
                # Switch regime periodically
                regime_bars += 1
                if regime_bars >= regime_length:
                    regime_dir *= -1
                    regime_bars = 0
                    regime_length = int(np.random.uniform(30, 120))

                # Trending drift + noise
                trend_strength = base * 0.0004  # directional bias per bar
                volatility = base * 0.00025  # noise

                drift = regime_dir * trend_strength
                # Add mean-reversion to prevent runaway prices
                drift += -0.00002 * (price - base)

                noise = np.random.normal(drift, volatility)
                open_p = round(price, 2)
                intra_high = abs(np.random.normal(0, volatility * 0.7))
                intra_low = abs(np.random.normal(0, volatility * 0.7))

                close_p = round(open_p + noise, 2)
                high_p = round(max(open_p, close_p) + intra_high, 2)
                low_p = round(min(open_p, close_p) - intra_low, 2)

                # Volume: higher during trends, with occasional spikes
                vol_base = 800 + np.random.exponential(400)
                # Boost volume in strong trend bars
                if abs(noise) > volatility:
                    vol_base *= 1.5
                volume = int(vol_base)

                rows.append({
                    "timestamp": t,
                    "open": open_p,
                    "high": high_p,
                    "low": low_p,
                    "close": close_p,
                    "volume": volume,
                })

                price = close_p
                t += timedelta(minutes=timeframe_minutes)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df.set_index("timestamp", inplace=True)
    return df


def resample_candles(df_1m: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """Resample 1M candles to higher timeframes (3M, 5M)."""
    rule = f"{minutes}min"
    resampled = df_1m.resample(rule).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()
    return resampled


# ── Trade result tracking ─────────────────────────────────────────


@dataclass
class TradeRecord:
    """One completed trade for the backtest log."""
    instrument: str
    direction: int
    strategy: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    score: int
    exit_reason: str  # "stop_loss", "partial_1r", "session_end"


@dataclass
class BacktestResult:
    """Final output of a backtest run."""
    instrument: str
    start_date: datetime
    end_date: datetime
    starting_capital: float
    ending_capital: float
    trades: list[TradeRecord] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def winning_trades(self) -> int:
        return sum(1 for t in self.trades if t.pnl > 0)

    @property
    def losing_trades(self) -> int:
        return sum(1 for t in self.trades if t.pnl <= 0)

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades

    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self.trades)

    @property
    def avg_pnl(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.total_pnl / self.total_trades

    @property
    def max_drawdown(self) -> float:
        """Maximum peak-to-trough drawdown from equity curve."""
        if not self.equity_curve:
            return 0.0
        peak = self.equity_curve[0]
        max_dd = 0.0
        for val in self.equity_curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @property
    def profit_factor(self) -> float:
        gross_profit = sum(t.pnl for t in self.trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.trades if t.pnl <= 0))
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    @property
    def sharpe_ratio(self) -> float:
        """Annualized Sharpe ratio from trade returns."""
        if len(self.trades) < 2:
            return 0.0
        returns = [t.pnl for t in self.trades]
        mean_r = np.mean(returns)
        std_r = np.std(returns, ddof=1)
        if std_r == 0:
            return 0.0
        # Assume ~5 trades per day, 252 trading days
        return float((mean_r / std_r) * np.sqrt(252 * 5))

    def summary(self) -> str:
        """Human-readable backtest summary."""
        lines = [
            f"═══ Backtest Results: {self.instrument} ═══",
            f"Period: {self.start_date:%Y-%m-%d} → {self.end_date:%Y-%m-%d}",
            f"Capital: €{self.starting_capital:.2f} → €{self.ending_capital:.2f}",
            f"Total PnL: €{self.total_pnl:.2f} ({self.total_pnl / self.starting_capital * 100:+.1f}%)",
            f"",
            f"Trades: {self.total_trades}  |  Wins: {self.winning_trades}  |  Losses: {self.losing_trades}",
            f"Win rate: {self.win_rate:.1%}",
            f"Avg PnL/trade: €{self.avg_pnl:.2f}",
            f"Profit factor: {self.profit_factor:.2f}",
            f"Max drawdown: {self.max_drawdown:.2%}",
            f"Sharpe ratio: {self.sharpe_ratio:.2f}",
        ]
        return "\n".join(lines)


# ── Backtesting engine ────────────────────────────────────────────


def run_backtest(
    instrument: Instrument = Instrument.US30,
    days: int = 20,
    capital: float = STARTING_CAPITAL,
    spread: float = 0.3,
    seed: int | None = 42,
) -> BacktestResult:
    """Run a full walk-forward backtest.

    Generates synthetic candle data, then walks bar-by-bar through the
    1M candles, building up the 3M and 5M views, running the exact same
    filters → strategies → scoring → risk pipeline as the live bot.
    """
    if seed is not None:
        np.random.seed(seed)

    # Generate 1M data, derive 3M and 5M
    df_1m_full = generate_candles(instrument, days=days)
    if df_1m_full.empty:
        return BacktestResult(
            instrument=instrument.value,
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
            starting_capital=capital,
            ending_capital=capital,
        )

    cfg = INSTRUMENT_CONFIGS[instrument]
    pv = POINT_VALUE[instrument]
    risk = RiskManager(balance=capital)
    trades: list[TradeRecord] = []
    equity_curve: list[float] = [capital]
    session_bar_count = 0
    prev_session_date_hour: tuple | None = None

    # We need at least 200 bars of lookback
    lookback = 200

    timestamps = df_1m_full.index.tolist()

    for i in range(lookback, len(df_1m_full)):
        now = timestamps[i]

        # Slice lookback window for 1M
        df_1m = df_1m_full.iloc[i - lookback + 1 : i + 1].copy()
        # Build 3M and 5M from available 1M data up to this point
        available = df_1m_full.iloc[: i + 1]
        df_3m = resample_candles(available, 3).iloc[-lookback:]
        df_5m = resample_candles(available, 5).iloc[-lookback:]

        if len(df_3m) < 30 or len(df_5m) < 30:
            continue

        # Track session bar count (reset on new session)
        current_key = (now.date(), now.hour // 4)
        if current_key != prev_session_date_hour:
            session_bar_count = 0
            prev_session_date_hour = current_key
        session_bar_count += 1

        # ── Manage open trades ────────────────────────────────
        current_price = df_1m["close"].iloc[-1]
        for trade_obj in list(risk.open_trades):
            bid = current_price - spread / 2
            ask = current_price + spread / 2
            price = bid if trade_obj.direction == 1 else ask

            # Check 1R partial close
            if not trade_obj.partial_closed:
                hit_1r = (
                    (trade_obj.direction == 1 and price >= trade_obj.take_profit_1r)
                    or (trade_obj.direction == -1 and price <= trade_obj.take_profit_1r)
                )
                if hit_1r:
                    pnl_partial = risk.partial_close(trade_obj, price, pv)
                    trades.append(TradeRecord(
                        instrument=instrument.value,
                        direction=trade_obj.direction,
                        strategy="partial",
                        entry_time=trade_obj._entry_time,
                        exit_time=now,
                        entry_price=trade_obj.entry_price,
                        exit_price=price,
                        size=trade_obj.size,
                        pnl=pnl_partial,
                        score=trade_obj._score,
                        exit_reason="partial_1r",
                    ))
                    trade_obj.stop_loss = trade_obj.entry_price  # move to breakeven
                    equity_curve.append(risk.balance)

            # Check stop loss
            stopped = (
                (trade_obj.direction == 1 and price <= trade_obj.stop_loss)
                or (trade_obj.direction == -1 and price >= trade_obj.stop_loss)
            )
            if stopped:
                pnl_close = risk.close_trade(trade_obj, price, pv)
                trades.append(TradeRecord(
                    instrument=instrument.value,
                    direction=trade_obj.direction,
                    strategy="close",
                    entry_time=trade_obj._entry_time,
                    exit_time=now,
                    entry_price=trade_obj.entry_price,
                    exit_price=price,
                    size=trade_obj.size,
                    pnl=pnl_close,
                    score=trade_obj._score,
                    exit_reason="stop_loss",
                ))
                equity_curve.append(risk.balance)

        # ── Drawdown check ────────────────────────────────────
        if risk.daily_drawdown_hit() or risk.weekly_drawdown_hit():
            continue

        if not risk.can_open_trade():
            continue

        # ── Entry filters ─────────────────────────────────────
        news_times: list[datetime] = []
        passed, session = all_filters_pass(
            df_5m, df_1m, instrument, spread, now, news_times,
        )
        if not passed:
            continue

        # ── Strategy signals ──────────────────────────────────
        signals = [
            ("ema_ribbon", ema_ribbon_scalp(df_1m)),
            ("vwap_rev", vwap_reversion(df_3m)),
            ("break_retest", break_and_retest(df_5m, df_1m)),
            ("orb", opening_range_breakout(df_1m, session_bar_count)),
        ]

        for name, direction in signals:
            if direction == 0:
                continue

            # ── Confluence scoring ────────────────────────────
            score = compute_confluence(direction, df_5m, df_3m, df_1m)
            if not score.triggered:
                continue

            # ── Execute trade ─────────────────────────────────
            atr_val = atr(df_5m, 14).iloc[-1]
            if pd.isna(atr_val) or atr_val == 0:
                continue

            entry = current_price + (spread / 2 if direction == 1 else -spread / 2)
            sl = entry - direction * cfg.stop_atr_mult * atr_val
            tp_1r = entry + direction * cfg.stop_atr_mult * atr_val

            size = risk.position_size(entry, sl, pv)
            if size <= 0:
                continue

            trade_obj = Trade(
                instrument=instrument.value,
                direction=direction,
                entry_price=entry,
                stop_loss=sl,
                take_profit_1r=tp_1r,
                size=size,
            )
            # Store backtest metadata on the trade object
            trade_obj._entry_time = now
            trade_obj._score = score.total
            trade_obj._strategy = name

            risk.open_trade(trade_obj)

            log.info(
                "[%s] %s %s %s score=%d/10 entry=%.2f sl=%.2f tp=%.2f size=%.2f",
                now.strftime("%Y-%m-%d %H:%M"),
                instrument.value,
                name,
                "LONG" if direction == 1 else "SHORT",
                score.total,
                entry, sl, tp_1r, size,
            )
            break  # one trade per bar

        # Day reset check (simplified: reset at start of London session)
        if now.hour == 7 and now.minute == 0:
            # Close any leftover trades from previous day
            for trade_obj in list(risk.open_trades):
                pnl = risk.close_trade(trade_obj, current_price, pv)
                trades.append(TradeRecord(
                    instrument=instrument.value,
                    direction=trade_obj.direction,
                    strategy=getattr(trade_obj, "_strategy", "unknown"),
                    entry_time=getattr(trade_obj, "_entry_time", now),
                    exit_time=now,
                    entry_price=trade_obj.entry_price,
                    exit_price=current_price,
                    size=trade_obj.size,
                    pnl=pnl,
                    score=getattr(trade_obj, "_score", 0),
                    exit_reason="session_end",
                ))
            risk.reset_day()
            equity_curve.append(risk.balance)

    # Close any remaining open trades at last price
    last_price = df_1m_full["close"].iloc[-1]
    for trade_obj in list(risk.open_trades):
        pnl = risk.close_trade(trade_obj, last_price, pv)
        trades.append(TradeRecord(
            instrument=instrument.value,
            direction=trade_obj.direction,
            strategy=getattr(trade_obj, "_strategy", "unknown"),
            entry_time=getattr(trade_obj, "_entry_time", timestamps[-1]),
            exit_time=timestamps[-1],
            entry_price=trade_obj.entry_price,
            exit_price=last_price,
            size=trade_obj.size,
            pnl=pnl,
            score=getattr(trade_obj, "_score", 0),
            exit_reason="backtest_end",
        ))
    equity_curve.append(risk.balance)

    return BacktestResult(
        instrument=instrument.value,
        start_date=timestamps[0],
        end_date=timestamps[-1],
        starting_capital=capital,
        ending_capital=risk.balance,
        trades=trades,
        equity_curve=equity_curve,
    )
