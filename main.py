import os
import logging
from telethon import TelegramClient, events
from config import Config

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    try:
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

                print("\nNew message received:")
                if hasattr(chat, 'title'):
                    print(f"Channel/Group: {chat.title}")
                else:
                    print(f"From: {sender.username or sender.first_name}")
                print(f"Content: {event.message.text}")
                print(f"Time: {event.message.date}")
                print("-" * 50)
            except Exception as e:
                logger.error(f"Error handling message: {e}")

        print("\n" + "="*50)
        print("TELEGRAM COLLECTOR RUNNING")
        print("Monitoring ALL messages...")
        print("="*50 + "\n")

        await client.run_until_disconnected()

    except Exception as e:
        logger.error(f"Error in main: {str(e)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())