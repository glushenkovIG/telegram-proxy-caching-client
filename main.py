import asyncio
import threading
import logging
from app import create_app
from telegram_client import TelegramCollector

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def run_flask():
    app = create_app()
    # Disable reloader when running in thread
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)

async def start_telegram_collector():
    collector = TelegramCollector()
    success = await collector.start()
    if success:
        # Keep the client running
        await collector.client.run_until_disconnected()
    else:
        logger.error("Failed to start Telegram collector")

if __name__ == "__main__":
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True  # Make thread daemon so it exits when main thread exits
    flask_thread.start()

    # Configure and run event loop
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(start_telegram_collector())
    except KeyboardInterrupt:
        pass
    finally:
        if 'loop' in locals():
            loop.close()