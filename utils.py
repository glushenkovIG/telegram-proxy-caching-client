import logging

logger = logging.getLogger(__name__)

def should_be_ton_dev(channel_title: str) -> bool:
    """Check if a channel is TON development related."""
    if not channel_title:
        return False
        
    keywords = ["ton dev", "ton development", "telegram developers", "ton 开发"]
    channel_title_lower = channel_title.lower()
    return any(keyword in channel_title_lower for keyword in keywords)

def get_proper_dialog_type(entity) -> str:
    """Determine the proper dialog type from a Telegram entity."""
    try:
        from telethon.tl.types import (
            User, Chat, Channel,
            UserEmpty, ChatEmpty, ChatForbidden,
            ChannelForbidden
        )
        
        if isinstance(entity, User):
            if entity.bot:
                return 'bot'
            elif entity.deleted:
                return 'deleted_account'
            return 'private'
        elif isinstance(entity, Chat):
            if isinstance(entity, (ChatEmpty, ChatForbidden)):
                return 'unknown'
            return 'group'
        elif isinstance(entity, Channel):
            if isinstance(entity, ChannelForbidden):
                return 'unknown'
            if entity.megagroup:
                return 'public_supergroup' if entity.username else 'private_supergroup'
            return 'channel'
        return 'unknown'
    except Exception as e:
        logger.error(f"Error determining dialog type: {str(e)}")
        return 'unknown'
