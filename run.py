#!/usr/bin/env python3
"""
Followarr Bot - Entry Point Script
This script serves as the entry point for the Docker container.
It handles environment setup and starts the bot.
"""

import os
import sys
import logging
import asyncio
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/logs/followarr.log')
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Check for required environment variables
required_vars = [
    'DISCORD_BOT_TOKEN',
    'TVDB_API_KEY',
    'TAUTULLI_URL',
    'TAUTULLI_API_KEY'
]

missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
    logger.error("Please check your .env file and ensure all required variables are set.")
    sys.exit(1)

# Import the bot
try:
    from src.bot import FollowarrBot
except ImportError as e:
    logger.error(f"Failed to import FollowarrBot: {e}")
    sys.exit(1)

async def main():
    """Main function to run the bot"""
    try:
        logger.info("Starting Followarr Bot...")
        bot = FollowarrBot()
        await bot.start(os.getenv('DISCORD_BOT_TOKEN'))
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 