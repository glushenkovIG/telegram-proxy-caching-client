import asyncio
import logging
from telethon import TelegramClient, events
from telethon.tl.types import Channel, Folder
from app import db
from models import TelegramMessage
from config import Config

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TelegramCollector:
    def __init__(self):
        self.client = TelegramClient('ton_collector_session',
                                   Config.TELEGRAM_API_ID,
                                   Config.TELEGRAM_API_HASH,
                                   system_version="4.16.30-vxCUSTOM")  # Set a custom system version
        self.is_connected = False
        self.target_channels = set()

    async def get_channels_from_folder(self):
        """Get all channels from the specified folder."""
        try:
            dialogs = await self.client.get_dialogs()
            for dialog in dialogs:
                if dialog.folder and dialog.folder.title == Config.TARGET_FOLDER:
                    if isinstance(dialog.entity, Channel):
                        self.target_channels.add(dialog.entity)
                        logger.info(f"Found channel in target folder: {dialog.entity.title}")

            logger.info(f"Found {len(self.target_channels)} channels in {Config.TARGET_FOLDER} folder")
            return True
        except Exception as e:
            logger.error(f"Error getting channels from folder: {str(e)}")
            return False

    async def start(self):
        try:
            print("\n" + "="*50)
            print("Starting Telegram Authentication Process")
            print("Please enter your phone number in international format")
            print("Example: +1234567890")
            print("After entering your phone number, you'll receive a code")
            print("Please enter that code when prompted")
            print("="*50 + "\n")

            # Start without bot token first
            await self.client.connect()

            if not await self.client.is_user_authorized():
                # Clear guidance for phone number input
                print("\nPlease enter your phone number now:")
                await self.client.start()

            self.is_connected = True
            logger.info("Successfully connected to Telegram")

            # Get channels from the target folder
            if not await self.get_channels_from_folder():
                logger.error("Failed to get channels from folder")
                return False

            return True

        except Exception as e:
            logger.error(f"Error starting Telegram collector: {str(e)}")
            self.is_connected = False
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