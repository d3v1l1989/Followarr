import aiohttp
import os
import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from datetime import datetime, timezone
import traceback
import json

logger = logging.getLogger(__name__)

@dataclass
class TVShow:
    id: int
    name: str
    overview: Optional[str] = None
    status: Optional[Dict[str, Any]] = None
    first_aired: Optional[str] = None
    network: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None
    image: Optional[str] = None
    slug: Optional[str] = None
    tvdb_id: Optional[int] = None
    artworks: Optional[List[Dict[str, Any]]] = None
    aliases: Optional[List[str]] = None
    original_language: Optional[str] = None
    original_network: Optional[Dict[str, Any]] = None
    year: Optional[str] = None
    remote_ids: Optional[List[Dict[str, Any]]] = None

    def __post_init__(self):
        # Convert string ID to int if necessary
        if isinstance(self.id, str):
            self.id = int(self.id)
        
        # Handle image URL
        if not self.image_url and self.image:
            # Make sure the image path starts with a slash
            image_path = self.image if self.image.startswith('/') else f"/{self.image}"
            self.image_url = f"https://www.thetvdb.com{image_path}"

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'TVShow':
        """Create a TVShow instance from API response data"""
        logger.info("Processing show data from API response")
        
        # Log the image-related data we receive
        logger.info(f"Image data received - image: {data.get('image')}")
        logger.info(f"Artwork data received: {data.get('artworks', [])[:2]}")
        
        show_data = {
            'id': data.get('id'),
            'name': data.get('name'),
            'overview': data.get('overview'),
            'status': data.get('status'),
            'first_aired': data.get('firstAired'),
            'network': data.get('network'),
            'image': None,
            'image_url': None
        }

        # Handle image URL - check if it's already a full URL
        if data.get('image'):
            if data['image'].startswith('http'):
                show_data['image_url'] = data['image']
                logger.info(f"Using provided full image URL: {show_data['image_url']}")
            else:
                image_path = data['image'] if data['image'].startswith('/') else f"/{data['image']}"
                show_data['image_url'] = f"https://artworks.thetvdb.com{image_path}"
                logger.info(f"Using constructed image URL: {show_data['image_url']}")
        
        # If no main image, try artworks
        elif data.get('artworks'):
            logger.info(f"No main image, checking {len(data['artworks'])} artworks")
            for artwork in data['artworks']:
                if artwork.get('type') == 'poster' and artwork.get('image'):
                    if artwork['image'].startswith('http'):
                        show_data['image_url'] = artwork['image']
                        logger.info(f"Using provided full artwork URL: {show_data['image_url']}")
                    else:
                        image_path = artwork['image'] if artwork['image'].startswith('/') else f"/{artwork['image']}"
                        show_data['image_url'] = f"https://artworks.thetvdb.com{image_path}"
                        logger.info(f"Using constructed artwork URL: {show_data['image_url']}")
                    break
        
        # Filter out None values
        show_data = {k: v for k, v in show_data.items() if v is not None}
        logger.info(f"Final image URL set to: {show_data.get('image_url', 'None')}")
        return cls(**show_data)

class TVDBClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('TVDB_API_KEY')
        if not self.api_key:
            raise ValueError("TVDB API key not provided and not found in environment variables")
        self.token = None
        self.base_url = 'https://api4.thetvdb.com/v4'
        logger.info("Initialized TVDB Client")

    async def _get_token(self) -> str:
        """Get authentication token from TVDB API."""
        if self.token:
            return self.token

        logger.info("Getting new TVDB token")
        try:
            response = await self._make_request('POST', 'login', json={"apikey": self.api_key})
            if response and 'data' in response and 'token' in response['data']:
                self.token = response['data']['token']
                logger.info("Successfully obtained TVDB token")
                return self.token
            logger.error("Failed to get TVDB token: Invalid response format")
            raise Exception("Failed to get TVDB token: Invalid response format")
        except Exception as e:
            logger.error(f"Error in _get_token: {str(e)}")
            raise

    async def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make an authenticated request to the TVDB API."""
        try:
            token = await self._get_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"Making TVDB API request: {method} {endpoint} with params: {params}")
            
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method,
                    f"{self.base_url}/{endpoint}",
                    headers=headers,
                    params=params
                ) as response:
                    if response.status == 401:
                        # Token expired, get a new one and retry
                        self.token = None
                        return await self._make_request(method, endpoint, params)
                    
                    response_data = await response.json()
                    logger.debug(f"TVDB API response: {response_data}")
                    return response_data
                    
        except Exception as e:
            logger.error(f"Error making TVDB API request: {e}")
            logger.error(traceback.format_exc())
            return None

    async def search_series(self, query: str) -> List[Dict]:
        """Search for TV series by name."""
        try:
            response = await self._make_request('GET', 'search', params={'query': query})
            if response and 'data' in response:
                return response['data']
            return []
        except Exception as e:
            logger.error(f"Error searching series: {e}")
            return []

    async def get_series_extended(self, series_id: int) -> Optional[Dict]:
        """Get extended information for a TV series."""
        try:
            response = await self._make_request('GET', f'series/{series_id}/extended')
            if response and 'data' in response:
                return response['data']
            return None
        except Exception as e:
            logger.error(f"Error getting series extended info: {e}")
            return None

    async def search_show(self, show_name: str) -> Optional[TVShow]:
        """Search for a TV show by name."""
        try:
            results = await self.search_series(show_name)
            if not results:
                return None
            
            # Get the first result
            show = results[0]
            show_id = show.get('tvdb_id') or show.get('id')
            if not show_id:
                return None
            
            # Get extended details
            show_details = await self.get_series_extended(show_id)
            if not show_details:
                return None
            
            return TVShow.from_api_response(show_details)
            
        except Exception as e:
            logger.error(f"Error searching for show: {e}")
            return None

    async def get_show_details(self, show_id: int) -> Optional[Dict]:
        """Get basic details for a TV show."""
        try:
            response = await self._make_request('GET', f'series/{show_id}')
            if response and 'data' in response:
                return response['data']
            return None
        except Exception as e:
            logger.error(f"Error getting show details: {e}")
            return None

    async def get_episode_details(self, episode_id: int) -> Optional[Dict]:
        """Get details for a specific episode."""
        try:
            response = await self._make_request('GET', f'episodes/{episode_id}/extended')
            if response and 'data' in response:
                return response['data']
            return None
        except Exception as e:
            logger.error(f"Error getting episode details: {e}")
            return None

    async def get_upcoming_episodes(self, show_id: int) -> List[Dict[str, Any]]:
        """Get upcoming episodes for a show."""
        try:
            # First get the show details to verify it exists
            show_data = await self._make_request('GET', f'series/{show_id}/extended')
            if not show_data or 'data' not in show_data:
                logger.error(f"Show with ID {show_id} not found")
                return []

            logger.info(f"Fetching upcoming episodes for show {show_id}")
            
            # Get all episodes
            response = await self._make_request('GET', f'series/{show_id}/episodes/official')
            logger.info(f"Raw episodes response: {response}")
            
            if not response or 'data' not in response or 'episodes' not in response['data']:
                logger.error("No episodes found in response")
                return []
            
            episodes = response['data']['episodes']
            logger.info(f"Found {len(episodes)} total episodes")
            
            # Get current date in UTC
            now = datetime.now(timezone.utc)
            
            # Filter for upcoming episodes
            upcoming_episodes = []
            for episode in episodes:
                try:
                    # Parse air date
                    air_date = datetime.fromisoformat(episode['aired'].replace('Z', '+00:00'))
                    
                    # Only include episodes that haven't aired yet
                    if air_date > now:
                        upcoming_episodes.append({
                            'id': episode['id'],
                            'name': episode['name'],
                            'air_date': air_date.isoformat(),
                            'season_number': episode['seasonNumber'],
                            'episode_number': episode['number'],
                            'overview': episode.get('overview', '')
                        })
                except (KeyError, ValueError) as e:
                    logger.warning(f"Error processing episode: {e}")
                    continue
            
            # Sort by air date
            upcoming_episodes.sort(key=lambda x: x['air_date'])
            
            logger.info(f"Found {len(upcoming_episodes)} upcoming episodes")
            return upcoming_episodes
            
        except Exception as e:
            logger.error(f"Error getting upcoming episodes: {e}")
            return [] 