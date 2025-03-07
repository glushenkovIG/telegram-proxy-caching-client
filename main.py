
from flask import render_template, jsonify, request
from app import app, db, logger
from models import TelegramMessage
from collector import ensure_single_collector
import atexit
import os
from datetime import datetime, timedelta
from sqlalchemy import func, desc

@app.route('/')
def index():
    # Get search query if exists
    search_query = request.args.get('search', '')
    
    # Fetch data for combined view
    messages = []
    all_count = 0
    ton_count = 0
    channels = []
    
    # Last 3 days statistics
    three_days_ago = datetime.utcnow() - timedelta(days=3)
    last_3_days_count = 0
    last_3_days_sent = 0
    last_3_days_received = 0
    
    # Leaderboard data
    senders_leaderboard = []
    receivers_leaderboard = []
    
    try:
        # Get total message count
        all_count = db.session.query(TelegramMessage).count()
        
        # Get TON dev message count
        ton_count = db.session.query(TelegramMessage).filter_by(is_ton_dev=True).count()
        
        # Get channel statistics
        channels = db.session.query(
            TelegramMessage.channel_title,
            db.func.count(TelegramMessage.id).label('count'),
            db.func.bool_or(TelegramMessage.is_ton_dev).label('is_ton_dev')
        ).group_by(TelegramMessage.channel_title).order_by(db.desc('count')).all()
        
        # Get 3-day statistics
        last_3_days_count = db.session.query(TelegramMessage).filter(
            TelegramMessage.timestamp >= three_days_ago
        ).count()
        
        last_3_days_sent = db.session.query(TelegramMessage).filter(
            TelegramMessage.timestamp >= three_days_ago,
            TelegramMessage.is_outgoing == True
        ).count()
        
        last_3_days_received = last_3_days_count - last_3_days_sent
        
        # Get senders leaderboard (channels with most outgoing messages in last 3 days)
        senders_leaderboard = db.session.query(
            TelegramMessage.channel_title,
            db.func.count(TelegramMessage.id).label('count')
        ).filter(
            TelegramMessage.timestamp >= three_days_ago,
            TelegramMessage.is_outgoing == True
        ).group_by(TelegramMessage.channel_title).order_by(db.desc('count')).limit(5).all()
        
        # Get receivers leaderboard (channels with most incoming messages in last 3 days)
        receivers_leaderboard = db.session.query(
            TelegramMessage.channel_title,
            db.func.count(TelegramMessage.id).label('count')
        ).filter(
            TelegramMessage.timestamp >= three_days_ago,
            TelegramMessage.is_outgoing == False
        ).group_by(TelegramMessage.channel_title).order_by(db.desc('count')).limit(5).all()
        
        # Get messages with search applied if search query exists
        query = db.session.query(TelegramMessage).order_by(TelegramMessage.timestamp.desc())
        
        if search_query:
            query = query.filter(TelegramMessage.content.ilike(f'%{search_query}%'))
        
        messages = query.limit(100).all()
        
        logger.info(f"Loaded {len(messages)} messages and {len(channels)} channels for display")
    except Exception as e:
        logger.error(f"Error loading data for UI: {str(e)}")
    
    return render_template('index.html', 
                          messages=messages, 
                          all_count=all_count,
                          ton_count=ton_count,
                          channels=channels,
                          last_3_days_count=last_3_days_count,
                          last_3_days_sent=last_3_days_sent,
                          last_3_days_received=last_3_days_received,
                          senders_leaderboard=senders_leaderboard,
                          receivers_leaderboard=receivers_leaderboard,
                          search_query=search_query)

@app.route('/status')
def status():
    return jsonify({"status": "running"})

@app.route('/database')
def database_stats():
    try:
        # Get total message count
        all_count = db.session.query(TelegramMessage).count()
        
        # Get TON dev message count
        ton_count = db.session.query(TelegramMessage).filter_by(is_ton_dev=True).count()
        
        # Get channel statistics
        # Using bool_or instead of max for boolean aggregation
        channels_query = db.session.query(
            TelegramMessage.channel_title,
            db.func.count(TelegramMessage.id).label('count'),
            db.func.bool_or(TelegramMessage.is_ton_dev).label('is_ton_dev')
        ).group_by(TelegramMessage.channel_title).order_by(db.desc('count')).all()
        
        # Get count of accessible channels
        total_accessible_channels = len(channels_query)
        
        return render_template(
            'database.html',
            all_count=all_count,
            ton_count=ton_count,
            channels=channels_query,
            total_accessible_channels=total_accessible_channels
        )
    except Exception as e:
        logger.error(f"Error loading database stats: {str(e)}")
        return f"Error loading database stats: {str(e)}", 500

# Start the collector thread when the app starts
collector_thread = None

def start_collector():
    global collector_thread
    try:
        # Start collector in background
        ensure_single_collector()
        from collector import collector_thread as ct
        collector_thread = ct
        logger.info("Collector thread started successfully")
    except Exception as e:
        logger.error(f"Failed to start collector: {str(e)}")
        # Don't let collector failure prevent web server from starting
        pass

# Register cleanup function
def cleanup():
    if collector_thread and collector_thread.is_alive():
        logger.info("Shutting down collector thread...")

if __name__ == "__main__":
    try:
        # Initialize database first
        with app.app_context():
            db.create_all()

        # Start collector with app context
        with app.app_context():
            start_collector()

        # Register cleanup
        atexit.register(cleanup)

        # Start Flask server
        port = int(os.environ.get("PORT", 5000))
        logger.info(f"Starting Flask server on port {port}")
        app.run(host="0.0.0.0", port=port, debug=True)
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        raise
