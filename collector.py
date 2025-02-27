import logging
from telethon import TelegramClient, events
from tqdm import tqdm
from config import Config
from app import app, db, TelegramMessage

# Set up logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize client using existing session
client = TelegramClient('ton_collector_session', 
                       Config.TELEGRAM_API_ID,
                       Config.TELEGRAM_API_HASH)

@client.on(events.NewMessage)
async def handle_message(event):
    """Handle and store new messages"""
    try:
        chat = await event.get_chat()
        chat_title = getattr(chat, 'title', None)

        if not event.message.text:
            return

        # Store in database
        with app.app_context():
            message = TelegramMessage(
                message_id=event.message.id,
                channel_id=str(chat.id),
                channel_title=chat_title,
                content=event.message.text,
                timestamp=event.message.date,
                is_ton_dev=chat_title in Config.TON_CHANNELS if chat_title else False
            )
            db.session.add(message)
            db.session.commit()
            logger.info(f"Stored message from {chat_title}")

    except Exception as e:
        logger.error(f"Error handling message: {str(e)}")

async def main():
    """Main collector function"""
    try:
        print("Starting collector...")
        await client.start()
        me = await client.get_me()
        print(f"Connected as: {me.username}")
        print("Listening for messages...")
        await client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Error: {str(e)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())