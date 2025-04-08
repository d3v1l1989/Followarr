import asyncio
from src.tvdb_client import TVDBClient
import os
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.DEBUG)

async def test_rookie_episodes():
    load_dotenv()
    client = TVDBClient()
    
    # The Rookie show ID
    show_id = 350665
    
    episodes = await client.get_upcoming_episodes(show_id)
    print(f"\nFound {len(episodes)} upcoming episodes for The Rookie:")
    for ep in episodes:
        print(f"- {ep['air_date']}: S{ep['season']}E{ep['episode']} - {ep['name']}")

if __name__ == "__main__":
    asyncio.run(test_rookie_episodes()) 