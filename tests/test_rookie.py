import os
import sys
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tvdb_client import TVDBClient

# Set up logging with a simpler format
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
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
            logger.info(f"Show: {show_data.get('name')} ({show_data.get('status')})")
        
        # Get upcoming episodes
        episodes = await client.get_upcoming_episodes(show_id)
        
        if episodes:
            logger.info(f"\nUpcoming episodes ({len(episodes)}):")
            for ep in episodes:
                logger.info(f"S{ep['season']:02d}E{ep['episode']:02d} - {ep['name']} ({ep['air_date']})")
        else:
            logger.info("No upcoming episodes found")
            
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_rookie_episodes()) 