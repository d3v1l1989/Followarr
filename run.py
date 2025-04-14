#!/usr/bin/env python3
"""
Followarr Bot - Entry Point Script
This script serves as the entry point for the Docker container.
It handles environment setup and starts the bot.
"""

import os
import logging
from dotenv import load_dotenv
from src.bot import FollowarrBot

# Load environment variables
load_dotenv()

# Configure logging
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Required environment variables
required_vars = {
    'DISCORD_BOT_TOKEN': 'Discord Bot Token',
    'DISCORD_CHANNEL_ID': 'Discord Channel ID',
    'TVDB_API_KEY': 'TVDB API Key',
    'PLEX_URL': 'Plex Server URL',
    'PLEX_TOKEN': 'Plex Token'
}

def check_env_vars():
    """Check if all required environment variables are set."""
    missing_vars = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"- {var} ({description})")
    
    if missing_vars:
        logger.error("Missing required environment variables:")
        for var in missing_vars:
            logger.error(var)
        logger.error("\nPlease edit your .env file and add the missing variables.")
        logger.error("You can find the .env file in the same directory as this script.")
        logger.error("After editing, restart the bot.")
        return False
    return True

def main():
    """Main entry point for the bot."""
    if not check_env_vars():
        return

    try:
        # Initialize and run the bot
        bot = FollowarrBot()
        bot.run(os.getenv('DISCORD_BOT_TOKEN'))
    except Exception as e:
        logger.error(f"Error running bot: {str(e)}")
        raise

if __name__ == "__main__":
    main() 