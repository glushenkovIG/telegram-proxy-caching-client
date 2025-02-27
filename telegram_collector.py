import os
import logging
import sys
from telethon import TelegramClient, events
from config import Config
from app import app, db
from models import TelegramMessage

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
            print("\n" + "="*50)
            print("TELEGRAM AUTHENTICATION REQUIRED")
            print("="*50)

            # Request verification code
            await client.send_code_request(Config.TELEGRAM_PHONE)
            print(f"\n>>> Code sent to {Config.TELEGRAM_PHONE}")
            print(">>> Please enter the code below:")
            code = input(">>> Code: ")

            try:
                await client.sign_in(Config.TELEGRAM_PHONE, code)
            except Exception as e:
                if "2FA" in str(e) or "password" in str(e).lower():
                    print("\n" + "="*50)
                    print("TWO-FACTOR AUTHENTICATION REQUIRED")
                    print("="*50)
                    password = input(">>> 2FA Password: ")
                    await client.sign_in(password=password)
                else:
                    raise e

        print("\nSuccessfully connected to Telegram!")

        # Get all dialogs and filter TON-related ones
        print("\nFetching TON development channels...")
        dialogs = await client.get_dialogs()
        ton_channels = [d for d in dialogs if d.name and any(channel in d.name for channel in Config.TON_CHANNELS)]

        if not ton_channels:
            print("No TON development channels found! Please make sure you have access to these channels.")
            print("Required channels:", ", ".join(Config.TON_CHANNELS))
            return

        print("\nMonitoring the following TON channels:")
        for channel in ton_channels:
            print(f"- {channel.name}")

        @client.on(events.NewMessage)
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
                    logger.info(f"Saved message {message.message_id} from {chat.title}")

                # Print to console
                print("\n" + "="*50)
                print(f"Channel: {chat.title}")
                print(f"From: {sender.username or sender.first_name if sender else 'Unknown'}")
                print("-"*50)
                print(f"{event.message.text}")
                print(f"Time: {event.message.date}")
                print("="*50)

            except Exception as e:
                logger.error(f"Error handling message: {e}")
                if 'db' in locals():
                    db.session.rollback()

        print("\n" + "="*50)
        print("TELEGRAM COLLECTOR RUNNING")
        print("Monitoring TON development channels and saving to database")
        print("="*50 + "\n")

        await client.run_until_disconnected()

    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
