from flask import render_template
from app import app, logger
from collector import ensure_single_collector

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == "__main__":
    with app.app_context():
        # Start collector in background
        ensure_single_collector()

    # Start Flask server
    app.run(host="0.0.0.0", port=5000, debug=True)