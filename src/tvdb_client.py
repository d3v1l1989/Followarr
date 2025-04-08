import aiohttp
import os
import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from datetime import datetime
import traceback

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
        if self.token:
            return self.token

        logger.info("Getting new TVDB token")
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.base_url}/login",
                    json={"apikey": self.api_key}
                ) as response:
                    response_text = await response.text()
                    logger.debug(f"Token response: {response_text}")
                    
                    if response.status == 200:
                        data = await response.json()
                        self.token = data["data"]["token"]
                        logger.info("Successfully obtained TVDB token")
                        return self.token
                    logger.error(f"Failed to get TVDB token. Status: {response.status}, Response: {response_text}")
                    raise Exception(f"Failed to get TVDB token: {response.status}")
            except Exception as e:
                logger.error(f"Error in _get_token: {str(e)}")
                raise

    async def _make_request(self, endpoint: str, method: str = "GET", params: Dict = None) -> Dict:
        token = await self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        logger.info(f"Making TVDB API request: {method} {endpoint} with params: {params}")
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.request(
                    method,
                    f"{self.base_url}/{endpoint}",
                    headers=headers,
                    params=params
                ) as response:
                    response_text = await response.text()
                    logger.debug(f"TVDB API response: {response_text}")
                    
                    if response.status == 401:  # Token expired
                        logger.info("Token expired, getting new token")
                        self.token = None
                        return await self._make_request(endpoint, method, params)
                    
                    if response.status == 200:
                        return await response.json()
                    
                    logger.error(f"TVDB API request failed: Status {response.status}, Response: {response_text}")
                    raise Exception(f"TVDB API request failed: {response.status}")
            except Exception as e:
                logger.error(f"Error in _make_request: {str(e)}")
                raise

    async def search_series(self, query: str) -> List[Dict]:
        """Search for TV series by name"""
        try:
            response = await self._make_request("search", params={"query": query, "type": "series"})
            if response and "data" in response:
                logger.info(f"Found {len(response['data'])} results for '{query}'")
                return response["data"]
            return []
        except Exception as e:
            logger.error(f"Error in search_series: {str(e)}")
            return []

    async def get_series_extended(self, series_id: int) -> Optional[Dict]:
        """Get extended information for a TV series"""
        try:
            response = await self._make_request(f"series/{series_id}/extended")
            if response and "data" in response:
                logger.info(f"Successfully got details for: {response['data'].get('name', 'Unknown')}")
                return response["data"]
            return None
        except Exception as e:
            logger.error(f"Error in get_series_extended: {str(e)}")
            return None

    async def search_show(self, show_name: str) -> Optional[TVShow]:
        """Search for a TV show by name"""
        logger.info(f"Searching for show: {show_name}")
        
        try:
            results = await self.search_series(show_name)
            if not results:
                return None
            
            # Find the best match (first result)
            show = results[0] if results else None
            if not show:
                return None
            
            # Get extended details for the show
            show_id = show.get('tvdb_id') or show.get('id')
            if not show_id:
                return None
                
            logger.info(f"Getting details for show: {show.get('name')}")
            show_details = await self.get_series_extended(show_id)
            if not show_details:
                return None
                
            # Create TVShow instance using the factory method
            return TVShow.from_api_response(show_details)
            
        except Exception as e:
            logger.error(f"Error searching for show: {str(e)}")
            return None

    async def get_show_details(self, show_id: int) -> Optional[Dict]:
        logger.info(f"Getting details for show ID: {show_id}")
        try:
            response = await self._make_request(f"series/{show_id}/extended")
            logger.debug(f"Show details response: {response}")
            
            if response and "data" in response:
                show_data = {
                    'id': response['data']['id'],
                    'seriesName': response['data']['name'],
                    'overview': response['data'].get('overview', ''),
                    'network': response['data'].get('network', ''),
                    'status': response['data'].get('status', ''),
                    'firstAired': response['data'].get('firstAired', ''),
                }
                logger.info(f"Successfully got details for: {show_data['seriesName']}")
                return show_data
            
            logger.warning(f"No details found for show ID: {show_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting show details for ID {show_id}: {str(e)}")
            return None

    async def get_episode_details(self, episode_id: int) -> Optional[Dict]:
        try:
            response = await self._make_request(f"episodes/{episode_id}/extended")
            if response and "data" in response:
                return response["data"]
            return None
        except Exception as e:
            print(f"Error getting episode details: {str(e)}")
            return None

    async def get_upcoming_episodes(self, show_id: int) -> List[Dict]:
        """Get upcoming episodes for a show"""
        try:
            logger.info(f"Getting upcoming episodes for show ID: {show_id}")
            response = await self._make_request(f"series/{show_id}/extended")
            
            if not response or "data" not in response:
                logger.warning(f"No data found for show {show_id}")
                return []

            data = response["data"]
            
            # Debug log the response structure
            logger.debug(f"Show data keys: {data.keys()}")
            
            # Episodes might be under 'episodes' or 'episode'
            episodes = data.get("episodes", data.get("episode", []))
            if not episodes:
                logger.info(f"No episodes found for show {show_id}")
                return []
            
            # Get current date in YYYY-MM-DD format
            today = datetime.now().strftime("%Y-%m-%d")
            
            # Filter for upcoming episodes
            upcoming = []
            for ep in episodes:
                if not isinstance(ep, dict):
                    continue
                    
                air_date = ep.get('aired') or ep.get('firstAired')
                if not air_date or air_date < today:
                    continue
                    
                upcoming.append({
                    'id': ep.get('id'),
                    'name': ep.get('name'),
                    'overview': ep.get('overview'),
                    'season': ep.get('seasonNumber'),
                    'episode': ep.get('number') or ep.get('episodeNumber'),
                    'air_date': air_date,
                    'runtime': ep.get('runtime'),
                    'image': ep.get('image'),
                    'show_name': data.get('name', 'Unknown Show')
                })
            
            # Sort by air date
            upcoming.sort(key=lambda x: x['air_date'])
            
            logger.info(f"Found {len(upcoming)} upcoming episodes for show {show_id}")
            return upcoming
            
        except Exception as e:
            logger.error(f"Error getting upcoming episodes for show {show_id}: {str(e)}")
            logger.error(traceback.format_exc())
            return [] 