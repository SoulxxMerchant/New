# NEXUS-Bot

## Overview
This is a Telegram bot built with Python that uses `python-telegram-bot` and `telethon` libraries. It's designed for campaign management through Telegram sessions.

## Project Structure
- `main.py` - Main bot application
- `requirements.txt` - Python dependencies
- `sessions.json` - Stores integrated session strings (created at runtime)

## Required Secrets
The bot requires the following environment variables/secrets to run:
- `BOT_TOKEN` - Telegram Bot Token from @BotFather
- `API_ID` - Telegram API ID from my.telegram.org
- `API_HASH` - Telegram API Hash from my.telegram.org

## Running the Bot
The bot runs as a console application via `python main.py`. It uses polling to receive updates from Telegram.

## Key Features
- Session integration via Telethon
- Campaign management with customizable timers
- Inline keyboard interface for bot interaction
