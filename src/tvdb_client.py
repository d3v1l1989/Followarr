import aiohttp
import os
import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import traceback
import json
from dotenv import load_dotenv

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
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('TVDB_API_KEY')
        if not self.api_key:
            raise ValueError("TVDB API key not provided and not found in environment variables")
        self.token = None
        self.base_url = 'https://api4.thetvdb.com/v4'

    async def _get_token(self) -> str:
        if self.token:
            return self.token

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/login",
                    json={"apikey": self.api_key}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and 'data' in data and 'token' in data['data']:
                            self.token = data['data']['token']
                            return self.token
                    
                    response_text = await response.text()
                    logger.error(f"Failed to get TVDB token. Status: {response.status}, Response: {response_text}")
                    raise Exception(f"Failed to get TVDB token: {response.status}")
        except Exception as e:
            logger.error(f"Error in _get_token: {str(e)}")
            raise

    async def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, json: Optional[Dict] = None) -> Dict:
        try:
            token = await self._get_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method,
                    f"{self.base_url}/{endpoint}",
                    headers=headers,
                    params=params,
                    json=json
                ) as response:
                    if response.status == 401:
                        self.token = None
                        return await self._make_request(method, endpoint, params, json)
                    
                    response_data = await response.json()
                    return response_data
                    
        except Exception as e:
            logger.error(f"Error making TVDB API request: {e}")
            logger.error(traceback.format_exc())
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

    async def get_show_details(self, show_id: int) -> Optional[Dict]:
        try:
            response = await self._make_request('GET', f'series/{show_id}')
            if response and 'data' in response:
                return response['data']
            return None
        except Exception as e:
            logger.error(f"Error getting show details: {e}")
            return None

    async def get_episode_details(self, episode_id: int) -> Optional[Dict]:
        try:
            response = await self._make_request('GET', f'episodes/{episode_id}/extended')
            if response and 'data' in response:
                return response['data']
            return None
        except Exception as e:
            logger.error(f"Error getting episode details: {e}")
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

    async def get_episodes(self, series_id: str) -> List[Dict]:
        try:
            response = await self._make_request('GET', f'series/{series_id}/episodes')
            if response and 'data' in response:
                return response['data']
            return []
        except Exception as e:
            logger.error(f"Error getting episodes: {e}")
            return []

    async def get_upcoming_episodes(self, series_id: str) -> List[Dict]:
        try:
            series = await self.get_series(series_id)
            if not series:
                logger.error(f"Could not find series with ID {series_id}")
                return []

            episodes = await self.get_episodes(series_id)
            if not episodes:
                logger.error(f"No episodes found for series {series_id}")
                return []

            now = datetime.now(timezone.utc)
            
            upcoming = []
            for episode in episodes:
                try:
                    air_date_str = episode.get('aired', '')  # TVDB v4 uses 'aired' instead of 'air_date'
                    if not air_date_str:
                        continue
                        
                    if 'T' in air_date_str:
                        air_date_str = air_date_str.replace('Z', '+00:00')
                        air_date = datetime.fromisoformat(air_date_str)
                    else:
                        air_date = datetime.strptime(air_date_str, "%Y-%m-%d")
                        air_date = air_date.replace(tzinfo=timezone.utc)
                    
                    if air_date > now:
                        upcoming.append(episode)
                except (ValueError, TypeError) as e:
                    logger.error(f"Error processing episode date: {e}")
                    continue

            upcoming.sort(key=lambda x: x.get('aired', ''))
            
            three_months_later = now + timedelta(days=90)
            upcoming = [
                ep for ep in upcoming 
                if datetime.fromisoformat(ep.get('aired', '').replace('Z', '+00:00')) <= three_months_later
            ]
            
            return upcoming

        except Exception as e:
            logger.error(f"Error getting upcoming episodes for series {series_id}: {str(e)}")
            return [] 