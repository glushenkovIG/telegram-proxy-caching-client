import asyncio
from app import app
from telegram_client import TelegramCollector

async def start_telegram_collector():
    collector = TelegramCollector()
    await collector.start()
    # Keep the client running
    await collector.client.run_until_disconnected()

if __name__ == "__main__":
    # Start the Flask app
    app.run(host="0.0.0.0", port=5000, debug=True)

    # Start the Telegram collector in the background
    loop = asyncio.get_event_loop()
    loop.create_task(start_telegram_collector())
    loop.run_forever()