"""Tests for broker OAuth2 token management."""

import json
import os
from datetime import UTC, datetime, timedelta

from broker._token import (
    TokenData,
    is_token_expired,
    load_tokens,
    save_tokens,
)


class TestTokenData:
    def test_creation(self):
        td = TokenData(
            access_token="acc123",
            refresh_token="ref456",
            expires_at="2026-04-01T00:00:00+00:00",
        )
        assert td.access_token == "acc123"
        assert td.refresh_token == "ref456"
        assert td.expires_at == "2026-04-01T00:00:00+00:00"

    def test_to_dict(self):
        td = TokenData(
            access_token="acc",
            refresh_token="ref",
            expires_at="2026-04-01T00:00:00+00:00",
        )
        d = td.to_dict()
        assert d["access_token"] == "acc"
        assert d["refresh_token"] == "ref"
        assert d["expires_at"] == "2026-04-01T00:00:00+00:00"

    def test_from_dict(self):
        d = {
            "access_token": "a",
            "refresh_token": "r",
            "expires_at": "2026-05-01T00:00:00+00:00",
        }
        td = TokenData.from_dict(d)
        assert td.access_token == "a"
        assert td.refresh_token == "r"


class TestSaveAndLoadTokens:
    def test_save_creates_file(self, tmp_path):
        path = str(tmp_path / "tokens.json")
        td = TokenData(
            access_token="acc",
            refresh_token="ref",
            expires_at="2026-04-01T00:00:00+00:00",
        )
        save_tokens(td, path)
        assert os.path.exists(path)

        with open(path) as f:
            data = json.load(f)
        assert data["access_token"] == "acc"

    def test_load_reads_saved_file(self, tmp_path):
        path = str(tmp_path / "tokens.json")
        original = TokenData(
            access_token="my_token",
            refresh_token="my_refresh",
            expires_at="2026-06-01T12:00:00+00:00",
        )
        save_tokens(original, path)
        loaded = load_tokens(path)
        assert loaded is not None
        assert loaded.access_token == "my_token"
        assert loaded.refresh_token == "my_refresh"

    def test_load_returns_none_for_missing_file(self, tmp_path):
        path = str(tmp_path / "nonexistent.json")
        assert load_tokens(path) is None

    def test_load_returns_none_for_corrupt_file(self, tmp_path):
        path = str(tmp_path / "bad.json")
        with open(path, "w") as f:
            f.write("not json at all {{{")
        assert load_tokens(path) is None

    def test_load_returns_none_for_missing_keys(self, tmp_path):
        path = str(tmp_path / "partial.json")
        with open(path, "w") as f:
            json.dump({"access_token": "only_this"}, f)
        assert load_tokens(path) is None


class TestIsTokenExpired:
    def test_not_expired(self):
        future = (datetime.now(UTC) + timedelta(days=10)).isoformat()
        td = TokenData(access_token="a", refresh_token="r", expires_at=future)
        assert is_token_expired(td) is False

    def test_expired(self):
        past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        td = TokenData(access_token="a", refresh_token="r", expires_at=past)
        assert is_token_expired(td) is True

    def test_expires_within_buffer(self):
        # Expires in 30 seconds — within default 5-minute buffer
        soon = (datetime.now(UTC) + timedelta(seconds=30)).isoformat()
        td = TokenData(access_token="a", refresh_token="r", expires_at=soon)
        assert is_token_expired(td) is True

    def test_expires_outside_buffer(self):
        # Expires in 10 minutes — outside 5-minute buffer
        later = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
        td = TokenData(access_token="a", refresh_token="r", expires_at=later)
        assert is_token_expired(td) is False

    def test_custom_buffer(self):
        # Expires in 2 minutes, buffer = 3 minutes → expired
        soon = (datetime.now(UTC) + timedelta(minutes=2)).isoformat()
        td = TokenData(access_token="a", refresh_token="r", expires_at=soon)
        assert is_token_expired(td, buffer_minutes=3) is True

    def test_invalid_date_treated_as_expired(self):
        td = TokenData(access_token="a", refresh_token="r", expires_at="not-a-date")
        assert is_token_expired(td) is True
