# NEXUS Telegram Bot

A powerful Telegram bot for campaign management and bulk messaging through integrated API sessions.

## Features

- **Session Integration**: Integrate Telegram accounts via Telethon API sessions
- **Campaign Management**: Send bulk messages to groups and channels
- **Customizable Timers**: Set group delay and cycle intervals
- **Admin Controls**: Ban/unban users, set premium status, broadcast messages
- **User Limits**: Daily message limits with premium tier support
- **Inline Keyboard Interface**: Easy-to-use button-based navigation

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/NEXUS-Bot.git
cd NEXUS-Bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your credentials
```

4. Run the bot:
```bash
python main.py
```

## Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | Telegram Bot Token from @BotFather |
| `API_ID` | Telegram API ID from my.telegram.org |
| `API_HASH` | Telegram API Hash from my.telegram.org |
| `ADMIN_IDS` | Comma-separated admin user IDs (e.g., 123456789,987654321) |

## Commands

### General Commands
- `/start` - Show the main menu with inline buttons
- `/stop` - Halt the bulk messaging campaign
- `/setad <message>` - Set the advertisement content
- `/setinterval <seconds>` - Set delay between different groups (min 5s)
- `/setctimer <seconds>` - Set delay between campaign cycles (min 60s)

### Admin Commands
- `/broadcast <message>` - Send message through all integrated sessions
- `/ban <user_id>` - Ban a user from campaigns
- `/unban <user_id>` - Unban a user
- `/setpremium <user_id> true|false` - Set user premium status

## Project Structure

```
NEXUS-Bot/
├── main.py           # Main bot application
├── requirements.txt  # Python dependencies
├── .env.example      # Environment variables template
├── .gitignore        # Git ignore rules
├── LICENSE           # MIT License
└── README.md         # This file
```

## How It Works

The bot uses:
- **python-telegram-bot**: For bot commands and inline keyboards
- **Telethon**: For session integration and bulk messaging
- **Flask**: Web server for uptime monitoring (port 5000)

## License

MIT License - see [LICENSE](LICENSE) for details.
