from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import logging
import json
from typing import Callable, Dict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WebhookServer:
    def __init__(self, notification_handler: Callable):
        self.app = FastAPI()
        self.notification_handler = notification_handler

        @self.app.post("/webhook/tautulli")
        async def tautulli_webhook(request: Request):
            try:
                payload = await request.json()
                logger.info("Received Tautulli webhook: %s", payload.get('event'))
                await self._handle_tautulli_webhook(payload)
                return JSONResponse(content={"status": "success"})
            except Exception as e:
                logger.error("Error processing webhook: %s", str(e))
                raise HTTPException(status_code=500, detail=str(e))

    async def _handle_tautulli_webhook(self, payload: Dict):
        try:
            # Check if this is a recently added episode
            if payload.get('event') == 'media.added' and payload.get('media_type') == 'episode':
                await self.notification_handler(payload)
        except Exception as e:
            logger.error("Error handling Tautulli webhook: %s", str(e))
            raise 