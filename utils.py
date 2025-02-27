# Shared utility functions for TON message collection and processing
import logging

logger = logging.getLogger(__name__)

def should_be_ton_dev(channel_title):
    """Determine if a channel is TON development related based on its title."""
    if not channel_title:
        return False

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
    
    channel_title_lower = channel_title.lower()
    for keyword in keywords:
        if keyword.lower() in channel_title_lower:
            logger.info(f"Channel '{channel_title}' matched TON Dev keyword: {keyword}")
            return True
            
    return False
