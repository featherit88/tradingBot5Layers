"""Breaking news scanner — blocks trading during major market-moving events.

Uses Finnhub's free general news API to scan headlines for keywords that
indicate extreme market conditions where technical signals are unreliable.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import UTC, datetime, timedelta

import requests

log = logging.getLogger("filters.breaking_news")

_FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/news"

# ── Keywords that block trading ───────────────────────────────────
# Grouped by category for clarity. All matched case-insensitively.

_BLOCK_KEYWORDS: dict[str, list[str]] = {
    # Federal Reserve / monetary policy
    "fed": [
        "emergency rate",
        "emergency cut",
        "emergency hike",
        "surprise rate",
        "fed pause",
        "fed pivot",
        "rate decision",
        "rate surprise",
        "quantitative tightening",
        "quantitative easing",
    ],
    # Geopolitical / war / crisis
    "geopolitical": [
        "war breaks out",
        "declares war",
        "military strike",
        "nuclear",
        "missile launch",
        "invasion",
        "martial law",
        "coup",
        "terror attack",
        "terrorist attack",
    ],
    # Trade policy / tariffs
    "trade_policy": [
        "new tariff",
        "tariff hike",
        "tariff increase",
        "trade war",
        "trade ban",
        "sanctions imposed",
        "embargo",
        "retaliatory tariff",
    ],
    # Market crisis / systemic
    "market_crisis": [
        "flash crash",
        "circuit breaker",
        "trading halt",
        "market crash",
        "black swan",
        "liquidity crisis",
        "bank run",
        "bank failure",
        "bank collapse",
        "default",
        "debt ceiling",
        "government shutdown",
    ],
    # Major economic surprises
    "economic_shock": [
        "recession confirmed",
        "stagflation",
        "hyperinflation",
        "deflation",
        "economic collapse",
        "jobs shock",
        "unemployment surge",
        "gdp contraction",
    ],
}

# Build a single compiled regex for fast matching
_all_keywords = []
for group in _BLOCK_KEYWORDS.values():
    _all_keywords.extend(group)
_BLOCK_PATTERN = re.compile(
    "|".join(re.escape(kw) for kw in _all_keywords),
    re.IGNORECASE,
)

# Cache
_cached_alerts: list[dict] = []
_cache_timestamp: datetime | None = None
_CACHE_TTL_MINUTES = 5  # check news every 5 minutes


def scan_breaking_news(
    api_key: str | None = None,
    max_age_minutes: int = 30,
) -> list[dict]:
    """Scan Finnhub headlines for market-moving keywords.

    Returns list of matching articles with:
      - headline: str
      - matched_keyword: str
      - source: str
      - timestamp: datetime
      - category: str (which keyword group matched)

    Results are cached for _CACHE_TTL_MINUTES.
    """
    global _cached_alerts, _cache_timestamp

    now = datetime.now(UTC)

    # Return cached if fresh
    if _cache_timestamp and (now - _cache_timestamp).total_seconds() < _CACHE_TTL_MINUTES * 60:
        return _cached_alerts

    if api_key is None:
        api_key = os.environ.get("FINNHUB_API_KEY", "")

    if not api_key:
        log.warning("No FINNHUB_API_KEY set — breaking news scanner disabled")
        return []

    try:
        resp = requests.get(
            _FINNHUB_NEWS_URL,
            params={"category": "general", "token": api_key},
            timeout=10,
        )
        resp.raise_for_status()
        articles = resp.json()
    except (requests.RequestException, ValueError) as e:
        log.warning("Failed to fetch Finnhub news: %s", e)
        return _cached_alerts  # return stale cache on failure

    cutoff = now - timedelta(minutes=max_age_minutes)
    alerts: list[dict] = []

    for article in articles:
        ts = article.get("datetime", 0)
        article_time = datetime.fromtimestamp(ts, tz=UTC)

        if article_time < cutoff:
            continue

        headline = article.get("headline", "")
        summary = article.get("summary", "")
        text = f"{headline} {summary}"

        match = _BLOCK_PATTERN.search(text)
        if match:
            # Find which category it belongs to
            matched_kw = match.group().lower()
            category = "unknown"
            for cat, keywords in _BLOCK_KEYWORDS.items():
                if any(kw.lower() == matched_kw for kw in keywords):
                    category = cat
                    break

            alerts.append({
                "headline": headline,
                "matched_keyword": matched_kw,
                "source": article.get("source", ""),
                "timestamp": article_time,
                "category": category,
            })

    _cached_alerts = alerts
    _cache_timestamp = now

    if alerts:
        log.warning(
            "BREAKING NEWS ALERT: %d market-moving headlines detected!",
            len(alerts),
        )
        for a in alerts:
            log.warning(
                "  [%s] %s — matched: '%s' (%s)",
                a["source"], a["headline"][:80],
                a["matched_keyword"], a["category"],
            )

    return alerts


def is_market_safe() -> bool:
    """Return True if no breaking news alerts are active.

    This is the main function called by the bot to gate trading.
    """
    alerts = scan_breaking_news()
    return len(alerts) == 0
