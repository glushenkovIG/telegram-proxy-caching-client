import os
import logging
from telethon import TelegramClient, events
from config import Config
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize database
DATABASE_URL = os.environ.get("DATABASE_URL")
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)

# Define message model
class Message(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True)
    sender_id = Column(String)
    chat_id = Column(String)
    message_text = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(engine)

# Initialize Telegram client
client = TelegramClient('ton_collector_session',
                      Config.TELEGRAM_API_ID,
                      Config.TELEGRAM_API_HASH)

@client.on(events.NewMessage)
async def handle_message(event):
    """Handles new incoming messages and saves them to the database."""
    try:
        sender = await event.get_sender()
        sender_id = str(sender.id) if sender else None
        chat_id = str(event.chat_id)
        message_text = event.raw_text

        # Save to database
        session = Session()
        message = Message(
            sender_id=sender_id,
            chat_id=chat_id,
            message_text=message_text
        )
        session.add(message)
        session.commit()

        print(f"[NEW MESSAGE] {chat_id} | {sender_id}: {message_text}")

    except Exception as e:
        logger.error(f"Error handling message: {e}")
        if 'session' in locals():
            session.rollback()
    finally:
        if 'session' in locals():
            session.close()

async def collect_history():
    """Collect historical messages from TON channels"""
    try:
        print("\nFetching TON development channels...")
        dialogs = await client.get_dialogs()
        ton_channels = [d for d in dialogs if d.name and any(channel in d.name for channel in Config.TON_CHANNELS)]

        total_messages = 0
        session = Session()

        for channel in ton_channels:
            print(f"\nCollecting messages from: {channel.name}")
            messages = await client.get_messages(channel, limit=None)  # None means all messages

            for msg in messages:
                if not msg.raw_text:  # Skip non-text messages
                    continue

                try:
                    message = Message(
                        sender_id=str(msg.sender_id) if msg.sender_id else None,
                        chat_id=str(channel.id),
                        message_text=msg.raw_text,
                        timestamp=msg.date
                    )
                    session.add(message)
                    total_messages += 1

                    if total_messages % 100 == 0:  # Commit every 100 messages
                        session.commit()
                        print(f"Saved {total_messages} messages so far...")

                except Exception as e:
                    logger.error(f"Error saving message: {e}")
                    session.rollback()

            session.commit()  # Final commit for this channel
            print(f"Finished collecting from {channel.name}")

        print(f"\nTotal historical messages collected: {total_messages}")

    except Exception as e:
        logger.error(f"Error collecting history: {e}")
        if 'session' in locals():
            session.rollback()
    finally:
        if 'session' in locals():
            session.close()

async def main():
    """Main function to run the client"""
    try:
        print("Connecting to Telegram...")
        await client.connect()

        if not await client.is_user_authorized():
            logger.info("Authentication required")
            await client.send_code_request(Config.TELEGRAM_PHONE)
            code = input("Enter the verification code: ")
            try:
                await client.sign_in(Config.TELEGRAM_PHONE, code)
            except Exception as e:
                if "2FA" in str(e):
                    password = input("Enter 2FA password: ")
                    await client.sign_in(password=password)
                else:
                    raise e

        print("Connected successfully!")

        # First collect historical messages
        await collect_history()

        # Then start listening for new messages
        print("\nNow listening for new messages...")
        await client.run_until_disconnected()

    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())