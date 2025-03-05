import pytest
from unittest.mock import MagicMock, patch
from collector import collect_messages
from models import TelegramMessage
from utils import should_be_ton_dev

@pytest.fixture
def mock_telegram_message():
    return MagicMock(
        id=1,
        text="Test message",
        date="2025-02-27"
    )

@pytest.fixture
def mock_telegram_channel():
    return MagicMock(
        id=123,
        title="TON Dev Chat"
    )

def test_should_be_ton_dev():
    """Test TON dev channel detection"""
    # Test positive cases
    assert should_be_ton_dev("TON Dev Chat") == True
    assert should_be_ton_dev("TON Development") == True
    assert should_be_ton_dev("Telegram Developers") == True
    assert should_be_ton_dev("TON 开发") == True

    # Test negative cases
    assert should_be_ton_dev("Random Chat") == False
    assert should_be_ton_dev("") == False
    assert should_be_ton_dev(None) == False

@pytest.mark.asyncio
async def test_collect_messages_handles_empty_session():
    """Test collector behavior when no session exists"""
    # Mock os.path.exists to return False
    with patch('os.path.exists') as mock_exists:
        mock_exists.return_value = False
        await collect_messages()
        # Should exit early with a log message
        mock_exists.assert_called_once_with('ton_collector_session.session')

@pytest.mark.asyncio
async def test_collect_messages_processes_ton_channels(mock_telegram_channel, mock_telegram_message):
    """Test collector properly processes TON dev channels"""
    # Mock the TelegramClient
    mock_client = MagicMock()
    mock_client.get_dialogs.return_value = [mock_telegram_channel]
    mock_client.iter_messages.return_value = [mock_telegram_message]
    
    with patch('telethon.TelegramClient', return_value=mock_client):
        await collect_messages()
        
        # Verify dialog was processed
        mock_client.get_dialogs.assert_called_once()
        mock_client.iter_messages.assert_called_once()
