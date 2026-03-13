"""CLI entry point for running backtests."""

import argparse
import json

from backtest import run_backtest
from config import STARTING_CAPITAL, Instrument, setup_logging


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Run a walk-forward backtest on synthetic market data.",
    )
    parser.add_argument(
        "instrument",
        nargs="?",
        default="US30",
        choices=["US30", "SPX"],
        help="Instrument to backtest (default: US30)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=20,
        help="Number of trading days to simulate (default: 20)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=STARTING_CAPITAL,
        help=f"Starting capital in EUR (default: {STARTING_CAPITAL})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON (for piping / automation)",
    )
    parser.add_argument(
        "--no-trades",
        action="store_true",
        help="Suppress individual trade log",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )
    return parser


def _result_to_dict(result) -> dict:
    """Convert BacktestResult to a JSON-serializable dict."""
    return {
        "instrument": result.instrument,
        "start_date": result.start_date.isoformat(),
        "end_date": result.end_date.isoformat(),
        "starting_capital": result.starting_capital,
        "ending_capital": result.ending_capital,
        "total_pnl": round(result.total_pnl, 2),
        "total_trades": result.total_trades,
        "winning_trades": result.winning_trades,
        "losing_trades": result.losing_trades,
        "win_rate": round(result.win_rate, 4),
        "avg_pnl": round(result.avg_pnl, 2),
        "profit_factor": round(result.profit_factor, 2),
        "max_drawdown": round(result.max_drawdown, 4),
        "sharpe_ratio": round(result.sharpe_ratio, 2),
        "trades": [
            {
                "time": t.entry_time.isoformat(),
                "direction": "LONG" if t.direction == 1 else "SHORT",
                "strategy": t.strategy,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl": round(t.pnl, 2),
                "exit_reason": t.exit_reason,
            }
            for t in result.trades
        ],
    }


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    setup_logging(log_level=args.log_level)

    instrument = Instrument[args.instrument]

    result = run_backtest(
        instrument=instrument,
        days=args.days,
        seed=args.seed,
        capital=args.capital,
    )

    if args.json_output:
        print(json.dumps(_result_to_dict(result), indent=2))
        return

    print(f"\nRunning backtest: {instrument.value}, {args.days} days, seed={args.seed}\n")
    print(result.summary())

    if not args.no_trades and result.trades:
        print(f"\n{'─' * 80}")
        print(f"{'Time':<18} {'Dir':<6} {'Strategy':<14} {'Entry':>10} {'Exit':>10} {'PnL':>10} {'Reason':<12}")
        print(f"{'─' * 80}")
        for t in result.trades:
            dir_str = "LONG" if t.direction == 1 else "SHORT"
            print(
                f"{t.entry_time:%Y-%m-%d %H:%M}  {dir_str:<6} {t.strategy:<14} "
                f"{t.entry_price:>10.2f} {t.exit_price:>10.2f} {t.pnl:>+10.2f} {t.exit_reason:<12}"
            )
    elif not result.trades:
        print("\nNo trades generated. Try adjusting parameters or increasing days.")


if __name__ == "__main__":
    main()
