
import os
import logging
import asyncio
from app import app, db
from models import TelegramMessage
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def diagnose_database():
    """Diagnose database issues"""
    with app.app_context():
        try:
            # Check total counts
            total_messages = TelegramMessage.query.count()
            print(f"Total messages in database: {total_messages}")
            
            # Check latest message
            latest_message = TelegramMessage.query.order_by(TelegramMessage.timestamp.desc()).first()
            if latest_message:
                print(f"Latest message: {latest_message.timestamp} from {latest_message.channel_title}")
                time_diff = datetime.utcnow() - latest_message.timestamp
                print(f"Age of latest message: {time_diff}")
                if time_diff > timedelta(hours=24):
                    print("WARNING: No new messages in the last 24 hours!")
            else:
                print("No messages found in database!")
            
            # Check channels
            channels = db.session.query(TelegramMessage.channel_id, 
                                      TelegramMessage.channel_title, 
                                      db.func.count(TelegramMessage.id).label('count'),
                                      db.func.max(TelegramMessage.timestamp).label('latest'))\
                               .group_by(TelegramMessage.channel_id)\
                               .all()
            
            print("\nChannel statistics:")
            for channel in channels:
                print(f"  - {channel.channel_title}: {channel.count} messages, latest: {channel.latest}")
            
            # Check possible issues with duplicate message IDs
            duplicate_check = db.session.query(
                TelegramMessage.message_id, 
                TelegramMessage.channel_id,
                db.func.count(TelegramMessage.id).label('count')
            ).group_by(
                TelegramMessage.message_id, 
                TelegramMessage.channel_id
            ).having(
                db.func.count(TelegramMessage.id) > 1
            ).all()
            
            if duplicate_check:
                print("\nWARNING: Found duplicate message IDs in the same channel:")
                for dup in duplicate_check:
                    print(f"  - Message ID {dup.message_id} in channel {dup.channel_id}: {dup.count} copies")
            else:
                print("\nNo duplicate message IDs found (good)")
                
        except Exception as e:
            print(f"Error diagnosing database: {str(e)}")

if __name__ == "__main__":
    asyncio.run(diagnose_database())
