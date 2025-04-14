import logging
from typing import Optional, Dict, List
from plexapi.server import PlexServer
from plexapi.video import Show, Episode
import aiohttp
import asyncio
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class PlexClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.plex = PlexServer(base_url, token)
        
    async def get_recently_added_episodes(self, hours: int = 24) -> List[Dict]:
        """
        Get recently added episodes from Plex within the specified time window.
        
        Args:
            hours (int): Number of hours to look back for recently added content
            
        Returns:
            List[Dict]: List of episode information dictionaries
        """
        try:
            # Get all recently added items
            recently_added = self.plex.library.recentlyAdded()
            
            # Filter for TV shows and episodes added within the time window
            cutoff_time = datetime.now() - timedelta(hours=hours)
            episodes = []
            
            for item in recently_added:
                if isinstance(item, Episode):
                    # Check if the episode was added within our time window
                    if item.addedAt >= cutoff_time:
                        show = item.show()
                        episodes.append({
                            'show_name': show.title,
                            'season_num': item.seasonNumber,
                            'episode_num': item.index,
                            'episode_title': item.title,
                            'summary': item.summary,
                            'air_date': item.originallyAvailableAt.isoformat() if item.originallyAvailableAt else None,
                            'tvdb_id': self._get_tvdb_id(show)
                        })
            
            return episodes
            
        except Exception as e:
            logger.error(f"Error getting recently added episodes: {str(e)}")
            return []
    
    def _get_tvdb_id(self, show: Show) -> Optional[int]:
        """
        Extract TVDB ID from a Plex show object.
        
        Args:
            show (Show): Plex show object
            
        Returns:
            Optional[int]: TVDB ID if found, None otherwise
        """
        try:
            # Try to get the TVDB ID from the show's external IDs
            for guid in show.guids:
                if 'tvdb' in guid.id.lower():
                    # Extract the ID from the GUID (format: tvdb://123456)
                    return int(guid.id.split('//')[-1])
            return None
        except Exception as e:
            logger.error(f"Error getting TVDB ID for show {show.title}: {str(e)}")
            return None
    
    async def get_show_by_tvdb_id(self, tvdb_id: int) -> Optional[Show]:
        """
        Find a show in Plex by its TVDB ID.
        
        Args:
            tvdb_id (int): TVDB ID of the show
            
        Returns:
            Optional[Show]: Plex show object if found, None otherwise
        """
        try:
            # Search all TV shows in the library
            for show in self.plex.library.section('TV Shows').all():
                if self._get_tvdb_id(show) == tvdb_id:
                    return show
            return None
        except Exception as e:
            logger.error(f"Error finding show with TVDB ID {tvdb_id}: {str(e)}")
            return None 