from flask import render_template, request, jsonify
from app import app, db
from models import TelegramMessage

@app.route('/')
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
    
    return render_template('index.html', 
                         messages=pagination.items,
                         pagination=pagination)

@app.route('/status')
def status():
    try:
        message_count = TelegramMessage.query.count()
        channel_count = db.session.query(TelegramMessage.channel_title)\
                                .distinct()\
                                .count()
        return jsonify({
            'status': 'healthy',
            'messages_collected': message_count,
            'channels_monitored': channel_count
        })
    except Exception as e:
        app.logger.error(f"Error checking status: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500
