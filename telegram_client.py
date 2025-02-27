import logging
from telethon import TelegramClient, events
from telethon.tl.types import Channel
from app import db
from models import TelegramMessage
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TelegramCollector:
    def __init__(self):
        self.client = TelegramClient('ton_collector_session',
                                   Config.TELEGRAM_API_ID,
                                   Config.TELEGRAM_API_HASH)
        
    async def start(self):
        await self.client.start(bot_token=Config.TELEGRAM_BOT_TOKEN)
        
        @self.client.on(events.NewMessage(chats=Config.TARGET_CHANNELS))
        async def handle_new_message(event):
            try:
                chat = await event.get_chat()
                sender = await event.get_sender()
                
                message = TelegramMessage(
                    message_id=event.message.id,
                    channel_id=str(chat.id),
                    channel_title=chat.title if isinstance(chat, Channel) else None,
                    sender_id=str(sender.id),
                    sender_username=sender.username,
                    content=event.message.text,
                )
                
                db.session.add(message)
                db.session.commit()
                logger.info(f"Stored message from {message.channel_title}")
                
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                db.session.rollback()
    
    async def fetch_history(self, channel, limit=100):
        try:
            async for message in self.client.iter_messages(channel, limit=limit):
                chat = await self.client.get_entity(channel)
                sender = await message.get_sender()
                
                db_message = TelegramMessage(
                    message_id=message.id,
                    channel_id=str(chat.id),
                    channel_title=chat.title if isinstance(chat, Channel) else None,
                    sender_id=str(sender.id) if sender else None,
                    sender_username=sender.username if sender else None,
                    content=message.text,
                    timestamp=message.date
                )
                
                db.session.add(db_message)
            
            db.session.commit()
            logger.info(f"Fetched history from {channel}")
            
        except Exception as e:
            logger.error(f"Error fetching history: {str(e)}")
            db.session.rollback()
