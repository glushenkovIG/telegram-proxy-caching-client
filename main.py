import logging
import os
from app import app

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    logger.info("Starting simplified Telegram collector and server")
    app.run(host='0.0.0.0', port=5000)