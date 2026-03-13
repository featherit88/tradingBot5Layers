"""Tests for run_backtest.py CLI argument parsing and output."""

import json

from run_backtest import _build_parser, main


class TestArgParser:
    """Verify CLI argument parsing."""

    def test_default_args(self):
        """No args → US30, 20 days, seed 42."""
        parser = _build_parser()
        args = parser.parse_args([])
        assert args.instrument == "US30"
        assert args.days == 20
        assert args.seed == 42
        assert args.json_output is False
        assert args.no_trades is False
        assert args.log_level == "INFO"

    def test_spx_instrument(self):
        """Positional 'SPX' sets instrument."""
        parser = _build_parser()
        args = parser.parse_args(["SPX"])
        assert args.instrument == "SPX"

    def test_custom_days_and_seed(self):
        """--days and --seed override defaults."""
        parser = _build_parser()
        args = parser.parse_args(["--days=50", "--seed=99"])
        assert args.days == 50
        assert args.seed == 99

    def test_custom_capital(self):
        """--capital overrides starting capital."""
        parser = _build_parser()
        args = parser.parse_args(["--capital=5000"])
        assert args.capital == 5000.0

    def test_json_flag(self):
        """--json enables JSON output."""
        parser = _build_parser()
        args = parser.parse_args(["--json"])
        assert args.json_output is True

    def test_no_trades_flag(self):
        """--no-trades suppresses trade log."""
        parser = _build_parser()
        args = parser.parse_args(["--no-trades"])
        assert args.no_trades is True

    def test_log_level(self):
        """--log-level sets verbosity."""
        parser = _build_parser()
        args = parser.parse_args(["--log-level=DEBUG"])
        assert args.log_level == "DEBUG"

    def test_combined_flags(self):
        """All flags combined."""
        parser = _build_parser()
        args = parser.parse_args(["SPX", "--days=10", "--seed=7", "--json", "--no-trades", "--log-level=WARNING"])
        assert args.instrument == "SPX"
        assert args.days == 10
        assert args.seed == 7
        assert args.json_output is True
        assert args.no_trades is True
        assert args.log_level == "WARNING"


class TestJsonOutput:
    """Verify JSON output mode produces valid, parseable JSON."""

    def test_json_output_is_valid(self, capsys):
        """--json flag produces valid JSON to stdout."""
        main(["US30", "--days=5", "--seed=42", "--json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["instrument"] == "US30"
        assert "total_trades" in data
        assert "win_rate" in data
        assert "trades" in data
        assert isinstance(data["trades"], list)

    def test_json_trades_have_required_fields(self, capsys):
        """Each trade in JSON output has the expected fields."""
        main(["US30", "--days=10", "--seed=42", "--json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        if data["trades"]:
            trade = data["trades"][0]
            assert "time" in trade
            assert "direction" in trade
            assert trade["direction"] in ("LONG", "SHORT")
            assert "strategy" in trade
            assert "entry_price" in trade
            assert "exit_price" in trade
            assert "pnl" in trade
            assert "exit_reason" in trade


class TestHumanOutput:
    """Verify default human-readable output."""

    def test_human_output_contains_summary(self, capsys):
        """Default output includes the backtest summary."""
        main(["US30", "--days=5", "--seed=42"])
        captured = capsys.readouterr()
        assert "Backtest Results" in captured.out
        assert "Win rate" in captured.out

    def test_no_trades_suppresses_log(self, capsys):
        """--no-trades hides the trade table."""
        main(["US30", "--days=10", "--seed=42", "--no-trades"])
        captured = capsys.readouterr()
        assert "Backtest Results" in captured.out
        # Trade table header should not appear
        assert "Strategy" not in captured.out or "Entry" not in captured.out
