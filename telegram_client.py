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
        self.client = TelegramClient('ton_collector_session',
                                   Config.TELEGRAM_API_ID,
                                   Config.TELEGRAM_API_HASH)
        self.is_connected = False

    async def start(self):
        try:
            logger.info("Starting TelegramCollector...")
            await self.client.connect()

            if not await self.client.is_user_authorized():
                try:
                    # Clear console and show prominent message
                    print("\n" + "="*50)
                    print("TELEGRAM AUTHENTICATION REQUIRED")
                    print("="*50)

                    # Send code request
                    await self.client.send_code_request(Config.TELEGRAM_PHONE)
                    logger.info(f"Verification code sent to {Config.TELEGRAM_PHONE}")

                    print(f"\n>>> A verification code has been sent to {Config.TELEGRAM_PHONE}")
                    print(">>> Please check your Telegram messages")
                    code = input(">>> Enter the verification code here: ")

                    try:
                        # Try to sign in with the code
                        await self.client.sign_in(Config.TELEGRAM_PHONE, code)
                    except Exception as e:
                        if "2FA" in str(e) or "password" in str(e).lower():
                            # Clear 2FA request
                            print("\n" + "="*50)
                            print("TWO-FACTOR AUTHENTICATION REQUIRED")
                            print("="*50)
                            password = input(">>> Please enter your 2FA password: ")
                            await self.client.sign_in(password=password)
                        else:
                            raise e

                    logger.info("Successfully signed in!")

                except Exception as auth_error:
                    logger.error(f"Authentication error: {auth_error}")
                    return False

            # Set up message handler
            @self.client.on(events.NewMessage())
            async def message_handler(event):
                try:
                    # Only process messages from our target
                    if str(event.chat_id) != str(event.client.get_me().id):
                        return

                    logger.info(f"New message received: ID {event.message.id}")

                    # Create message record
                    message = TelegramMessage(
                        message_id=event.message.id,
                        channel_id=str(event.chat_id),
                        channel_title="Saved Messages",
                        sender_id=str(event.sender_id) if event.sender_id else None,
                        sender_username=None,  # Will be updated when sender info is available
                        content=event.message.text,
                        timestamp=event.message.date
                    )

                    # Try to get sender info
                    try:
                        sender = await event.get_sender()
                        if sender:
                            message.sender_username = sender.username
                    except Exception as sender_error:
                        logger.warning(f"Could not get sender info: {sender_error}")

                    # Save to database
                    db.session.add(message)
                    db.session.commit()
                    logger.info(f"Stored message {message.message_id}")

                except Exception as message_error:
                    logger.error(f"Error processing message: {message_error}")
                    db.session.rollback()

            self.is_connected = True
            logger.info("TelegramCollector started successfully")
            print("\n" + "="*50)
            print("TELEGRAM COLLECTOR RUNNING")
            print("Messages from Saved Messages will be collected")
            print("="*50 + "\n")

            # Keep the client running
            await self.client.run_until_disconnected()
            return True

        except Exception as e:
            logger.error(f"Error in TelegramCollector.start(): {e}")
            self.is_connected = False
            return False

    def is_running(self):
        return self.is_connected