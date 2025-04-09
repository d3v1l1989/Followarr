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
            """
            Health check endpoint for monitoring and container orchestration.
            Returns 200 OK if the server is running.
            """
            return {"status": "healthy"}

        @self.app.post("/webhook/tautulli")
        async def tautulli_webhook(request: Request):
            try:
                # Get the raw body first
                body = await request.body()
                try:
                    # Try to parse the JSON
                    payload = json.loads(body)
                    # Log the full payload for debugging
                    logger.info(f"Received Tautulli webhook payload: {json.dumps(payload, indent=2)}")
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

                # Log essential information
                event = payload.get('event', 'unknown_event')
                media_type = payload.get('media_type', 'unknown')
                title = payload.get('title', 'unknown')
                grandparent_title = payload.get('grandparent_title', 'unknown')
                logger.info(f"Processing Tautulli webhook - Event: {event}, Media Type: {media_type}, Title: {title}, Show: {grandparent_title}")
                
                # Validate required fields
                if not self._validate_webhook_payload(payload):
                    logger.warning(f"Missing required fields in webhook payload: {json.dumps(payload, indent=2)}")
                    return JSONResponse(
                        status_code=400,
                        content={
                            "status": "error",
                            "message": "Missing required fields in webhook payload"
                        }
                    )

                # Process the webhook
                await self._handle_tautulli_webhook(payload)
                logger.info(f"Successfully processed Tautulli webhook for {grandparent_title}")
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
        Validate that the webhook payload contains all required fields.
        """
        # Basic required fields
        required_fields = ['event', 'media_type']
        
        # For media.added events, check additional required fields
        if payload.get('event') == 'media.added' and payload.get('media_type') == 'episode':
            required_fields.extend([
                'grandparent_title',  # Show name
                'parent_index',       # Season number
                'index',             # Episode number
                'title',             # Episode name
                'originally_available_at'  # Air date
            ])

        # Check if all required fields are present
        missing_fields = [field for field in required_fields if field not in payload]
        if missing_fields:
            logger.warning(f"Missing required fields in webhook payload: {missing_fields}")
            return False

        return True

    async def _handle_tautulli_webhook(self, payload: Dict):
        try:
            # Check if this is a recently added episode
            if payload.get('event') == 'media.added' and payload.get('media_type') == 'episode':
                logger.info(f"Processing media.added event for episode: {payload.get('title', 'Unknown')}")
                
                # Validate episode data
                if not self._validate_episode_data(payload):
                    logger.warning("Invalid episode data in webhook payload")
                    return
                
                await self.notification_handler(payload)
            else:
                logger.debug(f"Ignoring event: {payload.get('event')} for media type: {payload.get('media_type')}")

        except Exception as e:
            logger.error(f"Error handling Tautulli webhook: {str(e)}", exc_info=True)
            # Don't raise the exception, just log it
            # This prevents the webhook from failing and Tautulli from retrying

    def _validate_episode_data(self, payload: Dict) -> bool:
        """
        Validate that the episode data is complete and valid.
        """
        try:
            # Check for required episode fields
            required_fields = {
                'grandparent_title': str,  # Show name
                'parent_index': int,       # Season number
                'index': int,             # Episode number
                'title': str,             # Episode name
                'originally_available_at': str  # Air date
            }

            for field, field_type in required_fields.items():
                if field not in payload:
                    logger.warning(f"Missing required field: {field}")
                    return False
                
                # Try to convert to expected type
                try:
                    if field_type == int:
                        int(payload[field])
                    elif field_type == str and not isinstance(payload[field], str):
                        str(payload[field])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid type for field {field}: {payload[field]}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Error validating episode data: {str(e)}")
            return False 