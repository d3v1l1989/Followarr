import asyncio
import os
import sys
import logging
import json
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tvdb_client import TVDBClient

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_rookie_episodes():
    try:
        # Try to load .env file if python-dotenv is available
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            logger.warning("python-dotenv not installed, using environment variables as is")
        
        # Check if we have the TVDB API key
        tvdb_api_key = os.getenv('TVDB_API_KEY')
        if not tvdb_api_key:
            print("Error: TVDB_API_KEY not found in environment variables or .env file")
            return
            
        client = TVDBClient()
        
        # The Rookie show ID
        show_id = 350665
        
        print("\nFetching episodes for The Rookie (ID: 350665)...")
        episodes = await client.get_upcoming_episodes(show_id)
        
        if not episodes:
            print("\nNo upcoming episodes found!")
            return
            
        print(f"\nFound {len(episodes)} upcoming episodes:")
        for ep in episodes:
            air_date = ep['air_date']
            season = ep.get('season', 0)
            episode = ep.get('episode', 0)
            name = ep.get('name', 'Unknown')
            print(f"- {air_date}: S{season:02d}E{episode:02d} - {name}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(test_rookie_episodes()) 