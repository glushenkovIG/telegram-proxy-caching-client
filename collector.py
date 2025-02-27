import os
import logging
from telethon import TelegramClient, events
import sqlite3
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Telegram API credentials from config
API_ID = os.environ.get('TELEGRAM_API_ID')
API_HASH = os.environ.get('TELEGRAM_API_HASH')
SESSION_NAME = "ton_collector_session"

# Initialize the Telegram client
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# Connect to SQLite database
conn = sqlite3.connect("telegram_messages.db")
cursor = conn.cursor()

# Create table to store messages
cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER,
        chat_id INTEGER,
        message_text TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()

@client.on(events.NewMessage)
async def handle_message(event):
    """Handles new incoming messages and saves them to the database."""
    try:
        sender = await event.get_sender()
        sender_id = sender.id if sender else None
        chat_id = event.chat_id
        message_text = event.raw_text
        timestamp = event.date

        cursor.execute('''
            INSERT INTO messages (sender_id, chat_id, message_text, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (sender_id, chat_id, message_text, timestamp))
        conn.commit()
        
        print(f"[NEW MESSAGE] {chat_id} | {sender_id}: {message_text}")
        logger.info(f"Saved message from chat {chat_id}")

    except Exception as e:
        logger.error(f"Error handling message: {e}")
        if 'conn' in locals():
            conn.rollback()

async def main():
    """Main function to run the client"""
    try:
        print("Connecting to Telegram...")
        await client.connect()

        if not await client.is_user_authorized():
            print("\nTelegram authentication required")
            await client.send_code_request(os.environ.get('TELEGRAM_PHONE'))
            code = input("Enter verification code: ")
            try:
                await client.sign_in(os.environ.get('TELEGRAM_PHONE'), code)
            except Exception as e:
                if "2FA" in str(e):
                    password = input("Enter 2FA password: ")
                    await client.sign_in(password=password)
                else:
                    raise e

        print("\nConnected! Listening for incoming messages...")
        await client.run_until_disconnected()

    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
