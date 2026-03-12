"""Entry point — run the scalping bot."""

import logging
import os

from dotenv import load_dotenv

from bot import ScalpingBot
from broker import CTraderBroker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


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
