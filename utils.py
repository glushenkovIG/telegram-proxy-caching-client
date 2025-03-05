# Shared utility functions for TON message collection and processing
import logging

logger = logging.getLogger(__name__)

def should_be_ton_dev(channel_title):
    """Determine if a channel is TON development related based on its title."""
    if not channel_title:
        return False

    # Specific TON channel names (exact matches)
    ton_channels = [
        "TON Dev News",
        "TON Dev Chat",
        "TON Dev Chat (中文)",
        "Telegram Developers Community",
        "TON Society Chat",
        "TON Data Hub Chat",
        "TON Tact Language Chat",
        "Hackers League Hackathon",
        "TON Research",
        "TON Community",
        "TON Jobs",
        "TON Data Hub",
        "TON Status",
        "Testnet TON Status",
        "TON Contests",
        "BotNews",
        "The Open Network"
    ]
    
    # Keywords for broader matching
    keywords = [
        "ton dev",
        "ton development",
        "开发",  # Chinese
        "developers",
        "telegram developers",
        "TON Developers",
        "TON Dev",
        "电报开发",  # Additional Chinese variants
        "TON开发"
    ]
    
    # Check for exact channel matches first
    for channel in ton_channels:
        if channel_title.strip() == channel:
            logger.info(f"Channel '{channel_title}' exactly matched TON channel: {channel}")
            return True
    
    # Then check for keyword matches
    channel_title_lower = channel_title.lower()
    for keyword in keywords:
        if keyword.lower() in channel_title_lower:
            logger.info(f"Channel '{channel_title}' matched TON Dev keyword: {keyword}")
            return True
            
    return False
