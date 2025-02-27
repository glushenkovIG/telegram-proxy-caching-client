import asyncio
import logging
import os
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from app import db
from models import TelegramMessage
from config import Config

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TelegramCollector:
    def __init__(self):
        # Create a new Telegram client
        self.client = TelegramClient(
            'ton_collector_session',
            Config.TELEGRAM_API_ID,
            Config.TELEGRAM_API_HASH,
            system_version="4.16.30-vxCUSTOM"
        )
        self.is_connected = False

    async def start(self):
        try:
            logger.info("Starting Telegram Authentication Process")

            # Start the client
            await self.client.connect()

            if not await self.client.is_user_authorized():
                if not Config.TELEGRAM_PHONE:
                    logger.error("TELEGRAM_PHONE environment variable is not set")
                    print("Please set the TELEGRAM_PHONE environment variable in Replit Secrets")
                    return False

                logger.info(f"Using phone number from config: {Config.TELEGRAM_PHONE}")
                # Request code to be sent to the phone
                await self.client.send_code_request(Config.TELEGRAM_PHONE)

                # Note: For Replit deployment, we need a way to get the verification code
                # Let's provide a URL where the user can enter the code
                print("\n" + "="*50)
                print("A verification code has been sent to your phone.")
                print("Please set the TELEGRAM_CODE environment variable in Replit Secrets")
                print("with the code you received, then restart this Repl.")
                print("="*50 + "\n")

                # Check if code is in environment variables
                if 'TELEGRAM_CODE' in os.environ and os.environ.get('TELEGRAM_CODE'):
                    code = os.environ.get('TELEGRAM_CODE')
                    try:
                        await self.client.sign_in(Config.TELEGRAM_PHONE, code)
                    except SessionPasswordNeededError:
                        # 2FA is enabled
                        if 'TELEGRAM_PASSWORD' in os.environ and os.environ.get('TELEGRAM_PASSWORD'):
                            await self.client.sign_in(password=os.environ.get('TELEGRAM_PASSWORD'))
                        else:
                            print("Two-factor authentication is enabled.")
                            print("Please set the TELEGRAM_PASSWORD environment variable in Replit Secrets")
                            return False
                else:
                    print("Waiting for TELEGRAM_CODE to be set...")
                    return False

            self.is_connected = True
            logger.info("Successfully connected to Telegram")
            return True
        except Exception as e:
            logger.error(f"Error connecting to Telegram: {str(e)}")
            return False

    async def fetch_history(self, channel, limit=100):
        """Fetch historical messages from a channel."""
        try:
            logger.info(f"Fetching history from {channel.title}")

            async for message in self.client.iter_messages(channel, limit=limit):
                try:
                    if message.text:  # Only store messages with text content
                        sender = await message.get_sender()
                        db_message = TelegramMessage(
                            message_id=message.id,
                            channel_id=str(channel.id),
                            channel_title=channel.title if isinstance(channel, Channel) else None,
                            sender_id=str(sender.id) if sender else None,
                            sender_username=sender.username if sender else None,
                            content=message.text,
                            timestamp=message.date
                        )
                        db.session.add(db_message)

                except Exception as e:
                    logger.error(f"Error processing historical message: {str(e)}")
                    continue

            db.session.commit()
            logger.info(f"Successfully fetched history from {channel.title}")

        except Exception as e:
            logger.error(f"Error fetching history from {channel.title}: {str(e)}")
            db.session.rollback()

    def is_running(self):
        return self.is_connected