import logging
from typing import Optional, Dict, Tuple
import re

logger = logging.getLogger(__name__)

class GUIDParser:
    """Utility class to parse and handle Plex GUIDs."""
    
    @staticmethod
    def parse_guid(guid: str) -> Optional[Tuple[str, str]]:
        """
        Parse a Plex GUID into its source and ID components.
        
        Args:
            guid (str): The GUID to parse (e.g., 'tmdb://12345', 'tvdb://67890')
            
        Returns:
            Optional[Tuple[str, str]]: Tuple of (source, id) if valid, None otherwise
        """
        if not guid:
            return None
            
        try:
            # Match the pattern source://id
            match = re.match(r'^([a-zA-Z]+)://([^/]+)$', guid)
            if not match:
                logger.warning(f"Invalid GUID format: {guid}")
                return None
                
            source, id = match.groups()
            return (source.lower(), id)
        except Exception as e:
            logger.error(f"Error parsing GUID {guid}: {str(e)}")
            return None
            
    @staticmethod
    def get_tvdb_id(guid: str) -> Optional[int]:
        """
        Extract TVDB ID from a GUID if it's a TVDB GUID.
        
        Args:
            guid (str): The GUID to parse
            
        Returns:
            Optional[int]: TVDB ID if found, None otherwise
        """
        parsed = GUIDParser.parse_guid(guid)
        if not parsed:
            return None
            
        source, id = parsed
        if source == 'tvdb':
            try:
                return int(id)
            except ValueError:
                logger.warning(f"Invalid TVDB ID format: {id}")
                return None
        return None
        
    @staticmethod
    def get_tmdb_id(guid: str) -> Optional[int]:
        """
        Extract TMDB ID from a GUID if it's a TMDB GUID.
        
        Args:
            guid (str): The GUID to parse
            
        Returns:
            Optional[int]: TMDB ID if found, None otherwise
        """
        parsed = GUIDParser.parse_guid(guid)
        if not parsed:
            return None
            
        source, id = parsed
        if source == 'tmdb':
            try:
                return int(id)
            except ValueError:
                logger.warning(f"Invalid TMDB ID format: {id}")
                return None
        return None
        
    @staticmethod
    def get_imdb_id(guid: str) -> Optional[str]:
        """
        Extract IMDb ID from a GUID if it's an IMDb GUID.
        
        Args:
            guid (str): The GUID to parse
            
        Returns:
            Optional[str]: IMDb ID if found, None otherwise
        """
        parsed = GUIDParser.parse_guid(guid)
        if not parsed:
            return None
            
        source, id = parsed
        if source == 'imdb':
            # IMDb IDs start with 'tt' followed by numbers
            if re.match(r'^tt\d+$', id):
                return id
            logger.warning(f"Invalid IMDb ID format: {id}")
        return None 