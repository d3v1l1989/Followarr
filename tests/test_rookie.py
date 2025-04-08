import os
import sys
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tvdb_client import TVDBClient

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_rookie_episodes():
    try:
        # Load environment variables
        load_dotenv()
        tvdb_api_key = os.getenv('TVDB_API_KEY')
        
        if not tvdb_api_key:
            logger.error("TVDB_API_KEY not found in environment variables")
            return
        
        # Initialize TVDB client
        client = TVDBClient(tvdb_api_key)
        
        # The Rookie show ID
        show_id = 350665
        
        # Get show details first
        show_data = await client._make_request(f"series/{show_id}/extended")
        if show_data:
            logger.info(f"Show name: {show_data.get('name')}")
            logger.info(f"Show status: {show_data.get('status')}")
        
        # Get upcoming episodes
        logger.info(f"Fetching upcoming episodes for The Rookie (ID: {show_id})")
        episodes = await client.get_upcoming_episodes(show_id)
        
        if episodes:
            logger.info(f"Found {len(episodes)} upcoming episodes:")
            for ep in episodes:
                logger.info(f"  - {ep['air_date']}: S{ep['season']:02d}E{ep['episode']:02d} - {ep['name']}")
        else:
            logger.info("No upcoming episodes found")
            
    except Exception as e:
        logger.error(f"Error in test script: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_rookie_episodes()) 