"""Economic calendar news feed — blocks trading near high-impact events.

Uses Forex Factory's free JSON calendar API. Fetches once per session,
caches results, and returns upcoming event times for the news filter.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import requests

log = logging.getLogger("filters.news")

# Forex Factory free calendar endpoints
_FF_THIS_WEEK = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
_FF_NEXT_WEEK = "https://nfs.faireconomy.media/ff_calendar_nextweek.json"

# Only block on these countries (relevant to US30/SPX)
_RELEVANT_COUNTRIES = {"USD"}

# Only block on these impact levels
_BLOCK_IMPACTS = {"High", "Medium"}

# Cache
_cached_events: list[datetime] = []
_cache_timestamp: datetime | None = None
_CACHE_TTL_HOURS = 4  # refresh every 4 hours


def fetch_news_events(
    countries: set[str] = _RELEVANT_COUNTRIES,
    impacts: set[str] = _BLOCK_IMPACTS,
) -> list[datetime]:
    """Fetch economic calendar and return list of event datetimes (UTC).

    Only returns events matching the specified countries and impact levels.
    Results are cached for _CACHE_TTL_HOURS to avoid hammering the API.
    """
    global _cached_events, _cache_timestamp

    now = datetime.now(UTC)

    # Return cached if still fresh
    if _cache_timestamp and (now - _cache_timestamp).total_seconds() < _CACHE_TTL_HOURS * 3600:
        return _cached_events

    events: list[datetime] = []

    for url in [_FF_THIS_WEEK, _FF_NEXT_WEEK]:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as e:
            log.warning("Failed to fetch calendar from %s: %s", url, e)
            continue

        for item in data:
            country = item.get("country", "")
            impact = item.get("impact", "")

            if country not in countries:
                continue
            if impact not in impacts:
                continue

            date_str = item.get("date", "")
            if not date_str:
                continue

            try:
                # FF format: "2026-03-12T08:30:00-04:00"
                event_time = datetime.fromisoformat(date_str).astimezone(UTC)
                events.append(event_time)
            except (ValueError, TypeError):
                log.debug("Could not parse date: %s", date_str)
                continue

    # Sort and deduplicate
    events = sorted(set(events))

    _cached_events = events
    _cache_timestamp = now

    log.info(
        "Fetched %d high/medium-impact USD events for this/next week",
        len(events),
    )

    return events


def get_upcoming_events(
    now: datetime | None = None,
    lookahead_hours: int = 24,
) -> list[datetime]:
    """Return event times within the next N hours.

    This is what the bot calls each tick to get relevant news times
    for the check_news() filter.
    """
    if now is None:
        now = datetime.now(UTC)

    all_events = fetch_news_events()
    cutoff = now + timedelta(hours=lookahead_hours)

    return [e for e in all_events if now - timedelta(hours=1) <= e <= cutoff]
