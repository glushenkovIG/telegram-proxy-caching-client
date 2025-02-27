import os
import logging
import random
from telethon import TelegramClient, events
from tqdm import tqdm
from config import Config
import asyncio
from app import app, db
from models import TelegramMessage

# Set up basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize client
client = TelegramClient('ton_collector_session', 
                       Config.TELEGRAM_API_ID,
                       Config.TELEGRAM_API_HASH,
                       connection_retries=5)

# Track other messages
other_messages = 0
pbar = tqdm(desc="Other messages", unit=" msgs")

# Exact list of TON channels from screenshot
TON_CHANNELS = set([
    'TON Dev News',
    'Hackers League Hackathon', 
    'TON Society Chat',
    'TON Tact Language Chat',
    'Telegram Developers Community',
    'TON Data Hub Chat',
    'TON Data Hub',
    'TON Community',
    'TON Dev Chat (中文)',
    'TON Research',
    'TON Jobs',
    'TON Contests',
    'TON Status',
    'BotNews',
    'Testnet TON Status',
    'The Open Network'
])

@client.on(events.NewMessage)
async def handle_message(event):
    """Handle new messages"""
    try:
        global other_messages
        chat = await event.get_chat()
        chat_title = getattr(chat, 'title', None)
        chat_username = getattr(chat, 'username', None)
        chat_link = f"https://t.me/{chat_username}" if chat_username else "Private Channel"

        print(f"\nReceived message from chat: {chat_title}")  # Debug line

        # Save all messages to database
        sender = await event.get_sender()
        with app.app_context():
            message = TelegramMessage(
                message_id=event.message.id,
                channel_id=str(chat.id),
                channel_title=chat_title,
                channel_username=chat_username,
                sender_id=str(sender.id) if sender else None,
                sender_username=sender.username or sender.first_name if sender else 'Unknown',
                content=event.message.text,
                timestamp=event.message.date,
                is_ton_dev=bool(chat_title and chat_title.strip() in TON_CHANNELS)
            )
            db.session.add(message)
            db.session.commit()

        # Only show messages from exact channel matches in console
        if chat_title and chat_title.strip() in TON_CHANNELS:
            print("\n==================================================")
            print(f"Channel: {chat_title}")
            print(f"Channel ID: {chat.id}")
            print(f"Channel Link: {chat_link}")
            print(f"From: {sender.username or sender.first_name if sender else 'Unknown'}")
            print("--------------------------------------------------")
            print(f"Message: {event.message.text}")
            print(f"Time: {event.message.date}")
            print("==================================================")
        else:
            # Count other messages
            other_messages += 1
            pbar.update(1)

    except Exception as e:
        print(f"Error handling message: {str(e)}")

async def main():
    try:
        print("Connecting to Telegram...")
        await client.connect()
        me = await client.get_me()
        print(f"\nConnected as: {me.username}")
        print("\nMonitoring these channels:")
        for channel in sorted(TON_CHANNELS):
            print(f"- {channel}")
        print("\nWaiting for messages...")

        # Keep running until interrupted
        await client.disconnected
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        # Ensure proper disconnection
        await client.disconnect()
        logger.info("Client disconnected")

if __name__ == "__main__":
    try:
        # Run with proper exception handling  
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
    finally:
        logger.info("Exiting collector")