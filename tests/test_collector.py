import pytest
import asyncio
from unittest.mock import MagicMock, patch
from collector import collect_messages, should_be_ton_dev
from models import TelegramMessage
from app import db, app

@pytest.fixture
def mock_client():
    class MockMessage:
        def __init__(self, id, text, date):
            self.id = id
            self.text = text
            self.date = date

    class MockDialog:
        def __init__(self, id, title):
            self.id = id
            self.title = title
            
        async def iter_messages(self, limit):
            messages = [
                MockMessage(1, "Test message 1", "2025-02-27"),
                MockMessage(2, "Test message 2", "2025-02-27")
            ]
            for msg in messages:
                yield msg

    async def mock_get_dialogs(*args, **kwargs):
        return [
            MockDialog(1, "TON Dev Chat"),
            MockDialog(2, "Telegram Developers Community"),
            MockDialog(3, "Regular Channel")
        ]

    client = MagicMock()
    client.get_dialogs = mock_get_dialogs
    return client

@pytest.fixture
def test_app():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.mark.asyncio
async def test_collect_messages(test_app, mock_client):
    with app.app_context():
        # Clear any existing messages
        TelegramMessage.query.delete()
        db.session.commit()
        
        # Run collector
        await collect_messages(mock_client)
        
        # Verify messages were collected
        messages = TelegramMessage.query.all()
        assert len(messages) > 0
        
        # Verify TON Dev messages are labeled correctly
        ton_dev_messages = TelegramMessage.query.filter_by(is_ton_dev=True).all()
        for msg in ton_dev_messages:
            assert any(keyword in msg.channel_title.lower() 
                      for keyword in ["ton dev", "developers", "开发"])

@pytest.mark.asyncio
async def test_duplicate_message_handling(test_app, mock_client):
    with app.app_context():
        # Add an existing message
        existing_msg = TelegramMessage(
            message_id=1,
            channel_id="1",
            channel_title="TON Dev Chat",
            content="Test message 1",
            is_ton_dev=True
        )
        db.session.add(existing_msg)
        db.session.commit()
        
        # Run collector
        await collect_messages(mock_client)
        
        # Verify no duplicate messages
        messages = TelegramMessage.query.filter_by(message_id=1).all()
        assert len(messages) == 1
