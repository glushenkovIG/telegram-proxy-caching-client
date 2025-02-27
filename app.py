import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Create Flask app
app = Flask(__name__)

# Configure database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Initialize database
db = SQLAlchemy(app)

with app.app_context():
    # Make sure to import the models here or their tables won't be created
    import models  # noqa: F401

    db.create_all()

# Register blueprints after models are created
from routes import bp
app.register_blueprint(bp)

if __name__ == "__main__":
    try:
        # First try port 5000
        app.run(host='0.0.0.0', port=5000, debug=False)
    except OSError as e:
        if "Address already in use" in str(e):
            print("Port 5000 is in use, trying port 8080...")
            # If port 5000 is busy, use 8080
            app.run(host='0.0.0.0', port=8080, debug=False)
        else:
            raise