
# Telegram Cache Proxy

A self-hosted Flask-based proxy for caching Telegram messages. This application collects and processes messages from Telegram channels, providing cached access and basic analytics.

## Features

- Real-time message collection from Telegram channels
- Local caching of messages for fast access
- Message categorization by dialog types (private chats, groups, channels, etc.)
- Message tagging and filtering
- Live updates via automatic page refresh
- Dialog type detection and statistics

## Quick Setup on Replit

1. Clone this repository

2. Set up the following secrets in your Replit environment:

```
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
SESSION_SECRET=your_session_secret
```

3. Get your Telegram API credentials:
   - Visit https://my.telegram.org/auth
   - Go to 'API development tools'
   - Create a new application
   - Copy the `api_id` and `api_hash`

4. Hit the "Run" button on Replit!

## Manual Setup

### Prerequisites

- Python 3.11+
- SQLite or PostgreSQL database
- Telegram API credentials

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/telegram-cache-proxy.git
cd telegram-cache-proxy
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
export TELEGRAM_API_ID=your_api_id
export TELEGRAM_API_HASH=your_api_hash
export SESSION_SECRET=your_session_secret
export DATABASE_URL=postgresql://user:password@localhost/dbname
```

4. Run in production mode:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 main:app --timeout 120 --keep-alive 5 --log-level info
```

## Project Structure

```
├── api/                  # API routes and authentication
├── templates/            # HTML templates
├── main.py               # Main application file
├── models.py             # Database models
├── collector.py          # Message collection logic
└── requirements.txt      # Project dependencies
```

## License

[MIT](https://choosealicense.com/licenses/mit/)
