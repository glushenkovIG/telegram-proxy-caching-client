import logging
from flask import Blueprint, jsonify, request
from models import TelegramMessage
from .auth import require_api_key
from app import db

# Configure logging
logger = logging.getLogger(__name__)

api = Blueprint('api', __name__)

@api.route('/messages', methods=['GET'])
@require_api_key
def get_messages():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 100)
        channel = request.args.get('channel')

        query = TelegramMessage.query

        if channel:
            query = query.filter_by(channel_title=channel)

        messages = query.order_by(TelegramMessage.timestamp.desc())\
                       .paginate(page=page, per_page=per_page)

        return jsonify({
            'messages': [msg.to_dict() for msg in messages.items],
            'total': messages.total,
            'pages': messages.pages,
            'current_page': messages.page
        })

    except Exception as e:
        logger.error(f"Error in get_messages: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api.route('/channels', methods=['GET'])
@require_api_key
def get_channels():
    try:
        channels = db.session.query(TelegramMessage.channel_title)\
                           .distinct()\
                           .all()
        return jsonify({
            'channels': [channel[0] for channel in channels if channel[0]]
        })
    except Exception as e:
        logger.error(f"Error in get_channels: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api.route('/search', methods=['GET'])
@require_api_key
def search_messages():
    try:
        query = request.args.get('q')
        if not query:
            return jsonify({'error': 'Search query required'}), 400

        messages = TelegramMessage.query\
            .filter(TelegramMessage.content.ilike(f'%{query}%'))\
            .order_by(TelegramMessage.timestamp.desc())\
            .limit(100)\
            .all()

        return jsonify({
            'messages': [msg.to_dict() for msg in messages]
        })
    except Exception as e:
        logger.error(f"Error in search_messages: {str(e)}")
        return jsonify({'error': str(e)}), 500