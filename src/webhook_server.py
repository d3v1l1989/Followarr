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

        @self.app.get("/health")
        async def health_check():
            return {"status": "healthy"}

        @self.app.post("/webhook/tautulli")
        async def tautulli_webhook(request: Request):
            try:
                # Get the raw body first
                body = await request.body()
                try:
                    # Try to parse the JSON
                    payload = json.loads(body)
                except json.JSONDecodeError as e:
                    # Log the raw body for debugging
                    logger.warning(f"Invalid JSON received from Tautulli. Raw body: {body.decode('utf-8', errors='ignore')}")
                    return JSONResponse(
                        status_code=400,
                        content={
                            "status": "error",
                            "message": "Invalid JSON payload",
                            "detail": str(e)
                        }
                    )

                # Log only essential information
                logger.info(f"Received Tautulli webhook: {payload.get('event', 'unknown_event')}")
                
                # Validate required fields
                if not self._validate_webhook_payload(payload):
                    return JSONResponse(
                        status_code=400,
                        content={
                            "status": "error",
                            "message": "Missing required fields in webhook payload"
                        }
                    )

                # Process the webhook
                await self._handle_tautulli_webhook(payload)
                return JSONResponse(content={"status": "success"})

            except Exception as e:
                logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
                return JSONResponse(
                    status_code=500,
                    content={
                        "status": "error",
                        "message": "Internal server error",
                        "detail": str(e)
                    }
                )

    def _validate_webhook_payload(self, payload: Dict) -> bool:
        """
        Validate that the webhook payload contains the required fields.
        """
        required_fields = ['event']
        
        # For media.added events, check additional required fields
        if payload.get('event') == 'media.added':
            required_fields.extend(['media_type'])

        return all(field in payload for field in required_fields)

    async def _handle_tautulli_webhook(self, payload: Dict):
        try:
            # Check if this is a recently added episode
            if payload.get('event') == 'media.added' and payload.get('media_type') == 'episode':
                logger.info(f"Processing media.added event for episode: {payload.get('title', 'Unknown')}")
                await self.notification_handler(payload)
            else:
                logger.debug(f"Ignoring event: {payload.get('event')} for media type: {payload.get('media_type')}")

        except Exception as e:
            logger.error(f"Error handling Tautulli webhook: {str(e)}", exc_info=True)
            # Don't raise the exception, just log it
            # This prevents the webhook from failing and Tautulli from retrying 