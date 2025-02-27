import logging
from telethon import TelegramClient, events
from app import db, app
from models import TelegramMessage
from config import Config

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TelegramCollector:
    def __init__(self):
        self.client = TelegramClient(
            'ton_collector_session',
            Config.TELEGRAM_API_ID,
            Config.TELEGRAM_API_HASH
        )

    def start(self):
        import asyncio
        asyncio.run(self._start())

    async def _start(self):
        try:
            logger.info("Starting TelegramCollector...")
            await self.client.connect()

            if not await self.client.is_user_authorized():
                try:
                    print("\n" + "="*50)
                    print("TELEGRAM AUTHENTICATION REQUIRED")
                    print("="*50)

                    await self.client.send_code_request(Config.TELEGRAM_PHONE)
                    print(f"\n>>> A verification code has been sent to {Config.TELEGRAM_PHONE}")
                    code = input(">>> Enter the verification code here: ")

                    try:
                        await self.client.sign_in(Config.TELEGRAM_PHONE, code)
                    except Exception as e:
                        if "2FA" in str(e) or "password" in str(e).lower():
                            print("\n" + "="*50)
                            print("TWO-FACTOR AUTHENTICATION REQUIRED")
                            print("="*50)
                            password = input(">>> Please enter your 2FA password: ")
                            await self.client.sign_in(password=password)
                        else:
                            raise e

                except Exception as auth_error:
                    logger.error(f"Authentication error: {auth_error}")
                    return

            # Only process messages from our target
            @self.client.on(events.NewMessage())
            async def message_handler(event):
                try:
                    chat = await event.get_chat()

                    # Only process messages from specified TON channels
                    if not hasattr(chat, 'title') or not any(channel in chat.title for channel in Config.TON_CHANNELS):
                        return

                    sender = await event.get_sender()

                    # Save to database with app context
                    with app.app_context():
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
                        logger.info(f"Stored message {message.message_id}")

                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    if 'db' in locals():
                        db.session.rollback()

            print("\n" + "="*50)
            print("TELEGRAM COLLECTOR RUNNING")
            print("Messages from TON channels will be collected")
            print("="*50 + "\n")

            await self.client.run_until_disconnected()

        except Exception as e:
            logger.error(f"Error in TelegramCollector: {e}")