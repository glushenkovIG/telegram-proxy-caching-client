import os
import logging
from telethon import TelegramClient, events
from config import Config
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize database
db = SQLAlchemy()

class TelegramMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, nullable=False)
    channel_id = db.Column(db.String(100), nullable=False)
    channel_title = db.Column(db.String(200))
    sender_id = db.Column(db.String(100))
    sender_username = db.Column(db.String(100))
    content = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Create Flask app just for database
from flask import Flask
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

async def main():
    try:
        # Create database tables
        with app.app_context():
            db.create_all()
            logger.info("Database tables created")

        # Create the client
        client = TelegramClient('ton_collector_session',
                              Config.TELEGRAM_API_ID,
                              Config.TELEGRAM_API_HASH)

        print("\n" + "="*50)
        print("CONNECTING TO TELEGRAM")
        print("="*50)

        await client.connect()

        if not await client.is_user_authorized():
            try:
                print("\n" + "="*50)
                print("TELEGRAM AUTHENTICATION REQUIRED")
                print("="*50)

                await client.send_code_request(Config.TELEGRAM_PHONE)
                print(f"\n>>> A verification code has been sent to {Config.TELEGRAM_PHONE}")
                code = input(">>> Enter the verification code here: ")

                try:
                    await client.sign_in(Config.TELEGRAM_PHONE, code)
                except Exception as e:
                    if "2FA" in str(e) or "password" in str(e).lower():
                        print("\n" + "="*50)
                        print("TWO-FACTOR AUTHENTICATION REQUIRED")
                        print("="*50)
                        password = input(">>> Please enter your 2FA password: ")
                        await client.sign_in(password=password)
                    else:
                        raise e

            except Exception as auth_error:
                logger.error(f"Authentication error: {auth_error}")
                return

        # Message handler for ALL messages
        @client.on(events.NewMessage)
        async def message_handler(event):
            try:
                # Get message details
                sender = await event.get_sender()
                chat = await event.get_chat()

                # Create database record
                with app.app_context():
                    message = TelegramMessage(
                        message_id=event.message.id,
                        channel_id=str(event.chat_id),
                        channel_title=chat.title if hasattr(chat, 'title') else None,
                        sender_id=str(sender.id) if sender else None,
                        sender_username=sender.username if sender else None,
                        content=event.message.text,
                        timestamp=event.message.date
                    )
                    db.session.add(message)
                    db.session.commit()
                    logger.info(f"Saved message {message.message_id} to database")

                # Print to console
                print("\nNew message received and saved to database:")
                if hasattr(chat, 'title'):
                    print(f"Channel/Group: {chat.title}")
                else:
                    print(f"From: {sender.username or sender.first_name}")
                print(f"Content: {event.message.text}")
                print(f"Time: {event.message.date}")
                print("-" * 50)

            except Exception as e:
                logger.error(f"Error handling message: {e}")
                if 'db' in locals():
                    db.session.rollback()

        print("\n" + "="*50)
        print("TELEGRAM COLLECTOR RUNNING")
        print("Monitoring ALL messages (saving to database)")
        print("="*50 + "\n")

        await client.run_until_disconnected()

    except Exception as e:
        logger.error(f"Error in main: {str(e)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())