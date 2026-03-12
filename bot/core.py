"""Main bot loop — ties together filters, scoring, strategies, risk, and broker."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from broker import CTraderBroker
from config import (
    INSTRUMENT_CONFIGS,
    STARTING_CAPITAL,
    Instrument,
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

log = logging.getLogger("bot")

# ── Symbol mapping ───────────────────────────────────────────────
SYMBOL_MAP = {
    Instrument.US30: "US30",
    Instrument.SPX: "US500",
}
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
        self._running = False
        self._session_bar_counts: dict[Instrument, int] = {}

    # ── Main loop ────────────────────────────────────────────────

    def run(self) -> None:
        self.broker.connect()
        self._running = True
        log.info("Bot started. Balance: €%.2f", self.risk.balance)

        try:
            while self._running:
                self._tick()
                time.sleep(5)  # poll every 5 seconds
        except KeyboardInterrupt:
            log.info("Shutting down…")
        finally:
            self.broker.disconnect()

    def stop(self) -> None:
        self._running = False

    # ── Core tick ────────────────────────────────────────────────

    def _tick(self) -> None:
        now = datetime.now(timezone.utc)

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
            self._evaluate_instrument(instrument, now)

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

        # News times — placeholder, will integrate a news feed later
        news_times: list[datetime] = []

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
            score = compute_confluence(direction, df_5m, df_3m, df_1m)
            log.info(
                "%s %s signal=%s score=%d/10 %s",
                symbol, name,
                "LONG" if direction == 1 else "SHORT",
                score.total, score,
            )

            if not score.triggered:
                continue

            # ── Execute trade ────────────────────────────────────
            self._execute_trade(instrument, symbol, direction, df_5m, tick)
            break  # one trade per instrument per tick

    # ── Trade execution ──────────────────────────────────────────

    def _execute_trade(
        self,
        instrument: Instrument,
        symbol: str,
        direction: int,
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

        order_id = self.broker.market_order(
            symbol=symbol,
            direction=direction,
            volume=size,
            stop_loss=sl,
            take_profit=tp_1r,
            label=f"scalp-{symbol}",
        )

        trade = Trade(
            instrument=symbol,
            direction=direction,
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
                    pnl = self.risk.partial_close(trade, price, POINT_VALUE.get(
                        Instrument.US30, 1.0))  # simplified
                    log.info("PARTIAL CLOSE %s @ %.2f PnL=%.2f", trade.instrument, price, pnl)
                    # Move stop to breakeven
                    trade.stop_loss = trade.entry_price

            # Check stop loss
            stopped = (
                (trade.direction == 1 and price <= trade.stop_loss)
                or (trade.direction == -1 and price >= trade.stop_loss)
            )
            if stopped:
                pnl = self.risk.close_trade(trade, price, POINT_VALUE.get(
                    Instrument.US30, 1.0))
                log.info("STOPPED OUT %s @ %.2f PnL=%.2f", trade.instrument, price, pnl)
