import os
import logging
from telethon import TelegramClient, events
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import declarative_base
from config import Config

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask and database
class Base(declarative_base()):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.environ.get("SESSION_SECRET")

# Initialize SQLAlchemy
db.init_app(app)

# Initialize Telegram client
client = TelegramClient('ton_collector_session',
                      Config.TELEGRAM_API_ID,
                      Config.TELEGRAM_API_HASH)

@client.on(events.NewMessage)
async def handle_message(event):
    """Handle new messages from Telegram"""
    try:
        chat = await event.get_chat()
        sender = await event.get_sender()

        # Only process messages from TON channels
        if not hasattr(chat, 'title') or not any(channel in chat.title for channel in Config.TON_CHANNELS):
            return

        # Save to database
        with app.app_context():
            from models import TelegramMessage

            # Check for duplicate
            existing = TelegramMessage.query.filter_by(
                channel_id=str(event.chat_id),
                message_id=event.message.id
            ).first()

            if not existing and event.message.text:
                message = TelegramMessage(
                    message_id=event.message.id,
                    channel_id=str(event.chat_id),
                    channel_title=chat.title,
                    sender_id=str(sender.id) if sender else None,
                    sender_username=sender.username if sender else None,
                    content=event.message.text,
                    timestamp=event.message.date
                )
                db.session.add(message)
                db.session.commit()

                # Log the message
                print(f"[NEW MESSAGE] {chat.title} | {sender.username}: {event.message.text}")
                logger.info(f"Saved message from {chat.title}")

    except Exception as e:
        logger.error(f"Error handling message: {e}")
        if 'db' in locals():
            db.session.rollback()

async def main():
    """Main function to run the Telegram client"""
    try:
        # Create database tables
        with app.app_context():
            import models
            db.create_all()
            logger.info("Database tables created")

        await client.connect()

        if not await client.is_user_authorized():
            print("\nTelegram authentication required")
            await client.send_code_request(Config.TELEGRAM_PHONE)
            code = input("Enter verification code: ")
            try:
                await client.sign_in(Config.TELEGRAM_PHONE, code)
            except Exception as e:
                if "2FA" in str(e):
                    password = input("Enter 2FA password: ")
                    await client.sign_in(password=password)
                else:
                    raise e

        print("\nStarting message collection...")
        await client.run_until_disconnected()

    except Exception as e:
        logger.error(f"Error in Telegram client: {e}")
        raise

if __name__ == "__main__":
    # Run the client
    import asyncio
    asyncio.run(main())