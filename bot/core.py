"""Main bot loop — ties together filters, scoring, strategies, risk, and broker."""

from __future__ import annotations

import logging
import signal
import time
from datetime import datetime, timezone

from bot.db import TradeLogger
from broker import CTraderBroker
from config import (
    INSTRUMENT_CONFIGS,
    STARTING_CAPITAL,
    Instrument,
)
from filters import all_filters_pass, get_upcoming_events, is_market_safe
from indicators import atr
from risk import RiskManager, Trade
from scoring import compute_confluence
from strategies import (
    break_and_retest,
    ema_ribbon_scalp,
    opening_range_breakout,
    vwap_reversion,
)

log = logging.getLogger("bot")

# ── Symbol mapping ───────────────────────────────────────────────
SYMBOL_MAP = {
    Instrument.US30: "US30",
    Instrument.SPX: "US500",
}
SYMBOL_TO_INSTRUMENT = {v: k for k, v in SYMBOL_MAP.items()}
POINT_VALUE = {
    Instrument.US30: 1.0,   # adjust per broker contract spec
    Instrument.SPX: 1.0,
}


class ScalpingBot:
    def __init__(
        self,
        broker: CTraderBroker,
        instruments: list[Instrument] | None = None,
    ) -> None:
        self.broker = broker
        self.instruments = instruments or [Instrument.US30, Instrument.SPX]
        self.risk = RiskManager(balance=STARTING_CAPITAL)
        self.db = TradeLogger()
        self._running = False
        self._session_bar_counts: dict[Instrument, int] = {}
        self._last_reset_day: int | None = None
        self._last_reset_week: int | None = None
        self._daily_trades: int = 0
        self._daily_wins: int = 0
        self._daily_losses: int = 0
        self._daily_pnl: float = 0.0

    # ── Main loop ────────────────────────────────────────────────

    def run(self) -> None:
        self.broker.connect()
        self.db.connect()
        self._running = True
        self._install_signal_handlers()
        log.info("Bot started. Balance: €%.2f", self.risk.balance)

        try:
            while self._running:
                self._tick()
                time.sleep(5)  # poll every 5 seconds
        except KeyboardInterrupt:
            log.info("Keyboard interrupt received.")
        finally:
            self._shutdown()

    def stop(self) -> None:
        self._running = False

    # ── Signal handling ─────────────────────────────────────────

    def _install_signal_handlers(self) -> None:
        """Handle SIGINT and SIGTERM for graceful shutdown."""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum: int, frame) -> None:
        sig_name = signal.Signals(signum).name
        log.info("Received %s — initiating graceful shutdown…", sig_name)
        self._running = False

    def _shutdown(self) -> None:
        """Close all open positions, log daily summary, disconnect."""
        log.info("Shutting down — closing %d open positions…", len(self.risk.open_trades))
        now = datetime.now(timezone.utc)

        for trade in list(self.risk.open_trades):
            try:
                tick = self.broker.get_tick(trade.instrument)
                price = tick.bid if trade.direction == 1 else tick.ask
                pnl = self.risk.close_trade(trade, price, self._pv(trade))
                log.info("SHUTDOWN CLOSE %s @ %.2f PnL=%.2f", trade.instrument, price, pnl)
                self._record_close(trade, now, price, pnl, "shutdown")
            except Exception:
                log.exception("Failed to close %s during shutdown", trade.instrument)

        self._write_daily_summary(now)
        self.db.disconnect()
        self.broker.disconnect()
        log.info("Shutdown complete. Final balance: €%.2f", self.risk.balance)

    # ── Core tick ────────────────────────────────────────────────

    def _tick(self) -> None:
        now = datetime.now(timezone.utc)

        # Day/week reset checks
        self._check_resets(now)

        # Check breaking news — block new trades if major event
        if not is_market_safe():
            log.warning("Breaking news detected — skipping new trades.")
            self._manage_open_trades()
            return

        # Check drawdown limits
        if self.risk.daily_drawdown_hit():
            log.warning("Daily drawdown limit hit — halting.")
            self._running = False
            return

        if self.risk.weekly_drawdown_hit():
            log.warning("Weekly drawdown limit hit — manual review required.")
            self._running = False
            return

        # Manage open trades (partial close / trailing stop)
        self._manage_open_trades()

        for instrument in self.instruments:
            try:
                self._evaluate_instrument(instrument, now)
            except Exception:
                log.exception("Error evaluating %s — skipping to next instrument", instrument)

    # ── Day/week resets ─────────────────────────────────────────

    def _check_resets(self, now: datetime) -> None:
        """Reset daily/weekly counters at the start of each new day/week."""
        today = now.toordinal()
        week_num = now.isocalendar()[1]

        # Daily reset
        if self._last_reset_day is not None and today != self._last_reset_day:
            log.info(
                "Day reset — yesterday: %d trades, PnL €%.2f, balance €%.2f",
                self._daily_trades, self._daily_pnl, self.risk.balance,
            )
            self._write_daily_summary(now)
            self.risk.reset_day()
            self._daily_trades = 0
            self._daily_wins = 0
            self._daily_losses = 0
            self._daily_pnl = 0.0
            self._session_bar_counts.clear()
        self._last_reset_day = today

        # Weekly reset (on new ISO week)
        if self._last_reset_week is not None and week_num != self._last_reset_week:
            log.info("Week reset — new ISO week %d, balance €%.2f", week_num, self.risk.balance)
            self.risk.reset_week()
        self._last_reset_week = week_num

    # ── Instrument evaluation ────────────────────────────────────

    def _evaluate_instrument(self, instrument: Instrument, now: datetime) -> None:
        if not self.risk.can_open_trade():
            return

        symbol = SYMBOL_MAP[instrument]
        tick = self.broker.get_tick(symbol)

        # Fetch candles for all three timeframes
        df_1m = self.broker.get_candles(symbol, "1m", 200)
        df_3m = self.broker.get_candles(symbol, "3m", 200)
        df_5m = self.broker.get_candles(symbol, "5m", 200)

        if df_1m.empty or df_3m.empty or df_5m.empty:
            return

        # Fetch upcoming high-impact news events
        news_times = get_upcoming_events(now)

        # ── Entry filters ────────────────────────────────────────
        passed, session = all_filters_pass(
            df_5m, df_1m, instrument, tick.spread, now, news_times,
        )
        if not passed:
            return

        # Track bars since session open for ORB
        bar_count = self._session_bar_counts.get(instrument, 0) + 1
        self._session_bar_counts[instrument] = bar_count

        # ── Strategy signals ─────────────────────────────────────
        signals = [
            ("ema_ribbon", ema_ribbon_scalp(df_1m)),
            ("vwap_rev", vwap_reversion(df_3m)),
            ("break_retest", break_and_retest(df_5m, df_1m)),
            ("orb", opening_range_breakout(df_1m, bar_count)),
        ]

        for name, direction in signals:
            if direction == 0:
                continue

            # ── Confluence scoring ───────────────────────────────
            score = compute_confluence(direction, df_5m, df_3m, df_1m, now)
            log.info(
                "%s %s signal=%s score=%d/10 %s",
                symbol, name,
                "LONG" if direction == 1 else "SHORT",
                score.total, score,
            )

            if not score.triggered:
                continue

            # ── Execute trade ────────────────────────────────────
            self._execute_trade(instrument, symbol, direction, name, score.total, df_5m, tick)
            break  # one trade per instrument per tick

    # ── Trade execution ──────────────────────────────────────────

    def _execute_trade(
        self,
        instrument: Instrument,
        symbol: str,
        direction: int,
        strategy: str,
        score: int,
        df_5m,
        tick,
    ) -> None:
        cfg = INSTRUMENT_CONFIGS[instrument]
        pv = POINT_VALUE[instrument]
        atr_val = atr(df_5m, 14).iloc[-1]
        entry = tick.ask if direction == 1 else tick.bid
        sl = entry - direction * cfg.stop_atr_mult * atr_val
        tp_1r = entry + direction * cfg.stop_atr_mult * atr_val  # 1R target

        size = self.risk.position_size(entry, sl, pv)
        if size <= 0:
            return

        self.broker.market_order(
            symbol=symbol,
            direction=direction,
            volume=size,
            stop_loss=sl,
            take_profit=tp_1r,
            label=f"scalp-{symbol}",
        )

        now = datetime.now(timezone.utc)
        trade = Trade(
            instrument=symbol,
            direction=direction,
            entry_price=entry,
            stop_loss=sl,
            take_profit_1r=tp_1r,
            size=size,
            atr_at_entry=atr_val,
            entry_time=now,
            strategy=strategy,
            score=score,
        )

        # Log to MySQL
        trade.db_id = self.db.log_trade_open(
            opened_at=now,
            instrument=symbol,
            direction=direction,
            strategy=trade.strategy,
            score=trade.score,
            entry_price=entry,
            stop_loss=sl,
            take_profit_1r=tp_1r,
            size=size,
        )

        self.risk.open_trade(trade)
        log.info("OPENED %s %s @ %.2f SL=%.2f TP=%.2f size=%.2f",
                 "LONG" if direction == 1 else "SHORT",
                 symbol, entry, sl, tp_1r, size)

    # ── Open trade management ────────────────────────────────────

    def _manage_open_trades(self) -> None:
        """Partial close at 1R, trail stop on remainder."""
        now = datetime.now(timezone.utc)
        for trade in list(self.risk.open_trades):
            tick = self.broker.get_tick(trade.instrument)
            price = tick.bid if trade.direction == 1 else tick.ask

            # Check if 1R target hit → partial close
            if not trade.partial_closed:
                hit_1r = (
                    (trade.direction == 1 and price >= trade.take_profit_1r)
                    or (trade.direction == -1 and price <= trade.take_profit_1r)
                )
                if hit_1r:
                    pnl = self.risk.partial_close(trade, price, self._pv(trade))
                    log.info("PARTIAL CLOSE %s @ %.2f PnL=%.2f", trade.instrument, price, pnl)
                    self._record_pnl(pnl)
                    if trade.db_id is not None:
                        self.db.log_partial_close(
                            trade_id=trade.db_id,
                            closed_at=now,
                            exit_price=price,
                            pnl=pnl,
                            remaining_size=trade.size,
                        )

            # Trail stop after partial close
            self.risk.update_trailing_stop(trade, price)

            # Check stop loss
            stopped = (
                (trade.direction == 1 and price <= trade.stop_loss)
                or (trade.direction == -1 and price >= trade.stop_loss)
            )
            if stopped:
                pnl = self.risk.close_trade(trade, price, self._pv(trade))
                log.info("STOPPED OUT %s @ %.2f PnL=%.2f", trade.instrument, price, pnl)
                self._record_close(trade, now, price, pnl, "stop_loss")

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _pv(trade: Trade) -> float:
        """Look up point value for a trade's instrument."""
        inst = SYMBOL_TO_INSTRUMENT.get(trade.instrument)
        return POINT_VALUE.get(inst, 1.0) if inst else 1.0

    # ── DB + stats helpers ──────────────────────────────────────

    def _record_pnl(self, pnl: float) -> None:
        """Track daily stats for partial closes."""
        self._daily_pnl += pnl

    def _record_close(self, trade: Trade, now: datetime, price: float, pnl: float, reason: str) -> None:
        """Log a full close to DB and update daily stats."""
        self._daily_trades += 1
        self._daily_pnl += pnl
        if pnl > 0:
            self._daily_wins += 1
        else:
            self._daily_losses += 1

        if trade.db_id is not None:
            self.db.log_trade_close(
                trade_id=trade.db_id,
                closed_at=now,
                exit_price=price,
                pnl=pnl,
                exit_reason=reason,
                balance_after=self.risk.balance,
            )

    def _write_daily_summary(self, now: datetime) -> None:
        """Write the day's stats to MySQL."""
        self.db.log_daily_summary(
            trade_date=now.date(),
            starting_balance=self.risk.day_start_balance,
            ending_balance=self.risk.balance,
            total_trades=self._daily_trades,
            wins=self._daily_wins,
            losses=self._daily_losses,
            total_pnl=self._daily_pnl,
            max_drawdown_pct=(
                (self.risk.day_start_balance - self.risk.balance) / self.risk.day_start_balance
                if self.risk.day_start_balance > 0 else 0.0
            ),
        )
