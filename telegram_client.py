import asyncio
import os
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

async def main():
    """Interactive setup for Telegram client"""
    print("Setting up Telegram client...")
    api_id = input("Enter your Telegram API ID: ")
    api_hash = input("Enter your Telegram API Hash: ")

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

    # Save credentials to environment
    os.environ["TELEGRAM_API_ID"] = api_id
    os.environ["TELEGRAM_API_HASH"] = api_hash
    print("Please add these to your Replit Secrets:")
    print(f"TELEGRAM_API_ID = {api_id}")
    print(f"TELEGRAM_API_HASH = {api_hash}")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())