import aiohttp
import os
from typing import Optional, Dict, List

class TVDBClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.thetvdb.com/api"
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
                    self._token = data["token"]
                    return self._token
                raise Exception("Failed to get TVDB token")

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
                raise Exception(f"TVDB API request failed: {response.status}")

    async def search_show(self, name: str) -> Optional[Dict]:
        try:
            response = await self._make_request("search/series", params={"name": name})
            if response and "data" in response and response["data"]:
                return response["data"][0]  # Return first match
            return None
        except Exception:
            return None

    async def get_show_details(self, show_id: int) -> Optional[Dict]:
        try:
            response = await self._make_request(f"series/{show_id}")
            return response.get("data")
        except Exception:
            return None

    async def get_episode_details(self, episode_id: int) -> Optional[Dict]:
        try:
            response = await self._make_request(f"episodes/{episode_id}")
            return response.get("data")
        except Exception:
            return None 