import aiohttp
import os
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

class TVDBClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api4.thetvdb.com/v4"
        self._token = None
        logger.info("Initialized TVDB Client")

    async def _get_token(self) -> str:
        if self._token:
            return self._token

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
                        self._token = data["data"]["token"]
                        logger.info("Successfully obtained TVDB token")
                        return self._token
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
                        self._token = None
                        return await self._make_request(endpoint, method, params)
                    
                    if response.status == 200:
                        return await response.json()
                    
                    logger.error(f"TVDB API request failed: Status {response.status}, Response: {response_text}")
                    raise Exception(f"TVDB API request failed: {response.status}")
            except Exception as e:
                logger.error(f"Error in _make_request: {str(e)}")
                raise

    async def search_show(self, name: str) -> Optional[Dict]:
        logger.info(f"Searching for show: {name}")
        try:
            # Use the search endpoint
            response = await self._make_request("search", params={
                "query": name,
                "type": "series"
            })
            
            logger.debug(f"Search response: {response}")
            
            if response and "data" in response:
                shows = response["data"]
                logger.info(f"Found {len(shows)} results for '{name}'")
                
                # Log all found shows
                for show in shows:
                    logger.debug(f"Found show: {show.get('name', 'Unknown')} (Type: {show.get('type', 'Unknown')})")
                
                # Filter for exact or close matches
                for show in shows:
                    if show["type"] == "series":
                        logger.info(f"Getting details for show: {show.get('name', 'Unknown')}")
                        series_id = show["tvdb_id"]
                        details = await self.get_show_details(series_id)
                        if details:
                            logger.info(f"Returning details for: {details['seriesName']}")
                            return details
                
                # If no exact match found but we have results, return the first series
                for show in shows:
                    if show["type"] == "series":
                        logger.info(f"Falling back to first match: {show.get('name', 'Unknown')}")
                        series_id = show["tvdb_id"]
                        details = await self.get_show_details(series_id)
                        if details:
                            return details
            
            logger.warning(f"No shows found for query: {name}")
            return None
        except Exception as e:
            logger.error(f"Error searching for show '{name}': {str(e)}")
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