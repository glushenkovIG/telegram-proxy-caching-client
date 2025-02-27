import os
import logging
from app import app, db
from models import TelegramMessage
from utils import should_be_ton_dev

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_labels():
    with app.app_context():
        try:
            # Get all messages
            messages = TelegramMessage.query.all()
            logger.info(f"Found {len(messages)} messages to process")

            update_count = 0
            for message in messages:
                try:
                    # Use the shared logic from utils.py
                    new_is_ton_dev = should_be_ton_dev(message.channel_title)

                    if message.is_ton_dev != new_is_ton_dev:
                        message.is_ton_dev = new_is_ton_dev
                        update_count += 1
                        logger.info(f"Updated label for message in channel: {message.channel_title} to {new_is_ton_dev}")

                        if update_count % 100 == 0:
                            logger.info(f"Updated {update_count} messages so far")
                            db.session.commit()
                except Exception as e:
                    logger.error(f"Error processing message {message.id}: {str(e)}")
                    continue

            # Final commit for remaining changes
            db.session.commit()
            logger.info(f"Successfully updated {update_count} messages")

        except Exception as e:
            logger.error(f"Error updating labels: {str(e)}")
            db.session.rollback()

if __name__ == "__main__":
    update_labels()