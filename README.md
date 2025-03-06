# TON Message Analytics Platform

A Flask-based analytics platform for monitoring and analyzing Telegram Open Network (TON) community messages. The platform collects and processes messages from Telegram channels, providing real-time insights and statistics.

## Features

- Real-time message collection from Telegram channels
- Message categorization by dialog types (private chats, groups, channels, etc.)
- Daily statistics and message count tracking
- TON-specific message filtering
- Live updates via AJAX
- Dialog type detection and statistics

## Quick Setup on Replit

1. Click the "Run on Replit" button below:

[![Run on Replit](https://replit.com/badge/github/yourusername/ton-analytics)](https://replit.com/new/github/yourusername/ton-analytics)

2. Once the project is imported, you'll need to set up the following secrets in your Replit environment:

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
- PostgreSQL database
- Telegram API credentials

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ton-analytics.git
cd ton-analytics
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
FLASK_ENV=production gunicorn -w 4 -b 0.0.0.0:5000 main:app --timeout 120 --keep-alive 5 --log-level info
```

## Project Structure

```
├── api/                  # API routes and authentication
├── templates/           # HTML templates
├── main.py             # Main application file
├── models.py           # Database models
└── requirements.txt    # Project dependencies
```

## Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

## License

[MIT](https://choosealicense.com/licenses/mit/)
