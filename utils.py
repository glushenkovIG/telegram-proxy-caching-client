# Shared utility functions for TON message collection and processing
import logging

logger = logging.getLogger(__name__)

def should_be_ton_dev(channel_title):
    """Determine if a channel title indicates a TON developer channel"""
    ton_dev_keywords = [
        'ton dev', 
        'telegram developers', 
        'ton development',
        'ton developers',
        'ton community',
        'ton research',
        'ton jobs',
        'ton tact',
        'ton data hub',
        'ton society',
        'hackers league',
        'ton status',
        'ton contests'
    ]

    channel_title_lower = channel_title.lower()

    # Exact channel matches
    exact_matches = [
        'ton dev chat',
        'ton dev news',
        'ton dev chat (中文)',
        'ton dev chat (en)',
        'ton dev chat (py)',
        'ton dev chat (ру)',
        'telegram developers community',
        'ton society chat',
        'ton data hub chat',
        'ton tact language chat',
        'hackers league hackathon',
        'ton research',
        'ton community',
        'ton jobs',
        'ton status',
        'testnet ton status',
        'ton contests',
        'botnews',
        'the open network'
    ]

    for match in exact_matches:
        if channel_title_lower == match.lower():
            logger.info(f"Channel '{channel_title}' exactly matched TON channel: {match}")
            return True

    # Keyword-based matches
    for keyword in ton_dev_keywords:
        if keyword.lower() in channel_title_lower:
            logger.info(f"Channel '{channel_title}' matched TON keyword: {keyword}")
            return True

    return False