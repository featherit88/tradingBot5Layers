"""Price and volume conversion for cTrader Open API.

All prices in the API are integers = actual_price * 100,000.
All volumes are in "cents" where 100,000 = 1 standard lot.
"""

from __future__ import annotations

PRICE_FACTOR = 100_000
VOLUME_FACTOR = 100_000


def price_from_api(api_price: int, digits: int | None = None) -> float:
    """Convert API integer price to float. Optionally round to `digits`."""
    result = api_price / PRICE_FACTOR
    if digits is not None:
        result = round(result, digits)
    return result


def price_to_api(price: float) -> int:
    """Convert float price to API integer."""
    return round(price * PRICE_FACTOR)


def volume_from_lots(api_volume: int) -> float:
    """Convert API volume (cents) to lots. 100,000 = 1 lot."""
    return api_volume / VOLUME_FACTOR


def volume_to_lots(lots: float) -> int:
    """Convert lots to API volume (cents). 1 lot = 100,000."""
    return round(lots * VOLUME_FACTOR)
