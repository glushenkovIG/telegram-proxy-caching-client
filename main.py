
import logging
import threading
import asyncio
from app import app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_collector():
    """Run the collector in a separate thread"""
    import asyncio
    from collector import main
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())

if __name__ == "__main__":
    logger.info("Starting Telegram collector and Flask server")
    
    # Start collector in a separate thread
    collector_thread = threading.Thread(target=run_collector)
    collector_thread.daemon = True
    collector_thread.start()
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000)
