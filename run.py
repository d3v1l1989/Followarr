#!/usr/bin/env python3
"""
Followarr Bot - Entry Point Script
This script serves as the entry point for the Docker container.
It handles environment setup and starts the bot.
"""

import os
import sys
import asyncio
import logging
from dotenv import load_dotenv
from src.bot import FollowarrBot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def validate_env():
    """Validate required environment variables."""
    required_vars = {
        'DISCORD_BOT_TOKEN': 'Discord Bot Token (from Discord Developer Portal)',
        'DISCORD_CHANNEL_ID': 'Discord Channel ID',
        'TVDB_API_KEY': 'TVDB API Key',
        'TAUTULLI_URL': 'Tautulli Server URL',
        'TAUTULLI_API_KEY': 'Tautulli API Key'
    }
    
    missing_vars = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"{var} ({description})")
    
    if missing_vars:
        logger.error("Missing required environment variables:")
        for var in missing_vars:
            logger.error(f"  - {var}")
        logger.error("\nPlease edit your .env file and add the missing variables.")
        logger.error("You can find the .env file in the same directory as this script.")
        logger.error("After editing, restart the bot.")
        return False
    return True

async def main():
    """Main function to run the bot."""
    try:
        # Load environment variables
        load_dotenv()
        
        # Validate environment variables
        if not validate_env():
            sys.exit(1)
            
        logger.info("Starting Followarr Bot...")
        
        # Initialize and start the bot
        bot = FollowarrBot()
        await bot.start(os.getenv('DISCORD_BOT_TOKEN'))
        
    except Exception as e:
        logger.error(f"Error starting bot: {str(e)}")
        if "Improper token has been passed" in str(e):
            logger.error("\nThe Discord bot token appears to be invalid.")
            logger.error("Please check your .env file and ensure DISCORD_BOT_TOKEN is set correctly.")
            logger.error("You can find your bot token in the Discord Developer Portal under your application's Bot section.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 