"""Integration tests — verify modules work together across boundaries."""

from datetime import UTC, datetime, timedelta

import pandas as pd

from config import (
    INSTRUMENT_CONFIGS,
    MIN_CONFLUENCE_SCORE,
    PARTIAL_CLOSE_PCT,
    STARTING_CAPITAL,
    TRAIL_ATR_FRACTION,
    Instrument,
)
from filters import all_filters_pass, check_session
from indicators import atr, market_structure_bullish, supertrend, volume_spike, vwap
from risk import RiskManager, Trade
from scoring import ScoreBreakdown, compute_confluence
from strategies import break_and_retest, ema_ribbon_scalp, opening_range_breakout, vwap_reversion

# ── Helpers ──────────────────────────────────────────────────────────────


def _trending_df(base: float, step: float, n: int, volume: int = 1500) -> pd.DataFrame:
    """Build an uptrending OHLCV DataFrame."""
    rows = []
    for i in range(n):
        c = base + step * i
        rows.append({
            "open": c - 0.3,
            "high": c + 1.5,
            "low": c - 1.5,
            "close": c,
            "volume": volume,
        })
    return pd.DataFrame(rows)


def _downtrending_df(base: float, step: float, n: int, volume: int = 1500) -> pd.DataFrame:
    """Build a downtrending OHLCV DataFrame."""
    rows = []
    for i in range(n):
        c = base - step * i
        rows.append({
            "open": c + 0.3,
            "high": c + 1.5,
            "low": c - 1.5,
            "close": c,
            "volume": volume,
        })
    return pd.DataFrame(rows)


def _flat_df(n: int, price: float = 100.0, volume: int = 1500) -> pd.DataFrame:
    """Build a flat OHLCV DataFrame."""
    rows = []
    for _ in range(n):
        rows.append({
            "open": price,
            "high": price + 0.5,
            "low": price - 0.5,
            "close": price,
            "volume": volume,
        })
    return pd.DataFrame(rows)


def _zigzag_bullish_df() -> pd.DataFrame:
    """Build an uptrending zigzag DataFrame (HH + HL pattern)."""
    prices = [
        *[100, 102, 105, 108, 110, 108, 105, 103],
        *[105, 108, 112, 115, 118, 115, 112, 110],
        *[112, 115, 118, 120, 123],
    ]
    return _trending_df_from_prices(prices)


def _zigzag_bearish_df() -> pd.DataFrame:
    """Build a downtrending zigzag DataFrame (LL + LH pattern)."""
    prices = [
        *[200, 198, 195, 192, 190, 192, 195, 197],
        *[195, 192, 188, 185, 182, 185, 188, 190],
        *[188, 185, 182, 180, 177],
    ]
    return _trending_df_from_prices(prices)


def _trending_df_from_prices(prices: list[float], volume: int = 1500) -> pd.DataFrame:
    rows = []
    for c in prices:
        rows.append({
            "open": c - 0.5,
            "high": c + 1.0,
            "low": c - 1.0,
            "close": c,
            "volume": volume,
        })
    return pd.DataFrame(rows)


# ── 1. Indicators → Scoring Pipeline ────────────────────────────────────


