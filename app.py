import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

# Initialize extensions
db = SQLAlchemy(model_class=Base)
limiter = Limiter(key_func=get_remote_address)

def create_app():
    app = Flask(__name__)

    # Configure database
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-secret-key')

    # Initialize extensions
    db.init_app(app)
    limiter.init_app(app)

    with app.app_context():
        # Make sure to import the models here or their tables won't be created
        import models  # noqa: F401

        db.create_all()
        logger.info("Database tables created successfully")

        # Register blueprints
        from routes import bp as main_blueprint
        from api import api as api_blueprint
        app.register_blueprint(main_blueprint)
        app.register_blueprint(api_blueprint, url_prefix='/api')

    return app