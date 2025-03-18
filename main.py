from flask import render_template, jsonify, request
from app import app, db, logger
from collector import ensure_single_collector, setup_telegram_session
from models import TelegramMessage
from datetime import datetime, timedelta
import atexit
import os
import json
import asyncio
import sys
from telethon import TelegramClient  # Add this import


@app.route('/')
def index():
    session_path = os.path.join(os.environ.get('REPL_HOME', ''),
                                'ton_collector_session.session')
    session_valid = os.path.exists(session_path) and os.path.getsize(
        session_path) > 0

    messages = []
    all_count = 0
    ton_count = 0
    channels = []
    last_3_days_count = 0
    last_7_days_count = 0
    channel_activity = []
    last_7_days_activity = []

    try:
        all_count = db.session.query(TelegramMessage).count()
        ton_count = db.session.query(TelegramMessage).filter_by(
            is_ton_dev=True).count()
        three_days_ago = datetime.utcnow() - timedelta(days=3)
        last_3_days_count = db.session.query(TelegramMessage).filter(
            TelegramMessage.timestamp >= three_days_ago).count()
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        last_7_days_count = db.session.query(TelegramMessage).filter(
            TelegramMessage.timestamp >= seven_days_ago).count()
        channel_activity = db.session.query(
            TelegramMessage.channel_title,
            db.func.count(TelegramMessage.id).filter(
                TelegramMessage.is_outgoing == False).label('incoming'),
            db.func.count(TelegramMessage.id).filter(
                TelegramMessage.is_outgoing == True).label('outgoing'),
            db.func.count(TelegramMessage.id).label('total')).group_by(
                TelegramMessage.channel_title).order_by(
                    db.desc('total')).limit(10).all()
        last_7_days_activity = db.session.query(
            TelegramMessage.channel_title,
            db.func.count(TelegramMessage.id).filter(
                TelegramMessage.is_outgoing == False).label('incoming'),
            db.func.count(TelegramMessage.id).filter(
                TelegramMessage.is_outgoing == True).label('outgoing'),
            db.func.count(TelegramMessage.id).label('total')).filter(
                TelegramMessage.timestamp >= seven_days_ago).group_by(
                    TelegramMessage.channel_title).order_by(
                        db.desc('total')).limit(10).all()
        channels = db.session.query(
            TelegramMessage.channel_title,
            db.func.count(TelegramMessage.id).label('count'),
            db.func.bool_or(
                TelegramMessage.is_ton_dev).label('is_ton_dev')).group_by(
                    TelegramMessage.channel_title).order_by(
                        db.desc('count')).all()
        messages = db.session.query(TelegramMessage).order_by(
            TelegramMessage.timestamp.desc()).limit(100).all()
        logger.info(
            f"Loaded {len(messages)} messages and {len(channels)} channels for display"
        )
    except Exception as e:
        logger.error(f"Error loading data for UI: {str(e)}")

    return render_template('index.html',
                           messages=messages,
                           all_count=all_count,
                           ton_count=ton_count,
                           last_3_days_count=last_3_days_count,
                           last_7_days_count=last_7_days_count,
                           channel_activity=channel_activity,
                           last_7_days_activity=last_7_days_activity,
                           channels=channels,
                           session_valid=session_valid)


@app.route('/status')
def status():
    """Health check endpoint"""
    global collector_thread

    session_path = os.path.join(os.environ.get('REPL_HOME', ''),
                                'ton_collector_session.session')
    session_exists = os.path.exists(session_path) and os.path.getsize(
        session_path) > 0

    thread_running = collector_thread is not None and collector_thread.is_alive(
    )

    if session_exists and thread_running:
        return jsonify({
            "status": "running",
            "collector": "active",
            "session": "valid"
        })
    elif not session_exists:
        start_collector()
        return jsonify({
            "status": "warning",
            "collector": "restarted",
            "session": "invalid"
        })
    elif not thread_running:
        start_collector()
        return jsonify({
            "status": "warning",
            "collector": "restarted",
            "thread": "dead"
        })

    return jsonify({"status": "error", "message": "Unknown state"})


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """Setup page for creating a new Telegram session"""
    session_path = os.path.join(os.environ.get('REPL_HOME', ''),
                                'ton_collector_session.session')
    session_exists = os.path.exists(session_path)
    is_deployment = os.environ.get('REPLIT_DEPLOYMENT', False)

    return render_template('setup.html',
                           session_exists=session_exists,
                           is_deployment=is_deployment)


@app.route('/setup_process', methods=['POST'])
def setup_process():
    """Process the setup form and send verification code"""
    try:
        data = request.get_json()
        phone = data.get('phone')

        if not phone:
            return jsonify({
                "status": "error",
                "message": "Phone number is required"
            }), 400

        os.environ['TELEGRAM_PHONE'] = phone

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(setup_telegram_session())
        loop.close()

        if result:
            return jsonify({
                "status":
                "code_sent",
                "message":
                "Verification code sent to your Telegram app"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to send verification code"
            }), 500

    except Exception as e:
        logger.error(f"Setup process failed: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Setup failed: {str(e)}"
        }), 500


