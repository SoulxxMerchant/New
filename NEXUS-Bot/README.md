# NEXUS Telegram Bot

A powerful Telegram bot for campaign management and bulk messaging through integrated API sessions.

## Features

- **Session Integration**: Integrate Telegram accounts via Telethon API sessions
- **Campaign Management**: Send bulk messages to groups and channels
- **Customizable Timers**: Set group delay and cycle intervals
- **Admin Controls**: Ban/unban users, set premium status, broadcast messages
- **User Limits**: Daily message limits with premium tier support
- **Inline Keyboard Interface**: Easy-to-use button-based navigation

## Required Environment Variables

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
├── sessions.json     # Integrated session strings
├── user_data.json    # User data and limits
└── README.md         # This file
```

## Running the Bot

The bot runs with a Flask web server on port 5000 for uptime monitoring, while polling Telegram for updates.

```bash
python main.py
```

## License

All rights reserved.
