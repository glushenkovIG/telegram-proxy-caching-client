import os
import asyncio
import logging
from datetime import datetime, timedelta
from telethon import TelegramClient
from app import app, db
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
        with app.app_context():
            latest_msg = TelegramMessage.query.filter_by(
                channel_id=channel_id
            ).order_by(TelegramMessage.message_id.desc()).first()

            latest_id = latest_msg.message_id if latest_msg else 0
            logger.info(f"Latest message ID in database: {latest_id}")

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
                            new_msg = TelegramMessage(
                                message_id=message.id,
                                channel_id=channel_id,
                                channel_title=channel_title,
                                content=message.text,
                                timestamp=message.date,
                                is_ton_dev=False,  # Not a TON dev channel
                                is_outgoing=is_outgoing,
                                dialog_type=dialog_type
                            )

                            messages_to_process.append(new_msg)

                            if len(messages_to_process) >= 10:  # Commit in smaller chunks
                                db.session.add_all(messages_to_process)
                                db.session.commit()
                                total_imported += len(messages_to_process)
                                logger.info(f"Saved {len(messages_to_process)} messages, total so far: {total_imported}")
                                messages_to_process = []

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
                db.session.add_all(messages_to_process)
                db.session.commit()
                total_imported += len(messages_to_process)

            logger.info(f"Import completed. Total messages imported: {total_imported}")

    except Exception as e:
        logger.error(f"Error importing EACC messages: {str(e)}")
    finally:
        if client:
            await client.disconnect()
            logger.info("Disconnected Telegram client")

def run_importer():
    """Run the importer"""
    with app.app_context():
        asyncio.run(import_eacc_messages())

if __name__ == "__main__":
    run_importer()