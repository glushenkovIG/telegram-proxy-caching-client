import pytest
from utils import should_be_ton_dev
from models import TelegramMessage
from app import db, app

def test_should_be_ton_dev():
    # Test various channel titles
    assert should_be_ton_dev("TON Dev Chat") == True
    assert should_be_ton_dev("Telegram Developers Community") == True
    assert should_be_ton_dev("TON 开发") == True  # Chinese
    assert should_be_ton_dev("Random Channel") == False
    assert should_be_ton_dev(None) == False
    assert should_be_ton_dev("") == False

@pytest.fixture
def test_app():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

def test_message_creation(test_app):
    with app.app_context():
        # Create a test message
        msg = TelegramMessage(
            message_id=1,
            channel_id="123",
            channel_title="TON Dev Chat",
            content="Test message",
            is_ton_dev=True
        )
        db.session.add(msg)
        db.session.commit()

        # Verify message was saved
        saved_msg = TelegramMessage.query.first()
        assert saved_msg is not None
        assert saved_msg.channel_title == "TON Dev Chat"
        assert saved_msg.is_ton_dev == True

def test_ton_dev_detection(test_app):
    test_channels = [
        ("TON Dev Chat", True),
        ("Telegram Developers Community", True),
        ("TON 开发", True),
        ("Some Other Channel", False)
    ]

    with app.app_context():
        for title, expected in test_channels:
            msg = TelegramMessage(
                message_id=len(TelegramMessage.query.all()) + 1,
                channel_id=str(id(title)),  # Unique ID for each test channel
                channel_title=title,
                content="Test message"
            )
            msg.is_ton_dev = should_be_ton_dev(title)
            db.session.add(msg)
            db.session.commit()

            saved_msg = TelegramMessage.query.filter_by(channel_title=title).first()
            assert saved_msg.is_ton_dev == expected, f"Failed for channel: {title}"