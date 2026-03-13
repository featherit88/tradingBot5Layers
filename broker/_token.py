"""OAuth2 token persistence — load/save/check expiry."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

log = logging.getLogger(__name__)

DEFAULT_TOKEN_PATH = "docker/ctrader_tokens.json"
DEFAULT_BUFFER_MINUTES = 5


@dataclass
class TokenData:
    access_token: str
    refresh_token: str
    expires_at: str  # ISO-8601 datetime string

    def to_dict(self) -> dict:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
        }

    @staticmethod
    def from_dict(d: dict) -> TokenData:
        return TokenData(
            access_token=d["access_token"],
            refresh_token=d["refresh_token"],
            expires_at=d["expires_at"],
        )


def save_tokens(tokens: TokenData, path: str = DEFAULT_TOKEN_PATH) -> None:
    """Save tokens to a JSON file."""
    with open(path, "w") as f:
        json.dump(tokens.to_dict(), f, indent=2)
    log.info("Tokens saved to %s", path)


def load_tokens(path: str = DEFAULT_TOKEN_PATH) -> TokenData | None:
    """Load tokens from a JSON file. Returns None if missing or corrupt."""
    try:
        with open(path) as f:
            data = json.load(f)
        return TokenData.from_dict(data)
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None


def is_token_expired(tokens: TokenData, buffer_minutes: int = DEFAULT_BUFFER_MINUTES) -> bool:
    """Check if access token is expired or will expire within buffer."""
    try:
        expires_at = datetime.fromisoformat(tokens.expires_at)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return datetime.now(UTC) >= expires_at - timedelta(minutes=buffer_minutes)
    except (ValueError, TypeError):
        log.warning("Invalid expires_at value: %s — treating as expired", tokens.expires_at)
        return True