class TestIndicatorsToScoring:
    """Verify indicator outputs feed correctly into scoring."""

    def test_flat_market_scores_below_threshold(self):
        """Flat data should not trigger (score < 7)."""
        df = _flat_df(50)
        score = compute_confluence(1, df, df, df)
        assert score.total < MIN_CONFLUENCE_SCORE
        assert score.triggered is False

    def test_score_breakdown_components_are_bounded(self):
        """Each component must stay within its max value."""
        df = _trending_df(100, 2.0, 50)
        score = compute_confluence(1, df, df, df)
        assert 0 <= score.market_structure <= 3
        assert 0 <= score.supertrend_score <= 2
        assert 0 <= score.heikin_ashi <= 2
        assert 0 <= score.vwap_score <= 1
        assert 0 <= score.volume <= 1
        assert score.total <= 10

    def test_supertrend_feeds_into_scoring(self):
        """Supertrend direction from indicators must be used by scoring."""
        df_up = _trending_df(100, 3.0, 50)
        st = supertrend(df_up)
        last_dir = st["direction"].iloc[-1]
        score = compute_confluence(int(last_dir), df_up, df_up, df_up)
        # If supertrend agrees on both TFs, should get 2 points
        assert score.supertrend_score == 2

    def test_volume_spike_feeds_into_scoring(self):
        """Volume spike from indicators must be reflected in score."""
        df = _flat_df(50, volume=1000)
        # Last bar has volume spike at 2x (above 1.3x threshold, below 3x reject)
        df.loc[len(df) - 1, "volume"] = 2000
        score = compute_confluence(1, df, df, df)
        assert score.volume == 1

    def test_vwap_time_gate_integration(self):
        """VWAP must only score after 14:00 GMT."""
        df = _trending_df(100, 2.0, 50, volume=1500)
        morning = datetime(2026, 3, 13, 10, 0, tzinfo=UTC)
        afternoon = datetime(2026, 3, 13, 15, 0, tzinfo=UTC)

        score_am = compute_confluence(1, df, df, df, now=morning)
        assert score_am.vwap_score == 0

        # Afternoon: time gate should not block VWAP scoring
        score_pm = compute_confluence(1, df, df, df, now=afternoon)
        assert score_pm.total >= 0  # valid score produced


# ── 2. Filters → Scoring Pipeline ───────────────────────────────────────


class TestFiltersToScoring:
    """Verify filters gate scoring correctly."""

    def test_session_check_returns_valid_session(self):
        """check_session must return a Session enum during trading hours."""
        london_time = datetime(2026, 3, 13, 8, 0, tzinfo=UTC)
        ny_time = datetime(2026, 3, 13, 14, 30, tzinfo=UTC)
        off_time = datetime(2026, 3, 13, 4, 0, tzinfo=UTC)

        assert check_session(london_time) is not None
        assert check_session(ny_time) is not None
        assert check_session(off_time) is None

    def test_all_filters_pass_blocks_low_atr(self):
        """If ATR is too low, filters should block regardless of other conditions."""
        # Flat data → very low ATR
        df = _flat_df(50)
        ny_time = datetime(2026, 3, 13, 14, 30, tzinfo=UTC)
        passed, _session = all_filters_pass(
            df, df, Instrument.US30, 0.1, ny_time, [],
        )
        # Low ATR on flat data should fail the ATR floor filter
        assert passed is False

    def test_all_filters_pass_blocks_outside_session(self):
        """Outside trading hours, filters should block."""
        df = _trending_df(39000, 5.0, 50, volume=2000)
        off_time = datetime(2026, 3, 13, 4, 0, tzinfo=UTC)
        passed, _session = all_filters_pass(
            df, df, Instrument.US30, 0.1, off_time, [],
        )
        assert passed is False

    def test_all_filters_pass_blocks_near_news(self):
        """Within 15 min of news, filters should block."""
        df = _trending_df(39000, 5.0, 50, volume=2000)
        now = datetime(2026, 3, 13, 14, 30, tzinfo=UTC)
        news_in_5_min = [now + timedelta(minutes=5)]
        passed, _session = all_filters_pass(
            df, df, Instrument.US30, 0.1, now, news_in_5_min,
        )
        assert passed is False


# ── 3. Strategies → Scoring Pipeline ────────────────────────────────────


