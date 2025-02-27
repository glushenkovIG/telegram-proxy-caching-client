import os
import logging
from telethon import TelegramClient, events
from tqdm import tqdm
from config import Config
from app import app, db, TelegramMessage

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize client
client = TelegramClient('ton_collector_session', 
                       Config.TELEGRAM_API_ID,
                       Config.TELEGRAM_API_HASH)

# Track messages
pbar = tqdm(desc="Messages", unit=" msgs")

@client.on(events.NewMessage)
async def handle_message(event):
    """Handle and store new messages"""
    try:
        chat = await event.get_chat()
        chat_title = getattr(chat, 'title', None)

        # Store message in database
        with app.app_context():
            message = TelegramMessage(
                message_id=event.message.id,
                channel_id=str(chat.id),
                channel_title=chat_title,
                content=event.message.text,
                timestamp=event.message.date,
                is_ton_dev=chat_title in Config.TON_CHANNELS
            )
            db.session.add(message)
            db.session.commit()

        # Show TON dev messages in console
        if chat_title in Config.TON_CHANNELS:
            print(f"\nTON Message from {chat_title}:")
            print(f"Content: {event.message.text}")
        else:
            pbar.update(1)

    except Exception as e:
        logger.error(f"Error: {str(e)}")

async def main():
    """Main collector function"""
    try:
        print("Starting collector...")
        await client.start()
        me = await client.get_me()
        print(f"Connected as: {me.username}")
        print("\nMonitoring channels...")
        await client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Error: {str(e)}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())