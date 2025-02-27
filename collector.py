import os
import logging
from telethon import TelegramClient, events
from tqdm import tqdm
from config import Config
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# TON Developer channels with their metadata
TON_CHANNELS = {
    'TON Dev News': {'id': None, 'username': None},
    'Hackers League Hackathon': {'id': None, 'username': None},
    'TON Society Chat': {'id': None, 'username': None}, 
    'TON Tact Language Chat': {'id': None, 'username': None},
    'Telegram Developers Community': {'id': None, 'username': None},
    'TON Data Hub Chat': {'id': None, 'username': None},
    'TON Data Hub': {'id': None, 'username': None},
    'TON Community': {'id': None, 'username': None},
    'TON Dev Chat (中文)': {'id': None, 'username': None},
    'TON Research': {'id': None, 'username': None},
    'TON Jobs': {'id': None, 'username': None},
    'TON Contests': {'id': None, 'username': None},
    'TON Status': {'id': None, 'username': None},
    'BotNews': {'id': None, 'username': None},
    'Testnet TON Status': {'id': None, 'username': None},
    'The Open Network': {'id': None, 'username': None}
}

# Initialize client with credentials from config
client = TelegramClient("ton_collector_session", 
                      Config.TELEGRAM_API_ID,
                      Config.TELEGRAM_API_HASH,
                      base_logger="telethon")

@client.on(events.NewMessage)
async def handle_message(event):
    """Handle new messages"""
    try:
        chat = await event.get_chat()
        chat_title = getattr(chat, 'title', None)

        # Only show messages from exact channel matches
        if chat_title and chat_title.strip() in TON_CHANNELS:
            sender = await event.get_sender()
            chat_username = getattr(chat, 'username', None)

            # Update channel metadata if not set
            if TON_CHANNELS[chat_title.strip()]['id'] is None:
                TON_CHANNELS[chat_title.strip()]['id'] = chat.id
                TON_CHANNELS[chat_title.strip()]['username'] = chat_username
                logger.info(f"Updated metadata for channel: {chat_title} (ID: {chat.id})")

            # Format: timestamp | channel_id | channel_title | sender_id | sender_name | message
            formatted_message = event.message.text.replace('|', '//')
            print(f"{event.message.date} | {chat.id} | {chat_title} | {sender.id if sender else 'N/A'} | {sender.username or sender.first_name if sender else 'Unknown'} | {formatted_message}")

    except Exception as e:
        logger.error(f"Error in message handler: {str(e)}")

async def main():
    print("Connecting to Telegram...")
    try:
        # Try to connect with stored session first
        await client.start()

        # If no session, try to connect with phone
        if not await client.is_user_authorized():
            await client.start(phone=Config.TELEGRAM_PHONE)

        # Get all dialogs to populate channel metadata
        print("\nGetting channel information...")
        async for dialog in client.iter_dialogs():
            chat_title = getattr(dialog.entity, 'title', None)
            if chat_title and chat_title.strip() in TON_CHANNELS:
                chat_username = getattr(dialog.entity, 'username', None)
                TON_CHANNELS[chat_title.strip()]['id'] = dialog.entity.id
                TON_CHANNELS[chat_title.strip()]['username'] = chat_username
                logger.info(f"Found channel in dialogs: {chat_title} (ID: {dialog.entity.id})")

        print("\nConnected! Monitoring these channels:")
        print("\nChannel Name | Channel ID | Username")
        print("-" * 50)
        for channel in sorted(TON_CHANNELS.keys()):
            metadata = TON_CHANNELS[channel]
            print(f"{channel} | {metadata['id'] or 'Not seen yet'} | {metadata['username'] or 'Not seen yet'}")

        print("\nMessages will be output in format:")
        print("timestamp | channel_id | channel_name | sender_id | sender_name | message")
        print("\nPress Ctrl+C to stop")
        await client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())