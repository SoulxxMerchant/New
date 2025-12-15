import os
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    """Serves a simple status page for uptime monitoring."""
    return "🤖 Nexus Telegram Bot is Running and Polling."

@app.route('/health')
def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "NEXUS Bot"}

def run_flask_app():
    """Starts the Flask server."""
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
