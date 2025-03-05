from flask import Blueprint, render_template, request, jsonify
from models import TelegramMessage, db

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    # Get filter from query parameters
    filter_type = request.args.get('filter', 'ton_dev')  # Default to TON Dev

    # Base query
    query = TelegramMessage.query.order_by(TelegramMessage.timestamp.desc()).limit(100)

    # Apply filter
    if filter_type == 'ton_dev':
        query = query.filter_by(is_ton_dev=True)
    # 'all' filter doesn't need additional conditions

    messages = query.all()
    return render_template('index.html', messages=messages, current_filter=filter_type)

@bp.route('/ton-dev')
def ton_dev():
    """View showing only TON Dev messages"""
    return index()

@bp.route('/status')
def status():
    try:
        from config import Config

        message_count = TelegramMessage.query.count()
        channel_count = db.session.query(TelegramMessage.channel_title)\
                                .distinct()\
                                .count()
        latest_message = TelegramMessage.query\
            .order_by(TelegramMessage.timestamp.desc())\
            .first()

        # Check if API credentials are set
        api_id_set = bool(Config.TELEGRAM_API_ID and Config.TELEGRAM_API_ID != '12345')
        api_hash_set = bool(Config.TELEGRAM_API_HASH and Config.TELEGRAM_API_HASH != 'your-api-hash-here')

        return jsonify({
            'status': 'healthy',
            'messages_collected': message_count,
            'channels_monitored': channel_count,
            'latest_message_time': latest_message.timestamp.isoformat() if latest_message else None,
            'telegram_api_configured': api_id_set and api_hash_set
        })
    except Exception as e:
        from app import app
        app.logger.error(f"Error checking status: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500