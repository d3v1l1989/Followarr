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
                # Log request headers for debugging
                logger.info(f"Received webhook request from {request.client.host}")
                logger.debug(f"Request headers: {dict(request.headers)}")
                
                # Log the raw request body for debugging
                raw_body = await request.body()
                if not raw_body:
                    logger.error("Received empty webhook request body")
                    return JSONResponse(
                        status_code=400,
                        content={
                            "status": "error",
                            "message": "Empty request body",
                            "detail": "Tautulli webhook sent an empty request. Please check your Tautulli webhook configuration."
                        }
                    )
                
                logger.debug(f"Raw request body: {raw_body.decode()}")
                
                # Try to parse the JSON
                try:
                    payload = await request.json()
                    logger.debug(f"Parsed JSON payload: {json.dumps(payload, indent=2)}")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON: {str(e)}")
                    logger.error(f"Raw body that failed to parse: {raw_body.decode()}")
                    return JSONResponse(
                        status_code=400,
                        content={
                            "status": "error",
                            "message": "Invalid JSON payload",
                            "detail": str(e)
                        }
                    )
                
                # Validate the webhook payload
                if not self._validate_webhook_payload(payload):
                    logger.warning(f"Invalid webhook payload: {json.dumps(payload, indent=2)}")
                    return JSONResponse(
                        status_code=400,
                        content={
                            "status": "error",
                            "message": "Invalid webhook payload",
                            "detail": "Missing required fields"
                        }
                    )
                
                # Process the webhook
                await self._handle_tautulli_webhook(payload)
                
                logger.info(f"Successfully processed Tautulli webhook for {payload.get('grandparent_title', 'Unknown')}")
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
        
        # Check if all required fields are present
        missing_fields = [field for field in required_fields if field not in payload]
        if missing_fields:
            logger.warning(f"Missing required fields in webhook payload: {missing_fields}")
            return False

        # For media.added events, check additional required fields based on media type
        if payload.get('event') == 'media.added':
            if payload.get('media_type') == 'episode':
                # TV show episode specific fields
                episode_fields = [
                    'grandparent_title',  # Show name
                    'parent_media_index', # Season number
                    'media_index',       # Episode number
                    'title',            # Episode name
                    'originally_available_at'  # Air date
                ]
                missing_fields = [field for field in episode_fields if field not in payload]
                if missing_fields:
                    logger.warning(f"Missing required fields for episode: {missing_fields}")
                    return False
            elif payload.get('media_type') == 'movie':
                # Movie specific fields
                movie_fields = [
                    'title',            # Movie name
                    'originally_available_at'  # Release date
                ]
                missing_fields = [field for field in movie_fields if field not in payload]
                if missing_fields:
                    logger.warning(f"Missing required fields for movie: {missing_fields}")
                    return False
            else:
                logger.warning(f"Unsupported media type: {payload.get('media_type')}")
                return False

        return True

    async def _handle_tautulli_webhook(self, payload: Dict):
        try:
            # Check if this is a recently added media item
            if payload.get('event') == 'media.added':
                media_type = payload.get('media_type')
                logger.info(f"Processing media.added event for {media_type}: {payload.get('title', 'Unknown')}")
                
                # Validate media data
                if not self._validate_webhook_payload(payload):
                    logger.warning("Invalid media data in webhook payload")
                    return
                
                # Only process TV show episodes
                if media_type == 'episode':
                    await self.notification_handler(payload)
                else:
                    logger.info(f"Ignoring {media_type} notification")
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
                'parent_media_index': (int, str), # Season number (can be string or int)
                'media_index': (int, str),       # Episode number (can be string or int)
                'title': str,            # Episode name
                'originally_available_at': str  # Air date
            }

            for field, field_type in required_fields.items():
                if field not in payload:
                    logger.warning(f"Missing required field: {field}")
                    return False
                
                # Try to convert to expected type
                try:
                    if isinstance(field_type, tuple):  # Multiple types allowed
                        if int in field_type:
                            int(payload[field])  # Try to convert to int
                        elif str in field_type and not isinstance(payload[field], str):
                            str(payload[field])  # Try to convert to str
                    elif field_type == int:
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