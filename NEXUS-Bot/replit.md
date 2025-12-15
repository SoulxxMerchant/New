# NEXUS Telegram Bot

## Overview
A Telegram bot for campaign management and bulk messaging using python-telegram-bot and Telethon libraries. Includes a Flask web server for uptime monitoring.

## Project Structure
- `main.py` - Main bot application with Flask server and Telegram handlers
- `requirements.txt` - Python dependencies (telethon, python-telegram-bot, flask)
- `sessions.json` - Stores integrated Telethon session strings
- `user_data.json` - Stores user data, limits, and ban status

## Required Secrets
The bot requires these environment variables:
- `BOT_TOKEN` - Telegram Bot Token from @BotFather
- `API_ID` - Telegram API ID from my.telegram.org
- `API_HASH` - Telegram API Hash from my.telegram.org
- `ADMIN_IDS` - Comma-separated list of admin Telegram user IDs

## Running the Bot
The workflow runs `cd NEXUS-Bot && python main.py` which:
1. Starts Flask web server on port 5000
2. Initializes Telegram bot with polling
3. Loads existing sessions and user data

## Key Features
- Session integration via Telethon StringSession
- Campaign management with customizable group and cycle timers
- Inline keyboard interface for all bot interactions
- Admin commands for user management (ban, premium, broadcast)
- Daily message limits (150 standard, 1500 premium)

## User Preferences
- Bot uses inline keyboard buttons for navigation
- All configurations done via /set commands or inline buttons
