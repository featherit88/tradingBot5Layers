"""CLI entry point for running backtests."""

import sys

from backtest import run_backtest
from config import Instrument, setup_logging

setup_logging()


def main() -> None:
    instrument = Instrument.US30
    days = 20
    seed = 42

    # Parse simple CLI args
    for arg in sys.argv[1:]:
        if arg.upper() in ("SPX", "US500"):
            instrument = Instrument.SPX
        elif arg.upper() in ("US30",):
            instrument = Instrument.US30
        elif arg.startswith("--days="):
            days = int(arg.split("=")[1])
        elif arg.startswith("--seed="):
            seed = int(arg.split("=")[1])

    print(f"\nRunning backtest: {instrument.value}, {days} days, seed={seed}\n")

    result = run_backtest(
        instrument=instrument,
        days=days,
        seed=seed,
    )

    print(result.summary())

    # Print trade log
    if result.trades:
        print(f"\n{'─' * 80}")
        print(f"{'Time':<18} {'Dir':<6} {'Strategy':<14} {'Entry':>10} {'Exit':>10} {'PnL':>10} {'Reason':<12}")
        print(f"{'─' * 80}")
        for t in result.trades:
            dir_str = "LONG" if t.direction == 1 else "SHORT"
            print(
                f"{t.entry_time:%Y-%m-%d %H:%M}  {dir_str:<6} {t.strategy:<14} "
                f"{t.entry_price:>10.2f} {t.exit_price:>10.2f} {t.pnl:>+10.2f} {t.exit_reason:<12}"
            )
    else:
        print("\nNo trades generated. Try adjusting parameters or increasing days.")


if __name__ == "__main__":
    main()
