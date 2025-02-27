import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)

# Configure the SQLAlchemy part of the app instance
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.secret_key = os.environ.get("SESSION_SECRET")

# Initialize SQLAlchemy with the application
db.init_app(app)

# Initialize models and tables
def init_db():
    with app.app_context():
        # Import models here to avoid circular imports
        import models
        db.create_all()

# Import routes after db initialization
def init_routes():
    from routes import bp
    app.register_blueprint(bp)

# Initialize everything
init_db()
init_routes()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)