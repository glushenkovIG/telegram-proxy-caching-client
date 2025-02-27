import os
import logging
from telethon import TelegramClient, events
from tqdm import tqdm
from config import Config

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize client with credentials from config
client = TelegramClient('ton_collector_session', 
                       Config.TELEGRAM_API_ID,
                       Config.TELEGRAM_API_HASH)

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

        # Only show messages from exact channel matches
        if chat_title and chat_title.strip() in TON_CHANNELS:
            sender = await event.get_sender()
            chat_username = getattr(chat, 'username', None)
            chat_link = f"https://t.me/{chat_username}" if chat_username else "Private Channel"

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
        logger.error(f"Error in main: {str(e)}")

async def main():
    print("Connecting to Telegram...")
    try:
        # Try to connect with stored session first
        await client.start()

        # If no session, try to connect with phone
        if not await client.is_user_authorized():
            await client.start(phone=Config.TELEGRAM_PHONE)

        print("\nConnected! Monitoring these channels:")
        for channel in sorted(TON_CHANNELS):
            print(f"- {channel}")
        print("\nAll other messages will be counted in the progress bar")
        print("Press Ctrl+C to stop")
        await client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())