@app.route('/verify_code', methods=['POST'])
def verify_code():
    """Verify the Telegram authentication code"""
    try:
        data = request.get_json()
        code = data.get('code')

        if not code:
            return jsonify({
                "status": "error",
                "message": "No verification code provided"
            }), 400

        os.environ['TELEGRAM_CODE'] = code

        try:
            api_id = int(os.environ.get('TELEGRAM_API_ID'))
            api_hash = os.environ.get('TELEGRAM_API_HASH')
            phone = os.environ.get('TELEGRAM_PHONE')

            if not all([api_id, api_hash, phone]):
                return jsonify({
                    "status": "error",
                    "message": "Missing API credentials"
                }), 400
        except (TypeError, ValueError) as e:
            logger.error(f"Invalid API credentials: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "Invalid API credentials format"
            }), 400

        async def complete_verification():
            session_path = os.path.join(os.environ.get('REPL_HOME', os.getcwd()),
                                      'ton_collector_session.session')

            client = TelegramClient(session_path,
                                  api_id=api_id,
                                  api_hash=api_hash,
                                  system_version="4.16.30-vxCUSTOM",
                                  device_model="Replit Deployment",
                                  app_version="1.0")

            try:
                await client.connect()

                if not await client.is_user_authorized():
                    if not phone.startswith('+'):
                        formatted_phone = '+' + phone
                    else:
                        formatted_phone = phone

                    try:
                        await client.sign_in(formatted_phone, code)
                    except Exception as e:
                        logger.error(f"Sign in error: {str(e)}")
                        return False

                    if await client.is_user_authorized():
                        logger.info("Successfully authenticated with Telegram")
                        await client.disconnect()
                        return True
                    else:
                        logger.error("Failed to authorize after sign-in attempt")
                        await client.disconnect()
                        return False
                else:
                    logger.info("Already authorized with Telegram")
                    await client.disconnect()
                    return True

            except Exception as e:
                logger.error(f"Error in verification process: {str(e)}")
                try:
                    await client.disconnect()
                except:
                    pass
                return False

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(complete_verification())
        loop.close()

        if success:
            start_collector()
            return jsonify({
                "status": "success",
                "message": "Authentication successful"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to verify code with Telegram"
            }), 500

    except Exception as e:
        logger.error(f"Code verification failed: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Verification failed: {str(e)}"
        }), 500


@app.route('/setup_complete')
def setup_complete():
    """Setup completion page"""
    return render_template('setup_complete.html')


@app.route('/restart_collector', methods=['POST'])
def restart_collector():
    """Restart the collector thread"""
    try:
        global collector_thread

        session_path = os.path.join(os.environ.get('REPL_HOME', ''),
                                    'ton_collector_session.session')

        data = request.get_json() or {}
        remove_session = data.get('remove_session', True)

        if remove_session and os.path.exists(session_path):
            logger.info(f"Removing existing session file: {session_path}")
            try:
                os.remove(session_path)
                logger.info("Session file removed successfully")
            except Exception as e:
                logger.warning(f"Could not remove session file: {str(e)}")

        if collector_thread and collector_thread.is_alive():
            logger.info("Stopping existing collector thread...")
            import time
            time.sleep(2)

        import importlib
        import sys
        if 'collector' in sys.modules:
            importlib.reload(sys.modules['collector'])

        collector_thread = None

        success = start_collector()

        if success:
            return jsonify({
                "success": True,
                "message": "Collector restarted successfully"
            })
        else:
            return jsonify({
                "success": False,
                "message": "Failed to start collector thread"
            }), 500
    except Exception as e:
        logger.error(f"Failed to restart collector: {str(e)}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500


collector_thread = None


def start_collector():
    """Initialize and start the collector thread"""
    global collector_thread
    logger.info("Starting collector thread...")
    try:
        if collector_thread and collector_thread.is_alive():
            logger.info("Stopping existing collector thread...")
            import time
            time.sleep(1)

        session_path = os.path.join(os.environ.get('REPL_HOME', ''),
                                    'ton_collector_session.session')
        session_valid = os.path.exists(session_path) and os.path.getsize(
            session_path) > 0

        if not session_valid:
            logger.warning(
                "No valid session found. Collector will start but may not collect messages until setup is complete."
            )

        import importlib
        import sys
        if 'collector' in sys.modules:
            importlib.reload(sys.modules['collector'])

        from collector import ensure_single_collector
        ensure_single_collector()

        from collector import collector_thread as ct
        collector_thread = ct

        if collector_thread and collector_thread.is_alive():
            logger.info("Collector thread started successfully")
            return True
        else:
            logger.error("Collector thread was not started properly")
            return False
    except Exception as e:
        logger.error(f"Failed to start collector: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def cleanup():
    """Cleanup function to be called on shutdown"""
    if collector_thread and collector_thread.is_alive():
        logger.info("Shutting down collector thread...")


if __name__ == "__main__":
    try:
        with app.app_context():
            db.create_all()

        with app.app_context():
            start_collector()

        atexit.register(cleanup)

        port = int(os.environ.get("PORT", 5000))
        logger.info(f"Starting Flask server on port {port}")
        app.run(host="0.0.0.0", port=port, debug=True)
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        raise