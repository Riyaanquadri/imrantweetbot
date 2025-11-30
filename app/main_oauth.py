"""
Twitter bot with OAuth2 user context authentication.

This version uses OAuth2 bearer token for authentication via direct HTTP requests
instead of Tweepy's OAuth1 client (Tweepy v4 requires consumer key/secret for initialization).

Uses OAuth2ClientAdapter to make OAuth2Client compatible with the existing scheduler.
"""
import logging
import signal
import sys
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from app.config import Config
from app.logger import logger
from app.scheduler import BotScheduler
from app.quota import QuotaManager
from app.src.db import init_db
from app.oauth2_client import OAuth2Client
from app.oauth2_adapter import OAuth2ClientAdapter

def signal_handler(sig, frame):
    """Handle graceful shutdown."""
    logger.info('Received shutdown signal, stopping scheduler...')
    sys.exit(0)

def main():
    """Initialize and run the bot with OAuth2 authentication."""
    
    # Initialize database
    init_db()
    
    logger.info('Starting Crypto AI Twitter Bot (OAuth2 mode)')
    logger.info(f'Bot handle: {Config.BOT_HANDLE}')
    logger.info(f'Project keywords: {Config.PROJECT_KEYWORDS}')
    logger.info(f'DRY_RUN mode: {Config.DRY_RUN}')
    
    # Validate OAuth2 credentials
    if not Config.OAUTH2_USER_ACCESS_TOKEN:
        logger.error('OAUTH2_USER_ACCESS_TOKEN not set in .env')
        logger.error('Run: .venv/bin/python3 app/oauth_pkce.py && oauth_callback.py to get tokens')
        sys.exit(1)
    
    # Create OAuth2 client
    try:
        oauth2_client = OAuth2Client(Config.OAUTH2_USER_ACCESS_TOKEN)
        me = oauth2_client.get_me()
        logger.info(f'✓ OAuth2 authentication successful: @{me["data"]["username"]}')
    except Exception as e:
        logger.error(f'✗ OAuth2 authentication failed: {e}')
        sys.exit(1)
    
    # Initialize quota manager
    quota_manager = QuotaManager()
    
    # Create adapter to make OAuth2Client compatible with scheduler
    client = OAuth2ClientAdapter(oauth2_client)
    logger.info('Using OAuth2 client for all operations')
    
    # Initialize scheduler with OAuth2 adapter
    scheduler = BotScheduler(
        twitter_client=client,
        quota_manager=quota_manager
    )
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        logger.info('Scheduler started')
        scheduler.start()
        # Keep running
        while True:
            signal.pause()
    except KeyboardInterrupt:
        logger.info('Bot interrupted')
    finally:
        scheduler.shutdown()
        logger.info('Bot stopped')


if __name__ == '__main__':
    main()
