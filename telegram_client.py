
import asyncio
import os
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

async def main():
    """Interactive setup for Telegram client"""
    print("Setting up Telegram client...")
    
    # Get API credentials from environment
    api_id = os.environ.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH")
    
    if not api_id or not api_hash:
        print("API credentials not found in environment variables.")
        api_id = input("Enter your Telegram API ID: ")
        api_hash = input("Enter your Telegram API Hash: ")
        os.environ["TELEGRAM_API_ID"] = api_id
        os.environ["TELEGRAM_API_HASH"] = api_hash

    client = TelegramClient('ton_collector_session', int(api_id), api_hash)

    await client.connect()
    if not await client.is_user_authorized():
        phone = input("Enter your phone number (with country code): ")
        await client.send_code_request(phone)
        code = input("Enter the code you received: ")
        try:
            await client.sign_in(phone, code)
        except SessionPasswordNeededError:
            password = input("Enter your 2FA password: ")
            await client.sign_in(password=password)

    print("Successfully authenticated! The collector can now run.")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
