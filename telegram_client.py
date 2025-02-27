import logging
from telethon import TelegramClient, events
from app import db
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

            @self.client.on(events.NewMessage())
            async def message_handler(event):
                try:
                    # Only process messages from our target
                    if str(event.chat_id) != str(event.client.get_me().id):
                        return

                    message = TelegramMessage(
                        message_id=event.message.id,
                        channel_id=str(event.chat_id),
                        channel_title="Saved Messages",
                        sender_id=str(event.sender_id) if event.sender_id else None,
                        sender_username=None,
                        content=event.message.text,
                        timestamp=event.message.date
                    )

                    db.session.add(message)
                    db.session.commit()
                    logger.info(f"Stored message {message.message_id}")

                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    db.session.rollback()

            print("\n" + "="*50)
            print("TELEGRAM COLLECTOR RUNNING")
            print("Messages from Saved Messages will be collected")
            print("="*50 + "\n")

            await self.client.run_until_disconnected()

        except Exception as e:
            logger.error(f"Error in TelegramCollector: {e}")