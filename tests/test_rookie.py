import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

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
        load_dotenv()
        client = TVDBClient()
        
        # The Rookie show ID
        show_id = 350665
        
        print("\nFetching episodes for The Rookie (ID: 350665)...")
        episodes = await client.get_upcoming_episodes(show_id)
        
        print(f"\nFound {len(episodes)} upcoming episodes:")
        for ep in episodes:
            print(f"- {ep['air_date']}: S{ep['season']:02d}E{ep['episode']:02d} - {ep['name']}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(test_rookie_episodes()) 