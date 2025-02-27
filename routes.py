from flask import Blueprint, render_template, request, jsonify
from app import db
from models import TelegramMessage

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    search_query = request.args.get('q')

    query = TelegramMessage.query

    if search_query:
        query = query.filter(TelegramMessage.content.ilike(f'%{search_query}%'))

    pagination = query.order_by(TelegramMessage.timestamp.desc()).paginate(
        page=page, per_page=per_page
    )

    total_messages = TelegramMessage.query.count()

    return render_template('index.html', 
                         messages=pagination.items,
                         pagination=pagination,
                         total_messages=total_messages)

@bp.route('/status')
def status():
    try:
        message_count = TelegramMessage.query.count()
        channel_count = db.session.query(TelegramMessage.channel_title)\
                                .distinct()\
                                .count()
        latest_message = TelegramMessage.query\
            .order_by(TelegramMessage.timestamp.desc())\
            .first()

        return jsonify({
            'status': 'healthy',
            'messages_collected': message_count,
            'channels_monitored': channel_count,
            'latest_message_time': latest_message.timestamp.isoformat() if latest_message else None
        })
    except Exception as e:
        app.logger.error(f"Error checking status: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500