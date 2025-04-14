from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import logging
import json
from typing import Callable, Dict
import hmac
import hashlib
import base64

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WebhookServer:
    def __init__(self, notification_handler: Callable, plex_token: str):
        self.app = FastAPI()
        self.notification_handler = notification_handler
        self.plex_token = plex_token

        @self.app.get("/health")
        async def health_check():
            """
            Health check endpoint for monitoring and container orchestration.
            Returns 200 OK if the server is running.
            """
            return {"status": "healthy"}

        @self.app.post("/webhook/plex")
        async def plex_webhook(request: Request):
            try:
                # Log request headers for debugging
                logger.info(f"Received webhook request from {request.client.host}")
                logger.debug(f"Request headers: {dict(request.headers)}")
                
                # Verify the webhook signature if present
                signature = request.headers.get('X-Plex-Signature')
                if signature:
                    if not self._verify_plex_signature(request, signature):
                        logger.warning("Invalid Plex webhook signature")
                        return JSONResponse(
                            status_code=401,
                            content={"status": "error", "message": "Invalid signature"}
                        )
                
                # Log the raw request body for debugging
                raw_body = await request.body()
                if not raw_body:
                    logger.error("Received empty webhook request body")
                    return JSONResponse(
                        status_code=400,
                        content={
                            "status": "error",
                            "message": "Empty request body"
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
                if not self._validate_plex_payload(payload):
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
                await self._handle_plex_webhook(payload)
                
                logger.info("Successfully processed Plex webhook")
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

    def _verify_plex_signature(self, request: Request, signature: str) -> bool:
        """
        Verify the Plex webhook signature.
        
        Args:
            request: The FastAPI request object
            signature: The signature from the X-Plex-Signature header
            
        Returns:
            bool: True if signature is valid, False otherwise
        """
        try:
            # Get the raw body
            body = request.body()
            
            # Create HMAC with the Plex token
            hmac_obj = hmac.new(
                self.plex_token.encode(),
                body,
                hashlib.sha1
            )
            
            # Compare the signatures
            expected_signature = base64.b64encode(hmac_obj.digest()).decode()
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Error verifying Plex signature: {str(e)}")
            return False

    def _validate_plex_payload(self, payload: Dict) -> bool:
        """
        Validate that the Plex webhook payload contains all required fields.
        """
        # Basic required fields for Plex webhooks
        required_fields = ['event', 'Metadata']
        
        # Check if all required fields are present
        missing_fields = [field for field in required_fields if field not in payload]
        if missing_fields:
            logger.warning(f"Missing required fields in webhook payload: {missing_fields}")
            return False

        # For media.added events, check additional required fields
        if payload.get('event') == 'media.added':
            metadata = payload.get('Metadata', {})
            if metadata.get('type') == 'episode':
                # TV show episode specific fields
                episode_fields = [
                    'grandparentTitle',  # Show name
                    'parentIndex',       # Season number
                    'index',            # Episode number
                    'title',            # Episode name
                    'originallyAvailableAt'  # Air date
                ]
                missing_fields = [field for field in episode_fields if field not in metadata]
                if missing_fields:
                    logger.warning(f"Missing required fields for episode: {missing_fields}")
                    return False
            elif metadata.get('type') == 'movie':
                # Movie specific fields
                movie_fields = [
                    'title',            # Movie name
                    'originallyAvailableAt'  # Release date
                ]
                missing_fields = [field for field in movie_fields if field not in metadata]
                if missing_fields:
                    logger.warning(f"Missing required fields for movie: {missing_fields}")
                    return False
            else:
                logger.warning(f"Unsupported media type: {metadata.get('type')}")
                return False

        return True

    async def _handle_plex_webhook(self, payload: Dict):
        try:
            # Check if this is a recently added media item
            if payload.get('event') == 'media.added':
                metadata = payload.get('Metadata', {})
                media_type = metadata.get('type')
                logger.info(f"Processing media.added event for {media_type}: {metadata.get('title', 'Unknown')}")
                
                # Validate media data
                if not self._validate_plex_payload(payload):
                    logger.warning("Invalid media data in webhook payload")
                    return
                
                # Only process TV show episodes
                if media_type == 'episode':
                    # Transform Plex payload to match our notification format
                    notification_payload = {
                        'event': 'media.added',
                        'media_type': 'episode',
                        'grandparent_title': metadata.get('grandparentTitle'),
                        'parent_media_index': metadata.get('parentIndex'),
                        'media_index': metadata.get('index'),
                        'title': metadata.get('title'),
                        'originally_available_at': metadata.get('originallyAvailableAt'),
                        'summary': metadata.get('summary', '')
                    }
                    await self.notification_handler(notification_payload)
                else:
                    logger.info(f"Ignoring {media_type} notification")
            else:
                logger.debug(f"Ignoring event: {payload.get('event')}")

        except Exception as e:
            logger.error(f"Error handling Plex webhook: {str(e)}", exc_info=True)
            # Don't raise the exception, just log it
            # This prevents the webhook from failing and Plex from retrying 