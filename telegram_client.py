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
            print("Please watch for the phone number prompt below")
            print("="*50 + "\n")

            # This will automatically prompt for phone number if needed
            await self.client.start()

            if not await self.client.is_user_authorized():
                logger.error("Client not authorized. Please enter your phone number when prompted.")
                return False

            self.is_connected = True
            logger.info("Telegram collector started successfully")

            # Get channels from the target folder
            if not await self.get_channels_from_folder():
                logger.error("Failed to get channels from folder")
                return False

            # Start collecting historical messages
            for channel in self.target_channels:
                logger.info(f"Fetching history from {channel.title}")
                await self.fetch_history(channel, limit=100)

            # Set up event handler for new messages
            @self.client.on(events.NewMessage)
            async def handle_new_message(event):
                try:
                    chat = await event.get_chat()

                    # Only process messages from channels in our target folder
                    if chat not in self.target_channels:
                        return

                    sender = await event.get_sender()

                    if event.message.text:  # Only store text messages
                        message = TelegramMessage(
                            message_id=event.message.id,
                            channel_id=str(chat.id),
                            channel_title=chat.title if isinstance(chat, Channel) else None,
                            sender_id=str(sender.id) if sender else None,
                            sender_username=sender.username if sender else None,
                            content=event.message.text,
                        )

                        db.session.add(message)
                        db.session.commit()
                        logger.info(f"Stored new message from {message.channel_title}")

                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
                    db.session.rollback()

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