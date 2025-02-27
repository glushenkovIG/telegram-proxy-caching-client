from datetime import datetime
from sqlalchemy.sql import expression
from app import db

class TelegramMessage(db.Model):
    """Model for storing all Telegram messages"""
    __tablename__ = 'telegram_messages'

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, nullable=False)
    channel_id = db.Column(db.String(100), nullable=False)
    channel_title = db.Column(db.String(200))
    channel_username = db.Column(db.String(100))
    sender_id = db.Column(db.String(100))
    sender_username = db.Column(db.String(100))
    content = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_ton_dev = db.Column(db.Boolean, server_default=expression.false())

    def to_dict(self):
        return {
            'id': self.id,
            'message_id': self.message_id,
            'channel_id': self.channel_id,
            'channel_title': self.channel_title,
            'channel_username': self.channel_username,
            'sender_id': self.sender_id,
            'sender_username': self.sender_username,
            'content': self.content,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'is_ton_dev': self.is_ton_dev
        }