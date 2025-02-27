import os
import logging
from app import app, db
from models import TelegramMessage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def should_be_ton_dev(channel_title):
    if not channel_title:
        return False

    keywords = [
        "ton dev", 
        "ton development", 
        "开发",  # Chinese
        "developers",
        "telegram developers"
    ]
    return any(keyword.lower() in channel_title.lower() for keyword in keywords)

def update_labels():
    with app.app_context():
        try:
            # Get all messages
            messages = TelegramMessage.query.all()
            logger.info(f"Found {len(messages)} messages to process")

            update_count = 0
            for message in messages:
                try:
                    # Apply the same logic as in collector.py
                    new_is_ton_dev = should_be_ton_dev(message.channel_title)

                    if message.is_ton_dev != new_is_ton_dev:
                        message.is_ton_dev = new_is_ton_dev
                        update_count += 1

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