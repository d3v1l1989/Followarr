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
    english_name: Optional[str] = None

    def __post_init__(self):
        # Handle TVDB v4 ID format (e.g., 'series-75978')
        if isinstance(self.id, str) and self.id.startswith('series-'):
            self.id = int(self.id.replace('series-', ''))
        
        # Use English name if available
        if self.english_name:
            self.name = self.english_name
            logger.info(f"Using English name: {self.name}")
        
        # Prioritize direct image URL if available
        if not self.image_url and self.image:
            if self.image.startswith('http'):
                self.image_url = self.image
            else:
                image_path = self.image if self.image.startswith('/') else f"/{self.image}"
                self.image_url = f"https://www.thetvdb.com{image_path}"
        
        # If we still don't have an image URL, try to get it from artworks
        if not self.image_url and self.artworks:
            for artwork in self.artworks:
                if artwork.get('type') == 'poster':
                    self.image_url = artwork.get('image')
                    break

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'TVShow':
        show_data = {
            'id': data.get('id'),
            'name': data.get('name'),
            'english_name': data.get('english_name'),
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
        self.token_expiry = None

    async def _get_token(self) -> str:
        """Get or refresh the TVDB API token."""
        if self.token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.token

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/login",
                    json={"apikey": self.api_key}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.token = data['data']['token']
                        # Set token expiry to 23 hours from now
                        self.token_expiry = datetime.now() + timedelta(hours=23)
                        return self.token
                    else:
                        logger.error(f"Failed to get TVDB token: {response.status}")
                        raise Exception("Failed to get TVDB token")
        except Exception as e:
            logger.error(f"Error getting TVDB token: {str(e)}")
            raise

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an async request to the TVDB API."""
        try:
            # Get or refresh the token
            token = await self._get_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            # Use aiohttp for async HTTP requests
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/{endpoint}"
                async with session.request(method, url, headers=headers, **kwargs) as response:
                    if response.status == 404:
                        logger.warning(f"TVDB API 404: {endpoint} not found")
                        return None
                        
                    response.raise_for_status()
                    return await response.json()
                    
        except aiohttp.ClientError as e:
            logger.error(f"TVDB API error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error making TVDB request: {str(e)}")
            raise

    async def search_show(self, query: str) -> Optional[TVShow]:
        """Search for a TV show by name."""
        try:
            logger.info(f"Starting show search for query: {query}")
            # Search for the show
            data = await self._make_request("GET", f"search?query={query}")
            if not data or not data.get('data'):
                logger.warning(f"No results found for query: {query}")
                return None
                
            # Return the first result
            show_data = data['data'][0]
            logger.info(f"Found show: {show_data.get('name')} (ID: {show_data.get('id')})")
            
            # Get show details with translations
            show_details = await self.get_show_details(show_data.get('id'))
            if show_details:
                # Update the show name with English title if available
                show_data['name'] = show_details.get('english_name', show_data.get('name'))
                logger.info(f"Using English title: {show_data['name']}")
            
            # Log poster/image information
            if 'image' in show_data:
                logger.info(f"Show has image path: {show_data['image']}")
            else:
                logger.warning(f"No image path found for show: {show_data.get('name')}")
                
            if 'image_url' in show_data:
                logger.info(f"Show has direct image URL: {show_data['image_url']}")
                # Use the direct image URL if available
                show_data['image'] = show_data['image_url']
            else:
                logger.info(f"No direct image URL found for show: {show_data.get('name')}")
                
            show = TVShow.from_api_response(show_data)
            
            # Log final image URL after processing
            if show.image_url:
                logger.info(f"Final image URL for {show.name}: {show.image_url}")
            else:
                logger.warning(f"No final image URL available for {show.name}")
                
            return show
        except Exception as e:
            logger.error(f"Error searching for show: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    async def get_show_details(self, show_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a TV show."""
        try:
            # Strip any prefix from the show ID (e.g., 'series-', 'movie-')
            clean_show_id = str(show_id)  # Convert to string first
            if '-' in clean_show_id:
                clean_show_id = clean_show_id.split('-')[-1]
            
            # First try to get basic show info with translations and aliases
            basic_data = await self._make_request("GET", f"series/{clean_show_id}?include=translations,aliases")
            if not basic_data or not basic_data.get('data'):
                logger.warning(f"Could not get basic show info for ID: {clean_show_id}")
                return None
            
            # Then try to get extended info
            try:
                extended_data = await self._make_request("GET", f"series/{clean_show_id}/extended?include=translations,aliases")
                if not extended_data or not extended_data.get('data'):
                    logger.warning(f"Could not get extended show info for ID: {clean_show_id}")
                    # Use basic data if extended data is not available
                    show = basic_data['data']
                else:
                    show = extended_data['data']
            except Exception as e:
                logger.warning(f"Error getting extended show info for ID: {clean_show_id}: {str(e)}")
                # Fall back to basic data
                show = basic_data['data']
            
            # Get the primary image URL
            image_url = None
            if show.get('image'):
                image_url = show['image']
            elif show.get('images'):
                for image in show['images']:
                    if image.get('type') == 'poster' and image.get('thumbnail'):
                        image_url = image['thumbnail']
                        break
            
            # If we have an image URL, make sure it's absolute
            if image_url and not image_url.startswith('http'):
                image_url = f"https://artworks.thetvdb.com{image_url}"
            
            # Get English title from translations and aliases
            english_title = show.get('name')
            
            # First check translations
            if show.get('translations'):
                for translation in show['translations']:
                    if translation.get('language') == 'eng':
                        english_title = translation.get('name', english_title)
                        logger.info(f"Found English title from translations: {english_title}")
                        break
            
            # Then check aliases if we don't have an English title from translations
            if english_title == show.get('name') and show.get('aliases'):
                for alias in show['aliases']:
                    # Handle both string and dictionary aliases
                    alias_name = alias.get('name') if isinstance(alias, dict) else alias
                    if not alias_name:
                        continue
                        
                    # Check if alias is in English (simple check for non-ASCII characters)
                    try:
                        if all(ord(c) < 128 for c in str(alias_name)):
                            # Check if this is actually an English title (not pinyin or other romanization)
                            if not any(char.isdigit() for char in str(alias_name)):  # Skip if contains numbers
                                if not any(char in str(alias_name).lower() for char in ['xian', 'zhong', 'ying', 'xiong']):  # Skip common pinyin words
                                    english_title = alias_name
                                    logger.info(f"Found English title from aliases: {english_title}")
                                    break
                    except (TypeError, ValueError):
                        # Skip if we can't process this alias
                        continue
            
            # Ensure english_title is a string, not a dictionary
            if isinstance(english_title, dict):
                english_title = english_title.get('name', show.get('name'))
                logger.info(f"Extracted name from dictionary: {english_title}")
            
            return {
                'id': show.get('id'),
                'name': show.get('name'),
                'english_name': english_title,
                'overview': show.get('overview'),
                'status': show.get('status'),
                'first_aired': show.get('firstAired'),
                'network': show.get('network'),
                'image': image_url,
                'image_url': image_url
            }
            
        except Exception as e:
            logger.error(f"Error getting show details: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    async def get_episode_details(self, episode_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed information about an episode."""
        try:
            data = await self._make_request("GET", f"episodes/{episode_id}")
            if not data or not data.get('data'):
                logger.warning(f"No details found for episode ID: {episode_id}")
                return None
                
            return data['data']
        except Exception as e:
            logger.error(f"Error getting episode details: {str(e)}")
            return None

    async def search_series(self, query: str) -> List[Dict]:
        """Search for TV series."""
        try:
            # Make the request using the async _make_request method
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
            series_response = await self._make_request("GET", f"series/{series_id}")
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
                response = await self._make_request("GET", f"series/{series_id}/episodes/default", params=params)
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

                    # Process each episode to prefer English translations
                    for episode in page_episodes:
                        # Get English translation if available
                        if "translations" in episode:
                            for translation in episode["translations"]:
                                if translation.get("language") == "eng":
                                    # Prefer English title and overview
                                    if translation.get("name"):
                                        episode["name"] = translation["name"]
                                    if translation.get("overview"):
                                        episode["overview"] = translation["overview"]
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
        """Get upcoming episodes for a series."""
        try:
            # Strip any prefix from the series ID
            clean_series_id = series_id
            if '-' in series_id:
                clean_series_id = series_id.split('-')[-1]
            
            # Get all episodes
            episodes = await self.get_episodes(clean_series_id)
            if not episodes:
                return []
            
            # Filter for upcoming episodes
            now = datetime.now(timezone.utc)  # Make sure now is timezone-aware
            upcoming_episodes = []
            
            for episode in episodes:
                # Skip episodes without air date
                if not episode.get('aired'):
                    continue
                
                # Parse air date
                try:
                    # Try parsing as ISO format with timezone
                    air_date = datetime.fromisoformat(episode['aired'].replace('Z', '+00:00'))
                    if air_date.tzinfo is None:
                        # If the parsed datetime is naive, make it timezone-aware
                        air_date = air_date.replace(tzinfo=timezone.utc)
                except ValueError:
                    try:
                        # Try parsing as date-only format and make it timezone-aware
                        air_date = datetime.strptime(episode['aired'], '%Y-%m-%d')
                        # Set time to midnight UTC for date-only times
                        air_date = air_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
                    except ValueError:
                        continue
                
                # Only include episodes that haven't aired yet
                if air_date > now:
                    upcoming_episodes.append(episode)
            
            # Sort by air date
            upcoming_episodes.sort(key=lambda x: x.get('aired', ''))
            
            return upcoming_episodes
            
        except Exception as e:
            logger.error(f"Error getting upcoming episodes: {str(e)}")
            return [] 