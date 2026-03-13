"""One-time OAuth2 token exchange for cTrader Open API.

Usage (inside Docker container):
    python -m broker.exchange_token --client-id YOUR_ID --client-secret YOUR_SECRET

Steps:
    1. Opens the authorization URL for you to visit in a browser
    2. You grant access and get redirected — copy the ?code= value
    3. Paste the code here and it exchanges it for access + refresh tokens
    4. Tokens are saved to docker/ctrader_tokens.json
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta

import requests
from dotenv import load_dotenv

from broker._token import TokenData, save_tokens

# cTrader OAuth2 endpoints
AUTH_URL = "https://openapi.ctrader.com/apps/auth"
TOKEN_URL = "https://openapi.ctrader.com/apps/token"
REDIRECT_URI = "https://openapi.ctrader.com/apps/auth-callback"

# Access tokens last ~30 days
TOKEN_LIFETIME_DAYS = 30


def get_auth_url(client_id: str) -> str:
    """Build the authorization URL the user must visit."""
    return (
        f"{AUTH_URL}"
        f"?client_id={client_id}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope=trading"
    )


def exchange_code(client_id: str, client_secret: str, auth_code: str) -> TokenData:
    """Exchange authorization code for access + refresh tokens."""
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    expires_in = data.get("expiresIn", TOKEN_LIFETIME_DAYS * 86400)
    expires_at = (datetime.now(UTC) + timedelta(seconds=expires_in)).isoformat()

    return TokenData(
        access_token=data["accessToken"],
        refresh_token=data["refreshToken"],
        expires_at=expires_at,
    )


def refresh_token(client_id: str, client_secret: str, refresh_tok: str) -> TokenData:
    """Refresh an expired access token."""
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_tok,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    expires_in = data.get("expiresIn", TOKEN_LIFETIME_DAYS * 86400)
    expires_at = (datetime.now(UTC) + timedelta(seconds=expires_in)).isoformat()

    return TokenData(
        access_token=data["accessToken"],
        refresh_token=data["refreshToken"],
        expires_at=expires_at,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Exchange cTrader OAuth2 authorization code for tokens",
    )
    parser.add_argument("--client-id", default=os.getenv("CTRADER_CLIENT_ID", ""))
    parser.add_argument("--client-secret", default=os.getenv("CTRADER_CLIENT_SECRET", ""))
    parser.add_argument(
        "--token-file",
        default="docker/ctrader_tokens.json",
        help="Path to save tokens (default: docker/ctrader_tokens.json)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh an existing token instead of exchanging a new code",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    load_dotenv("docker/.env")
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.client_id or not args.client_secret:
        print("ERROR: --client-id and --client-secret required (or set in .env)")
        sys.exit(1)

    if args.refresh:
        # Refresh mode: read existing token and refresh
        from broker._token import load_tokens

        tokens = load_tokens(args.token_file)
        if tokens is None:
            print(f"ERROR: No existing tokens found at {args.token_file}")
            sys.exit(1)

        print("Refreshing access token…")
        new_tokens = refresh_token(args.client_id, args.client_secret, tokens.refresh_token)
        save_tokens(new_tokens, args.token_file)
        print(f"New tokens saved to {args.token_file}")
        print(f"Access token expires: {new_tokens.expires_at}")
        return

    # Exchange mode: get new tokens from auth code
    url = get_auth_url(args.client_id)
    print("\n1. Open this URL in your browser:\n")
    print(f"   {url}\n")
    print("2. Log in and grant access.")
    print("3. You'll be redirected. Copy the 'code' parameter from the URL.\n")

    auth_code = input("Paste the authorization code here: ").strip()
    if not auth_code:
        print("ERROR: No code provided.")
        sys.exit(1)

    print("\nExchanging code for tokens…")
    tokens = exchange_code(args.client_id, args.client_secret, auth_code)
    save_tokens(tokens, args.token_file)
    print(f"\nTokens saved to {args.token_file}")
    print(f"Access token expires: {tokens.expires_at}")
    print("\nYou can now start the bot!")


if __name__ == "__main__":
    main()
