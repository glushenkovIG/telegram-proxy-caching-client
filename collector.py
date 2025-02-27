import os
from telethon import TelegramClient, events

# Telegram API credentials
API_ID = os.environ.get('TELEGRAM_API_ID')
API_HASH = os.environ.get('TELEGRAM_API_HASH')

# Initialize client
client = TelegramClient('ton_collector_session', API_ID, API_HASH)

@client.on(events.NewMessage)
async def handle_message(event):
    """Print all incoming messages"""
    try:
        # Get chat and sender info
        chat = await event.get_chat()
        sender = await event.get_sender()

        # Print message details with clear formatting
        print("\n" + "="*50)
        print(f"Channel: {chat.title if hasattr(chat, 'title') else 'Private'}")
        print(f"From: {sender.username or sender.first_name if sender else 'Unknown'}")
        print("-"*50)
        print(f"Message: {event.message.text}")
        print(f"Time: {event.message.date}")
        print("="*50)

    except Exception as e:
        print(f"Error handling message: {e}")

async def main():
    """Main function to run the client"""
    try:
        print("\nConnecting to Telegram...")
        await client.connect()

        if not await client.is_user_authorized():
            print("\nAuthentication required")
            await client.send_code_request(os.environ.get('TELEGRAM_PHONE'))
            code = input("Enter the verification code: ")
            try:
                await client.sign_in(os.environ.get('TELEGRAM_PHONE'), code)
            except Exception as e:
                if "2FA" in str(e):
                    password = input("Enter 2FA password: ")
                    await client.sign_in(password=password)
                else:
                    raise e

        print("\nConnected successfully!")
        print("Listening for messages... Press Ctrl+C to stop")

        await client.run_until_disconnected()

    except Exception as e:
        print(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())