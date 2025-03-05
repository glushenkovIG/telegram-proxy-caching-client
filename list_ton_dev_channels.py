
from app import app, db
from models import TelegramMessage
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def list_ton_dev_channels():
    """List all channels marked as TON Dev and their message counts"""
    with app.app_context():
        try:
            # Get channels marked as TON Dev
            channels = db.session.query(
                TelegramMessage.channel_id,
                TelegramMessage.channel_title,
                db.func.count(TelegramMessage.id).label('message_count')
            ).filter(
                TelegramMessage.is_ton_dev == True
            ).group_by(
                TelegramMessage.channel_id, 
                TelegramMessage.channel_title
            ).all()
            
            print(f"\nFound {len(channels)} TON Dev channels:")
            print("="*70)
            print(f"{'Channel Title':<50} | {'Message Count':>10}")
            print("-"*70)
            
            total_messages = 0
            for channel in channels:
                print(f"{channel.channel_title:<50} | {channel.message_count:>10}")
                total_messages += channel.message_count
                
            print("="*70)
            print(f"Total TON Dev messages: {total_messages}")
            
            # Also show most recent messages
            latest_messages = TelegramMessage.query.filter(
                TelegramMessage.is_ton_dev == True
            ).order_by(
                TelegramMessage.timestamp.desc()
            ).limit(5).all()
            
            if latest_messages:
                print("\nMost recent messages:")
                for msg in latest_messages:
                    print(f"[{msg.timestamp}] {msg.channel_title}: {msg.content[:50]}...")
            
        except Exception as e:
            logger.error(f"Error listing TON Dev channels: {str(e)}")

if __name__ == "__main__":
    list_ton_dev_channels()