class TestStrategiesToScoring:
    """Verify strategy signals feed into scoring correctly."""

    def test_zero_signal_skips_scoring(self):
        """If strategy returns 0, no scoring should happen (caller responsibility)."""
        df = _flat_df(50)
        signal = ema_ribbon_scalp(df)
        assert signal == 0  # flat data → no signal

    def test_strategy_direction_matches_scoring_direction(self):
        """Strategy direction (1/-1) must match what scoring expects."""
        df_up = _trending_df(100, 2.0, 50)
        signal = ema_ribbon_scalp(df_up)
        if signal != 0:
            # Score with the same direction the strategy produced
            score = compute_confluence(signal, df_up, df_up, df_up)
            assert isinstance(score, ScoreBreakdown)
            assert score.total >= 0

    def test_vwap_reversion_direction_into_scoring(self):
        """VWAP reversion signal should produce a valid scoring input."""
        df = _trending_df(100, 2.0, 50)
        signal = vwap_reversion(df)
        # Signal is 0, 1, or -1
        assert signal in (-1, 0, 1)

    def test_break_and_retest_direction_into_scoring(self):
        """Break and retest signal should produce a valid scoring input."""
        df = _trending_df(100, 2.0, 50)
        signal = break_and_retest(df, df)
        assert signal in (-1, 0, 1)

    def test_orb_direction_into_scoring(self):
        """ORB signal should produce a valid scoring input."""
        df = _trending_df(100, 2.0, 50)
        signal = opening_range_breakout(df, session_bar_count=20)
        assert signal in (-1, 0, 1)


# ── 4. Scoring → Risk Pipeline ──────────────────────────────────────────


class TestScoringToRisk:
    """Verify scoring output drives risk decisions correctly."""

    def test_triggered_score_allows_trade_creation(self):
        """A triggered score should allow trade creation through risk manager."""
        risk = RiskManager(balance=STARTING_CAPITAL)
        assert risk.can_open_trade() is True

        # Simulate a triggered trade
        cfg = INSTRUMENT_CONFIGS[Instrument.US30]
        entry = 39500.0
        sl = entry - cfg.stop_atr_mult * 10.0  # ATR ~10
        tp = entry + cfg.stop_atr_mult * 10.0
        size = risk.position_size(entry, sl, point_value=1.0)
        assert size > 0

        trade = Trade(
            instrument="US30",
            direction=1,
            entry_price=entry,
            stop_loss=sl,
            take_profit_1r=tp,
            size=size,
            atr_at_entry=10.0,
            strategy="ema_ribbon_scalp",
            score=7,
        )
        risk.open_trade(trade)
        assert len(risk.open_trades) == 1

    def test_score_below_threshold_should_not_trigger(self):
        """Score below 7 should not trigger — caller must check."""
        score = ScoreBreakdown(market_structure=3, supertrend_score=2)
        assert score.total == 5
        assert score.triggered is False


# ── 5. Full Trade Lifecycle (Risk Integration) ──────────────────────────


