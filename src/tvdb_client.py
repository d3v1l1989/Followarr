import aiohttp
import os
from typing import Optional, Dict, List

class TVDBClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api4.thetvdb.com/v4"
        self._token = None

    async def _get_token(self) -> str:
        if self._token:
            return self._token

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/login",
                json={"apikey": self.api_key}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self._token = data["data"]["token"]
                    return self._token
                raise Exception(f"Failed to get TVDB token: {response.status}")

    async def _make_request(self, endpoint: str, method: str = "GET", params: Dict = None) -> Dict:
        token = await self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                f"{self.base_url}/{endpoint}",
                headers=headers,
                params=params
            ) as response:
                if response.status == 401:  # Token expired
                    self._token = None
                    return await self._make_request(endpoint, method, params)
                
                if response.status == 200:
                    return await response.json()
                raise Exception(f"TVDB API request failed: {response.status} - {await response.text()}")

    async def search_show(self, name: str) -> Optional[Dict]:
        try:
            # Use the search endpoint
            response = await self._make_request("search", params={
                "query": name,
                "type": "series"
            })
            
            if response and "data" in response:
                # Filter for exact or close matches
                shows = response["data"]
                for show in shows:
                    if show["type"] == "series":
                        # Get full series details
                        series_id = show["tvdb_id"]
                        details = await self.get_show_details(series_id)
                        if details:
                            return details
                
                # If no exact match found but we have results, return the first series
                for show in shows:
                    if show["type"] == "series":
                        series_id = show["tvdb_id"]
                        details = await self.get_show_details(series_id)
                        if details:
                            return details
            
            return None
        except Exception as e:
            print(f"Error searching for show: {str(e)}")
            return None

    async def get_show_details(self, show_id: int) -> Optional[Dict]:
        try:
            response = await self._make_request(f"series/{show_id}/extended")
            if response and "data" in response:
                return {
                    'id': response['data']['id'],
                    'seriesName': response['data']['name'],
                    'overview': response['data'].get('overview', ''),
                    'network': response['data'].get('network', ''),
                    'status': response['data'].get('status', ''),
                    'firstAired': response['data'].get('firstAired', ''),
                }
            return None
        except Exception as e:
            print(f"Error getting show details: {str(e)}")
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