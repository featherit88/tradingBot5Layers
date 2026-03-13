"""Tests for config.logging — setup_logging() function."""

import json
import logging

from config import setup_logging


class TestSetupLogging:
    """Verify setup_logging() configures the root logger correctly."""

    def _reset_root_logger(self):
        """Remove all handlers from root logger between tests."""
        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)
            handler.close()

    def test_default_produces_human_readable(self):
        """Default setup uses human-readable format."""
        self._reset_root_logger()
        setup_logging()
        root = logging.getLogger()
        assert root.level == logging.INFO
        assert len(root.handlers) >= 1
        # The formatter should contain the level name pattern
        formatter = root.handlers[0].formatter
        assert formatter is not None
        assert "levelname" in formatter._fmt
        self._reset_root_logger()

    def test_json_format_produces_valid_json(self, capsys):
        """JSON mode outputs parseable JSON lines."""
        self._reset_root_logger()
        setup_logging(json_format=True)
        test_logger = logging.getLogger("test.json")
        test_logger.info("hello world")
        captured = capsys.readouterr()
        # Parse the JSON output
        line = captured.err.strip().split("\n")[-1]
        data = json.loads(line)
        assert data["message"] == "hello world"
        assert data["level"] == "INFO"
        assert "timestamp" in data
        assert data["logger"] == "test.json"
        self._reset_root_logger()

    def test_debug_level(self):
        """log_level='DEBUG' sets root logger to DEBUG."""
        self._reset_root_logger()
        setup_logging(log_level="DEBUG")
        root = logging.getLogger()
        assert root.level == logging.DEBUG
        self._reset_root_logger()

    def test_warning_level(self):
        """log_level='WARNING' sets root logger to WARNING."""
        self._reset_root_logger()
        setup_logging(log_level="WARNING")
        root = logging.getLogger()
        assert root.level == logging.WARNING
        self._reset_root_logger()

    def test_file_logging(self, tmp_path):
        """log_file writes log output to a file."""
        self._reset_root_logger()
        log_file = tmp_path / "bot.log"
        setup_logging(log_file=str(log_file))
        test_logger = logging.getLogger("test.file")
        test_logger.info("file test message")
        # Flush handlers
        for handler in logging.getLogger().handlers:
            handler.flush()
        content = log_file.read_text()
        assert "file test message" in content
        self._reset_root_logger()

    def test_json_file_logging(self, tmp_path):
        """JSON mode + file logging writes valid JSON to file."""
        self._reset_root_logger()
        log_file = tmp_path / "bot.json.log"
        setup_logging(json_format=True, log_file=str(log_file))
        test_logger = logging.getLogger("test.jsonfile")
        test_logger.info("json file test")
        for handler in logging.getLogger().handlers:
            handler.flush()
        content = log_file.read_text().strip()
        last_line = content.split("\n")[-1]
        data = json.loads(last_line)
        assert data["message"] == "json file test"
        self._reset_root_logger()

    def test_idempotent_call(self):
        """Calling setup_logging() twice doesn't double handlers."""
        self._reset_root_logger()
        setup_logging()
        count1 = len(logging.getLogger().handlers)
        setup_logging()
        count2 = len(logging.getLogger().handlers)
        assert count2 == count1
        self._reset_root_logger()
