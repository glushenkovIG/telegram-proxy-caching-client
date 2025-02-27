import os
import logging
import time
import random
from telethon import TelegramClient, events
from tqdm import tqdm
from config import Config

# Set up basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add a small random delay before initializing to avoid simultaneous access
time.sleep(random.uniform(1, 3))

# Initialize client with credentials from config
# Use a unique session name if running multiple instances
session_suffix = os.environ.get('SESSION_SUFFIX', '')
session_name = f'ton_collector_session{session_suffix}'

client = TelegramClient(session_name, 
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

        # Only show messages from exact channel matches
        if chat_title and chat_title.strip() in TON_CHANNELS:
            sender = await event.get_sender()
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
        await client.start()
        me = await client.get_me()
        print(f"\nConnected as: {me.username}")
        print(f"Using session: {session_name}")
        print("\nMonitoring these channels:")
        for channel in sorted(TON_CHANNELS):
            print(f"- {channel}")
        print("\nWaiting for messages...")
        
        # Add periodic state saving to avoid database locks
        while await client.is_connected():
            await asyncio.sleep(60)  # Save state every minute
            try:
                client._save_states_and_entities()
                logger.info("Saved client state successfully")
            except Exception as e:
                logger.warning(f"Error saving state: {e}")
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        # Ensure proper disconnection
        await client.disconnect()
        logger.info("Client disconnected")

if __name__ == "__main__":
    import asyncio
    try:
        # Use a different event loop policy for Windows if needed
        if os.name == 'nt':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        # Run with proper exception handling
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
    finally:
        logger.info("Exiting collector")