
import os
import asyncio
import logging
import random
import sqlite3
from datetime import datetime, timedelta
from telethon import TelegramClient
from app import app
from models import TelegramMessage
from utils import get_proper_dialog_type

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('eacc_importer')

async def import_eacc_messages():
    """Import messages from EACC channel"""
    client = None
    eacc_db_path = 'instance/eacc_messages.db'
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(eacc_db_path), exist_ok=True)
    
    # Initialize the separate database with a timeout for when the DB is locked
    # and the proper isolation level for concurrent access
    conn = sqlite3.connect(eacc_db_path, timeout=30.0)
    conn.isolation_level = 'IMMEDIATE'  # This helps prevent locks
    cursor = conn.cursor()
    
    # Create table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS telegram_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER NOT NULL,
        channel_id TEXT NOT NULL,
        channel_title TEXT,
        content TEXT,
        timestamp TIMESTAMP,
        is_ton_dev BOOLEAN DEFAULT 0,
        is_outgoing BOOLEAN DEFAULT 0,
        dialog_type TEXT,
        sender_id TEXT,
        sender_username TEXT
    )
    ''')
    conn.commit()
    
    try:
        logger.info("Starting EACC chat import process")
        session_path = 'ton_collector_session.session'

        # Check if session exists
        if not os.path.exists(session_path):
            logger.error("Session file not found. Please run setup first")
            return

        # Initialize client with dummy values when reusing session
        client = TelegramClient(
            session_path,
            api_id=1,  # Dummy value, not used with existing session
            api_hash='dummy',  # Dummy value, not used with existing session
            system_version="4.16.30-vxCUSTOM"
        )

        await client.connect()

        if not await client.is_user_authorized():
            logger.error("Session unauthorized. Please run setup first")
            return

        logger.info("Successfully connected using existing session")

        # Get the EACC chat entity
        eacc_chat = 'eaccchat'
        entity = await client.get_entity(eacc_chat)

        if not entity:
            logger.error(f"Could not find chat: {eacc_chat}")
            return

        channel_id = str(entity.id)
        channel_title = getattr(entity, 'title', eacc_chat)
        dialog_type = get_proper_dialog_type(entity)

        logger.info(f"Found chat: {channel_title} with ID: {channel_id}")

        # Get latest stored message ID for this channel
        cursor.execute(
            "SELECT message_id FROM telegram_messages WHERE channel_id = ? ORDER BY message_id DESC LIMIT 1",
            (channel_id,)
        )
        result = cursor.fetchone()
        latest_id = result[0] if result else 0
        logger.info(f"Latest message ID in EACC database: {latest_id}")

        # Batch size for processing messages
        batch_size = 100 # Increased batch size
        total_imported = 0
        total_messages_estimate = 107000  # Total messages in the chat

        # Calculate time estimates
        start_time = datetime.now()

        # We'll use larger batches while still being careful with rate limits
        messages_to_process = []

        # Start from the beginning if no messages are found
        logger.info(f"Fetching messages (limit: {batch_size})...")

        batch_counter = 0
        offset_id = 0  # Start from most recent messages

        # If we have messages in the DB already, start from the latest one
        # Otherwise, we'll get all messages

        while True:
            batch_counter += 1
            logger.info(f"Fetching batch #{batch_counter} (offset_id: {offset_id})")

            # Get messages with a small batch size to avoid rate limits
            messages = await client.get_messages(
                entity, 
                limit=batch_size,
                offset_id=offset_id
            )

            if not messages or len(messages) == 0:
                logger.info("No more messages to process")
                break

            # Update offset for next batch
            offset_id = messages[-1].id

            for message in messages:
                # Skip if we've already processed this message
                if message.id <= latest_id and latest_id != 0:
                    logger.debug(f"Skipping message {message.id} - already processed")
                    continue

                if message.text:
                    try:
                        is_outgoing = getattr(message, 'out', False)

                        # Create new message object
                        # Get sender information
                        sender = await message.get_sender()
                        sender_id = str(sender.id) if sender else None
                        sender_username = getattr(sender, 'username', None)
                        
                        new_msg = TelegramMessage(
                            message_id=message.id,
                            channel_id=channel_id,
                            channel_title=channel_title,
                            content=message.text,
                            timestamp=message.date,
                            is_ton_dev=False,  # Not a TON dev channel
                            is_outgoing=is_outgoing,
                            dialog_type=dialog_type,
                            sender_id=sender_id,
                            sender_username=sender_username
                        )

                        messages_to_process.append(new_msg)

                        if len(messages_to_process) >= 10:  # Commit in smaller chunks
                            # Add retry logic for database operations
                            max_retries = 5
                            retry_count = 0
                            retry_delay = 1  # Start with 1 second delay
                            
                            while retry_count < max_retries:
                                try:
                                    for msg in messages_to_process:
                                        cursor.execute(
                                            """
                                            INSERT INTO telegram_messages 
                                            (message_id, channel_id, channel_title, content, timestamp, is_ton_dev, is_outgoing, dialog_type, sender_id, sender_username)
                                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                            """,
                                            (
                                                msg.message_id, 
                                                msg.channel_id, 
                                                msg.channel_title, 
                                                msg.content, 
                                                msg.timestamp, 
                                                msg.is_ton_dev, 
                                                msg.is_outgoing, 
                                                msg.dialog_type,
                                                msg.sender_id,
                                                msg.sender_username
                                            )
                                        )
                                    conn.commit()
                                    total_imported += len(messages_to_process)
                                    logger.info(f"Saved {len(messages_to_process)} messages, total so far: {total_imported}")
                                    messages_to_process = []
                                    break  # Successfully committed, exit retry loop
                                except Exception as e:
                                    if "database is locked" in str(e).lower():
                                        retry_count += 1
                                        logger.warning(f"Database locked, retry attempt {retry_count}/{max_retries} after {retry_delay}s")
                                        await asyncio.sleep(retry_delay)
                                        # Exponential backoff with jitter
                                        retry_delay = min(retry_delay * 2, 30) + (random.random() * 2)
                                    else:
                                        logger.error(f"Error saving messages: {str(e)}")
                                        break
                            
                            if retry_count >= max_retries:
                                logger.error("Max retries exceeded for database commit")
                            
                            # Sleep to avoid hitting rate limits
                            await asyncio.sleep(2)  # Reduced sleep time as requested
                    except Exception as e:
                        logger.error(f"Error processing message {message.id}: {str(e)}")

            # If we didn't get a full batch, we've reached the end
            if len(messages) < batch_size:
                logger.info("Reached the end of available messages")
                break

            # Sleep between batches to avoid rate limits
            elapsed_time = datetime.now() - start_time
            messages_processed = total_imported
            messages_remaining = total_messages_estimate - messages_processed
            try:
                messages_per_second = messages_processed / elapsed_time.total_seconds()
                estimated_remaining_time = timedelta(seconds=(messages_remaining / messages_per_second))
                logger.info(f"Estimated time remaining: {estimated_remaining_time}")
            except ZeroDivisionError:
                logger.info("Not enough data to estimate time remaining.")

            logger.info(f"Waiting 2 seconds before next batch")
            await asyncio.sleep(2)  # Reduced sleep time as requested

        # Save any remaining messages
        if messages_to_process:
            max_retries = 5
            retry_count = 0
            retry_delay = 1
            
            while retry_count < max_retries:
                try:
                    for msg in messages_to_process:
                        cursor.execute(
                            """
                            INSERT INTO telegram_messages 
                            (message_id, channel_id, channel_title, content, timestamp, is_ton_dev, is_outgoing, dialog_type, sender_id, sender_username)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                msg.message_id, 
                                msg.channel_id, 
                                msg.channel_title, 
                                msg.content, 
                                msg.timestamp, 
                                msg.is_ton_dev, 
                                msg.is_outgoing, 
                                msg.dialog_type,
                                msg.sender_id,
                                msg.sender_username
                            )
                        )
                    conn.commit()
                    total_imported += len(messages_to_process)
                    break
                except Exception as e:
                    if "database is locked" in str(e).lower():
                        retry_count += 1
                        logger.warning(f"Database locked, retry attempt {retry_count}/{max_retries} after {retry_delay}s")
                        await asyncio.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, 30) + (random.random() * 2)
                    else:
                        logger.error(f"Error saving final messages batch: {str(e)}")
                        break
            
            if retry_count >= max_retries:
                logger.error("Max retries exceeded for final database commit")

        logger.info(f"Import completed. Total messages imported: {total_imported}")

    except Exception as e:
        logger.error(f"Error importing EACC messages: {str(e)}")
    finally:
        if client:
            await client.disconnect()
            logger.info("Disconnected Telegram client")
        
        # Close the database connection
        if 'conn' in locals() and conn:
            conn.close()
            logger.info("Closed EACC database connection")

def run_importer():
    """Run the importer"""
    asyncio.run(import_eacc_messages())

if __name__ == "__main__":
    run_importer()
