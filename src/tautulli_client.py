import aiohttp
from typing import Optional, Dict, List
import logging

class TautulliClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key

    async def _make_request(self, cmd: str, params: Dict = None) -> Dict:
        if params is None:
            params = {}
        
        params.update({
            'apikey': self.api_key,
            'cmd': cmd
        })

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/v2", params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data['response']['result'] == 'success':
                            return data['response']['data']
                        else:
                            logging.error(f"Tautulli API error: {data['response']['message']}")
                            return None
                    else:
                        logging.error(f"Tautulli API HTTP error: {response.status}")
                        return None
        except Exception as e:
            logging.error(f"Tautulli API request failed: {str(e)}")
            return None 