import logging
from telethon import TelegramClient, events, tl
from config import Config
from app import app, db, TelegramMessage

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize client with existing session
client = TelegramClient('ton_collector_session', 
                       Config.TELEGRAM_API_ID,
                       Config.TELEGRAM_API_HASH)

@client.on(events.NewMessage)
async def handle_message(event):
    """Handle incoming messages"""
    try:
        # Get message details
        chat = await event.get_chat()
        chat_title = getattr(chat, 'title', None)

        if not event.message.text:
            return

        # Get dialog info to check folder
        dialog = await client.get_dialogs()
        is_ton_dev = False

        # Check if the chat is in TON Dev folder
        for d in dialog:
            if d.entity.id == chat.id:
                folder = await client(tl.functions.messages.GetDialogFiltersRequest())
                for f in folder:
                    if hasattr(f, 'title') and f.title == "TON Devs":
                        if any(p.peer.channel_id == chat.id for p in f.include_peers):
                            is_ton_dev = True
                            break
                break

        # Store in database
        with app.app_context():
            message = TelegramMessage(
                message_id=event.message.id,
                channel_id=str(chat.id),
                channel_title=chat_title,
                content=event.message.text,
                timestamp=event.message.date,
                is_ton_dev=is_ton_dev
            )
            db.session.add(message)
            db.session.commit()
            logger.info(f"Stored message from {chat_title} (TON Dev: {is_ton_dev})")

    except Exception as e:
        logger.error(f"Error handling message: {str(e)}")

async def main():
    """Main collector function"""
    try:
        logger.info("Starting collector using existing session...")
        await client.start()
        me = await client.get_me()
        logger.info(f"Connected as: {me.username}")
        logger.info("Listening for messages...")
        await client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Error: {str(e)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())