import asyncio
import logging
from telegram_client import TelegramCollector

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main():
    try:
        # Create and start Telegram collector
        collector = TelegramCollector()
        await collector.start()

        # Keep the client running
        await collector.client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")

if __name__ == "__main__":
    # Run the Telegram client
    asyncio.run(main())