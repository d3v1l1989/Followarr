from fastapi import FastAPI, Request, HTTPException, Form, File, UploadFile
from fastapi.responses import JSONResponse
import logging
import json
from typing import Callable, Dict, Any
import hmac
import hashlib
import base64
import asyncio
from datetime import datetime
import traceback

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WebhookServer:
    def __init__(self, callback):
        self.app = FastAPI()
        self.callback = callback
        self.setup_routes()

    def setup_routes(self):
        @self.app.post("/webhook/plex")
        async def handle_plex_webhook(payload: str = Form(...), thumb: UploadFile = None):
            """Handle incoming Plex webhook notifications."""
            try:
                # Parse the JSON payload
                data = json.loads(payload)
                logger.info(f"Received Plex webhook: {data.get('event')}")
                
                # Only process library.new events
                if data.get('event') != 'library.new':
                    logger.info(f"Ignoring non-library.new event: {data.get('event')}")
                    return {"status": "ignored", "reason": "not_library_new"}
                
                # Check if it's a TV show episode
                if data.get('Metadata', {}).get('type') != 'episode':
                    logger.info(f"Ignoring non-episode content: {data.get('Metadata', {}).get('type')}")
                    return {"status": "ignored", "reason": "not_episode"}
                
                # Process the notification
                await self.callback(data)
                return {"status": "success"}
                
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON payload: {str(e)}")
                return {"status": "error", "message": "Invalid JSON payload"}
            except Exception as e:
                logger.error(f"Error processing webhook: {str(e)}")
                logger.error(traceback.format_exc())
                return {"status": "error", "message": str(e)}
        
        @self.app.get("/health")
        async def health_check():
            return {"status": "healthy"}

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
                    await self.callback(notification_payload)
                else:
                    logger.info(f"Ignoring {media_type} notification")
            else:
                logger.debug(f"Ignoring event: {payload.get('event')}")

        except Exception as e:
            logger.error(f"Error handling Plex webhook: {str(e)}", exc_info=True)
            # Don't raise the exception, just log it
            # This prevents the webhook from failing and Plex from retrying 