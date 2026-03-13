"""Main orchestration loop that ties all modules together."""

from bot.core import ScalpingBot
from bot.db import TradeLogger

__all__ = ["ScalpingBot", "TradeLogger"]
