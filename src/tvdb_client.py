import aiohttp
import os
import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import traceback
import json
from dotenv import load_dotenv
import requests
import time

# Load env vars and setup logging
load_dotenv()
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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
        if isinstance(self.id, str):
            self.id = int(self.id)
        
        if not self.image_url and self.image:
            image_path = self.image if self.image.startswith('/') else f"/{self.image}"
            self.image_url = f"https://www.thetvdb.com{image_path}"

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'TVShow':
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

        if data.get('image'):
            if data['image'].startswith('http'):
                show_data['image_url'] = data['image']
            else:
                image_path = data['image'] if data['image'].startswith('/') else f"/{data['image']}"
                show_data['image_url'] = f"https://artworks.thetvdb.com{image_path}"
        
        elif data.get('artworks'):
            for artwork in data['artworks']:
                if artwork.get('type') == 'poster' and artwork.get('image'):
                    if artwork['image'].startswith('http'):
                        show_data['image_url'] = artwork['image']
                    else:
                        image_path = artwork['image'] if artwork['image'].startswith('/') else f"/{artwork['image']}"
                        show_data['image_url'] = f"https://artworks.thetvdb.com{image_path}"
                    break
        
        show_data = {k: v for k, v in show_data.items() if v is not None}
        return cls(**show_data)

class TVDBClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api4.thetvdb.com/v4"
        self.token = None
        self.token_expiry = 0
        
    def _get_token(self) -> str:
        """Get or refresh the TVDB API token."""
        current_time = time.time()
        if self.token and current_time < self.token_expiry:
            return self.token
            
        try:
            response = requests.post(
                f"{self.base_url}/login",
                json={"apikey": self.api_key}
            )
            response.raise_for_status()
            data = response.json()
            self.token = data['data']['token']
            # Set token expiry to 23 hours from now (TVDB tokens last 24 hours)
            self.token_expiry = current_time + (23 * 60 * 60)
            return self.token
        except Exception as e:
            logger.error(f"Error getting TVDB token: {str(e)}")
            raise
            
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make a request to the TVDB API with proper error handling."""
        try:
            token = self._get_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = requests.request(
                method,
                f"{self.base_url}/{endpoint}",
                headers=headers,
                **kwargs
            )
            
            if response.status_code == 404:
                logger.warning(f"TVDB API 404: {endpoint} not found")
                return None
                
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"TVDB API 404: {endpoint} not found")
                return None
            logger.error(f"TVDB API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error making TVDB request: {str(e)}")
            raise
            
    def search_show(self, query: str) -> Optional[Dict[str, Any]]:
        """Search for a TV show by name."""
        try:
            data = self._make_request("GET", f"search?query={query}")
            if not data or not data.get('data'):
                logger.warning(f"No results found for query: {query}")
                return None
                
            # Return the first result
            return data['data'][0]
        except Exception as e:
            logger.error(f"Error searching for show: {str(e)}")
            return None
            
    def get_show_details(self, show_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed information about a TV show."""
        try:
            data = self._make_request("GET", f"series/{show_id}")
            if not data or not data.get('data'):
                logger.warning(f"No details found for show ID: {show_id}")
                return None
                
            return data['data']
        except Exception as e:
            logger.error(f"Error getting show details: {str(e)}")
            return None
            
    def get_episode_details(self, episode_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed information about an episode."""
        try:
            data = self._make_request("GET", f"episodes/{episode_id}")
            if not data or not data.get('data'):
                logger.warning(f"No details found for episode ID: {episode_id}")
                return None
                
            return data['data']
        except Exception as e:
            logger.error(f"Error getting episode details: {str(e)}")
            return None

    async def search_series(self, query: str) -> List[Dict]:
        try:
            response = await self._make_request('GET', 'search', params={'query': query})
            if response and 'data' in response:
                return response['data']
            return []
        except Exception as e:
            logger.error(f"Error searching series: {e}")
            return []

    async def get_series_extended(self, series_id: int) -> Optional[Dict]:
        try:
            response = await self._make_request('GET', f'series/{series_id}/extended')
            if response and 'data' in response:
                return response['data']
            return None
        except Exception as e:
            logger.error(f"Error getting series extended info: {e}")
            return None

    async def search_show(self, show_name: str) -> Optional[TVShow]:
        try:
            results = await self.search_series(show_name)
            if not results:
                return None
            
            show = results[0]
            show_id = show.get('tvdb_id') or show.get('id')
            if not show_id:
                return None
            
            show_details = await self.get_series_extended(show_id)
            if not show_details:
                return None
            
            return TVShow.from_api_response(show_details)
            
        except Exception as e:
            logger.error(f"Error searching for show: {e}")
            return None

    async def get_series(self, series_id: str) -> Optional[Dict]:
        try:
            response = await self._make_request('GET', f'series/{series_id}')
            if response and 'data' in response:
                return response['data']
            return None
        except Exception as e:
            logger.error(f"Error getting series: {e}")
            return None

    async def get_episodes(self, series_id: int) -> List[Dict]:
        """Get all episodes for a series using TVDB API v4."""
        try:
            # First check if series exists
            series_response = await self._make_request('GET', f"series/{series_id}")
            logger.info(f"Series response for {series_id}: {json.dumps(series_response, indent=2)}")
            
            if not series_response or "data" not in series_response:
                logger.error(f"Series {series_id} not found")
                return []

            episodes = []
            page = 0  # Start from page 0
            while True:
                # TVDB API v4 parameters
                params = {
                    "page": page,
                    "limit": 100,  # Maximum allowed by API
                    "sort": "aired",  # Sort by air date
                    "order": "asc",   # Ascending order
                    "airedSeason": "all",  # Get all seasons
                    "include": "translations"  # Include episode translations
                }
                
                # TVDB API v4 endpoint for episodes
                response = await self._make_request('GET', f"series/{series_id}/episodes/default", params=params)
                logger.info(f"Episodes response for {series_id} page {page}: {json.dumps(response, indent=2)}")
                
                if not response:
                    logger.error(f"No episodes found for series {series_id}")
                    return []

                if response.get("status") == "error":
                    logger.error(f"TVDB API error for series {series_id}: {response.get('message')}")
                    return []

                # Check if we have episodes in the response
                if "data" in response and "episodes" in response["data"]:
                    page_episodes = response["data"]["episodes"]
                    if not page_episodes:
                        logger.info(f"No more episodes found for series {series_id} on page {page}")
                        break
                    episodes.extend(page_episodes)
                    
                    # Check if there are more pages
                    if "links" in response and "next" in response["links"] and response["links"]["next"]:
                        page += 1
                    else:
                        break
                else:
                    logger.error(f"Invalid response format for series {series_id}: {json.dumps(response, indent=2)}")
                    return []

            logger.info(f"Found {len(episodes)} episodes for series {series_id}")
            return episodes

        except Exception as e:
            logger.error(f"Error getting episodes for series {series_id}: {str(e)}")
            logger.error(traceback.format_exc())
            return []

    async def get_upcoming_episodes(self, series_id: str) -> List[Dict]:
        """Get upcoming episodes for a series within the next 3 months."""
        try:
            # Get all episodes for the series
            episodes = await self.get_episodes(series_id)
            if not episodes:
                logger.error(f"No episodes found for series {series_id}")
                return []

            now = datetime.now(timezone.utc)
            three_months_later = now + timedelta(days=90)
            upcoming_episodes = []

            for episode in episodes:
                try:
                    # TVDB API v4 uses 'aired' instead of 'air_date'
                    air_date_str = episode.get('aired')
                    if not air_date_str:
                        continue

                    # Handle different date formats
                    if 'T' in air_date_str:
                        # ISO format with time
                        air_date_str = air_date_str.replace('Z', '+00:00')
                        air_date = datetime.fromisoformat(air_date_str)
                    else:
                        # Date-only format
                        air_date = datetime.strptime(air_date_str, "%Y-%m-%d")
                        air_date = air_date.replace(tzinfo=timezone.utc)

                    # Check if episode is in the future and within 3 months
                    if now < air_date <= three_months_later:
                        upcoming_episodes.append(episode)

                except (ValueError, TypeError) as e:
                    logger.error(f"Error processing episode date for series {series_id}: {e}")
                    continue

            # Sort episodes by air date
            upcoming_episodes.sort(key=lambda x: x.get('aired', ''))
            
            logger.info(f"Found {len(upcoming_episodes)} upcoming episodes for series {series_id}")
            return upcoming_episodes

        except Exception as e:
            logger.error(f"Error getting upcoming episodes for series {series_id}: {str(e)}")
            return [] 