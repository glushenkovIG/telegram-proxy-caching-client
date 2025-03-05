
import logging
from app import app, db
from models import TelegramMessage
from utils import should_be_ton_dev

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_ton_channels():
    """Update is_ton_dev flag for all messages based on expanded channel list"""
    with app.app_context():
        try:
            # Get all unique channels
            channels = db.session.query(
                TelegramMessage.channel_id,
                TelegramMessage.channel_title
            ).distinct().all()
            
            logger.info(f"Found {len(channels)} unique channels to evaluate")
            
            updated_channels = 0
            for channel in channels:
                channel_id = channel.channel_id
                channel_title = channel.channel_title
                
                # Determine if channel should be marked as TON Dev
                is_ton_dev = should_be_ton_dev(channel_title)
                
                # Update all messages for this channel
                result = db.session.query(TelegramMessage).filter(
                    TelegramMessage.channel_id == channel_id,
                    TelegramMessage.is_ton_dev != is_ton_dev
                ).update({TelegramMessage.is_ton_dev: is_ton_dev})
                
                if result > 0:
                    updated_channels += 1
                    logger.info(f"Updated channel '{channel_title}' to is_ton_dev={is_ton_dev}, {result} messages affected")
            
            db.session.commit()
            logger.info(f"Successfully updated {updated_channels} channels")
            
            # Now show the current TON Dev channels
            ton_channels = db.session.query(
                TelegramMessage.channel_title,
                db.func.count(TelegramMessage.id).label('message_count')
            ).filter(
                TelegramMessage.is_ton_dev == True
            ).group_by(
                TelegramMessage.channel_title
            ).all()
            
            print(f"\nCurrent TON Dev channels ({len(ton_channels)}):")
            print("="*70)
            print(f"{'Channel Title':<50} | {'Message Count':>10}")
            print("-"*70)
            
            for channel in ton_channels:
                print(f"{channel.channel_title:<50} | {channel.message_count:>10}")
                
            print("="*70)
            
        except Exception as e:
            logger.error(f"Error updating TON channels: {str(e)}")
            db.session.rollback()

if __name__ == "__main__":
    update_ton_channels()