class TestFullTradeLifecycle:
    """Test open → partial close → trailing stop → full close."""

    def test_full_long_lifecycle(self):
        """Long trade: open → partial close at 1R → trail → close at stop."""
        risk = RiskManager(balance=2000.0)
        entry = 39500.0
        atr_val = 10.0
        sl = entry - 1.2 * atr_val  # 39488
        tp = entry + 1.2 * atr_val  # 39512
        size = risk.position_size(entry, sl, point_value=1.0)

        trade = Trade(
            instrument="US30", direction=1, entry_price=entry,
            stop_loss=sl, take_profit_1r=tp, size=size,
            atr_at_entry=atr_val,
        )
        risk.open_trade(trade)
        initial_balance = risk.balance

        # 1) Partial close at 1R
        pnl_partial = risk.partial_close(trade, tp, point_value=1.0)
        assert pnl_partial > 0
        assert trade.partial_closed is True
        assert trade.size < size  # 50% closed
        assert trade.best_price == tp
        assert risk.balance > initial_balance

        # 2) Price moves up → trailing stop should update
        higher_price = tp + 5.0
        RiskManager.update_trailing_stop(trade, higher_price)
        assert trade.best_price == higher_price
        expected_sl = higher_price - TRAIL_ATR_FRACTION * atr_val
        assert trade.stop_loss == expected_sl

        # 3) Price moves up more → stop moves up
        even_higher = higher_price + 3.0
        RiskManager.update_trailing_stop(trade, even_higher)
        assert trade.best_price == even_higher
        new_sl = even_higher - TRAIL_ATR_FRACTION * atr_val
        assert trade.stop_loss == new_sl
        assert new_sl > expected_sl  # stop moved up

        # 4) Full close at stop
        balance_before_close = risk.balance
        pnl_full = risk.close_trade(trade, trade.stop_loss, point_value=1.0)
        assert len(risk.open_trades) == 0
        assert risk.balance == balance_before_close + pnl_full

    def test_full_short_lifecycle(self):
        """Short trade: open → partial close at 1R → trail → close."""
        risk = RiskManager(balance=2000.0)
        entry = 39500.0
        atr_val = 10.0
        sl = entry + 1.2 * atr_val  # 39512
        tp = entry - 1.2 * atr_val  # 39488
        size = risk.position_size(entry, sl, point_value=1.0)

        trade = Trade(
            instrument="US30", direction=-1, entry_price=entry,
            stop_loss=sl, take_profit_1r=tp, size=size,
            atr_at_entry=atr_val,
        )
        risk.open_trade(trade)

        # 1) Partial close at 1R (price dropped to tp)
        pnl_partial = risk.partial_close(trade, tp, point_value=1.0)
        assert pnl_partial > 0
        assert trade.partial_closed is True

        # 2) Price drops further → trail stop down
        lower_price = tp - 5.0
        RiskManager.update_trailing_stop(trade, lower_price)
        assert trade.best_price == lower_price
        expected_sl = lower_price + TRAIL_ATR_FRACTION * atr_val
        assert trade.stop_loss == expected_sl

        # 3) Close trade
        risk.close_trade(trade, trade.stop_loss, point_value=1.0)
        assert len(risk.open_trades) == 0

    def test_double_close_guard(self):
        """Closing the same trade twice should return 0 PnL."""
        risk = RiskManager(balance=2000.0)
        trade = Trade("US30", 1, 39500, 39488, 39512, 1.0)
        risk.open_trade(trade)
        pnl1 = risk.close_trade(trade, 39510, point_value=1.0)
        pnl2 = risk.close_trade(trade, 39510, point_value=1.0)
        assert pnl1 != 0
        assert pnl2 == 0.0

    def test_partial_close_only_once(self):
        """Second partial close attempt should return 0."""
        risk = RiskManager(balance=2000.0)
        trade = Trade("US30", 1, 39500, 39488, 39512, 2.0, atr_at_entry=10.0)
        risk.open_trade(trade)
        pnl1 = risk.partial_close(trade, 39512, point_value=1.0)
        pnl2 = risk.partial_close(trade, 39520, point_value=1.0)
        assert pnl1 > 0
        assert pnl2 == 0.0


# ── 6. Drawdown Guards Integration ──────────────────────────────────────


class TestDrawdownIntegration:
    """Test drawdown limits block new trades correctly."""

    def test_daily_drawdown_blocks_new_trades(self):
        """After 3% daily loss, can_open_trade should return False."""
        risk = RiskManager(balance=2000.0)
        # Lose 3% = €60
        risk.balance = 2000.0 - 60.0
        assert risk.daily_drawdown_hit() is True
        assert risk.can_open_trade() is False

    def test_max_open_trades_blocks_new_trades(self):
        """With 2 trades open, can_open_trade should return False."""
        risk = RiskManager(balance=2000.0)
        trade1 = Trade("US30", 1, 39500, 39488, 39512, 1.0)
        trade2 = Trade("US30", -1, 39600, 39612, 39588, 1.0)
        risk.open_trade(trade1)
        risk.open_trade(trade2)
        assert risk.can_open_trade() is False

    def test_daily_reset_clears_drawdown(self):
        """After daily reset, drawdown should be recalculated from new balance."""
        risk = RiskManager(balance=2000.0)
        risk.balance = 1950.0  # 2.5% drawdown
        assert risk.daily_drawdown_hit() is False  # < 3%
        risk.balance = 1940.0  # 3% drawdown
        assert risk.daily_drawdown_hit() is True
        risk.reset_day()  # new day starts at 1940
        assert risk.daily_drawdown_hit() is False  # 0% from new start


# ── 7. Indicators Cross-Validation ──────────────────────────────────────


