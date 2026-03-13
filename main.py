"""Entry point — run the scalping bot."""

import os

from dotenv import load_dotenv

from bot import ScalpingBot
from broker import CTraderBroker
from config import setup_logging

setup_logging()


def main() -> None:
    load_dotenv("docker/.env")

    broker = CTraderBroker(
        client_id=os.getenv("CTRADER_CLIENT_ID", ""),
        client_secret=os.getenv("CTRADER_CLIENT_SECRET", ""),
        account_id=os.getenv("CTRADER_ACCOUNT_ID", ""),
    )

    bot = ScalpingBot(broker)
    bot.run()


if __name__ == "__main__":
    main()