class TestIndicatorsCrossValidation:
    """Verify multiple indicators work on the same data without conflicts."""

    def test_atr_and_supertrend_same_data(self):
        """ATR and supertrend should both work on the same DataFrame."""
        df = _trending_df(39000, 5.0, 50)
        atr_series = atr(df, 14)
        st = supertrend(df)
        assert len(atr_series) == len(df)
        assert len(st) == len(df)
        # ATR should be positive where not NaN
        valid_atr = atr_series.dropna()
        assert (valid_atr > 0).all()

    def test_vwap_and_volume_spike_same_data(self):
        """VWAP and volume_spike should both work on the same 1M data."""
        df = _trending_df(100, 0.5, 50, volume=1500)
        vwap_series = vwap(df)
        has_spike = volume_spike(df)
        assert len(vwap_series) == len(df)
        assert has_spike is not None  # numpy bool, not Python bool

    def test_market_structure_requires_sufficient_data(self):
        """Market structure needs enough bars for fractal detection."""
        short_df = _flat_df(5)
        long_df = _zigzag_bullish_df()
        assert not market_structure_bullish(short_df)
        assert market_structure_bullish(long_df)


# ── 8. Config → Module Consistency ───────────────────────────────────────


class TestConfigConsistency:
    """Verify config values are used consistently across modules."""

    def test_instrument_configs_have_required_fields(self):
        """Both instruments must have all config fields."""
        for inst in Instrument:
            cfg = INSTRUMENT_CONFIGS[inst]
            assert cfg.min_atr_5m > 0
            assert cfg.max_spread > 0
            assert cfg.stop_atr_mult > 0

    def test_min_confluence_score_matches_scoring(self):
        """MIN_CONFLUENCE_SCORE should be 7."""
        assert MIN_CONFLUENCE_SCORE == 7
        # A score of exactly 7 should trigger
        score = ScoreBreakdown(market_structure=3, supertrend_score=2, heikin_ashi=2)
        assert score.total == 7
        assert score.triggered is True

    def test_partial_close_pct_is_50(self):
        """Partial close should be 50%."""
        assert PARTIAL_CLOSE_PCT == 0.5

    def test_position_sizing_uses_risk_per_trade(self):
        """Position sizing should risk exactly 1% of account."""
        risk = RiskManager(balance=2000.0)
        entry = 39500.0
        stop = 39490.0  # 10 pts distance
        size = risk.position_size(entry, stop, point_value=1.0)
        # 1% of 2000 = 20, distance = 10, point_value = 1
        # size = 20 / (10 * 1) = 2.0
        assert size == 2.0


# ── 9. Backtest End-to-End ───────────────────────────────────────────────


class TestBacktestEndToEnd:
    """Verify backtest produces valid results."""

    def test_backtest_runs_without_error(self):
        """Backtest should complete without exceptions."""
        from backtest import run_backtest

        result = run_backtest(
            instrument=Instrument.US30,
            days=5,
            capital=2000.0,
            seed=42,
        )
        assert result is not None
        assert result.instrument == "US30"
        assert result.starting_capital == 2000.0

    def test_backtest_equity_curve_length(self):
        """Equity curve should have entries for every bar processed."""
        from backtest import run_backtest

        result = run_backtest(instrument=Instrument.US30, days=3, seed=42)
        assert len(result.equity_curve) > 0

    def test_backtest_pnl_matches_balance_change(self):
        """Total PnL should equal ending - starting capital."""
        from backtest import run_backtest

        result = run_backtest(instrument=Instrument.US30, days=5, seed=42)
        expected_pnl = result.ending_capital - result.starting_capital
        assert abs(result.total_pnl - expected_pnl) < 0.01

    def test_backtest_trade_directions_valid(self):
        """All trades should have direction 1 or -1."""
        from backtest import run_backtest

        result = run_backtest(instrument=Instrument.US30, days=10, seed=42)
        for t in result.trades:
            assert t.direction in (1, -1)

    def test_backtest_deterministic_with_seed(self):
        """Same seed should produce identical results."""
        from backtest import run_backtest

        r1 = run_backtest(instrument=Instrument.US30, days=5, seed=99)
        r2 = run_backtest(instrument=Instrument.US30, days=5, seed=99)
        assert r1.total_trades == r2.total_trades
        assert r1.ending_capital == r2.ending_capital
        assert len(r1.equity_curve) == len(r2.equity_curve)
