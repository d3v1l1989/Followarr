from sqlalchemy import Column, Integer, String, select, MetaData, Table, and_, or_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os
from typing import List, Dict, Any, Optional
import logging
from pathlib import Path
from src.guid_parser import GUIDParser

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, database_url: str):
        """Initialize the database connection."""
        # Convert sqlite:/// to sqlite+aiosqlite:///
        if database_url.startswith('sqlite:///'):
            database_url = database_url.replace('sqlite:///', 'sqlite+aiosqlite:///')
        
        self.database_url = database_url
        self.engine = create_async_engine(
            database_url,
            connect_args={"check_same_thread": False}
        )
        self.metadata = MetaData()
        
        # Define the follows table with additional GUID fields
        self.follows = Table(
            'follows',
            self.metadata,
            Column('user_id', Integer, primary_key=True),
            Column('show_title', String, primary_key=True),
            Column('plex_id', String),  # Plex's rating key
            Column('tvdb_id', Integer),  # TVDB ID if available
            Column('tmdb_id', Integer),  # TMDB ID if available
            Column('imdb_id', String),   # IMDb ID if available
            Column('guid', String),       # Original Plex GUID
            Column('show_id', Integer, primary_key=True)
        )
        
        # Create async session maker
        self.async_session_maker = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def init_db(self):
        """Initialize the database tables."""
        try:
            # Ensure the database directory exists
            db_path = Path(self.database_url.replace('sqlite+aiosqlite:///', ''))
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with self.engine.begin() as conn:
                # Only create tables if they don't exist
                await conn.run_sync(self.metadata.create_all)
            logger.info("Database tables initialized successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {str(e)}")
            raise

    async def async_session(self) -> AsyncSession:
        """Get an async session."""
        return self.async_session_maker()

    def add_subscription(self, user_id: str, show_id: int, show_name: str) -> bool:
        """Add a show subscription for a user"""
        session = self.Session()
        try:
            # Check if subscription already exists
            existing = session.query(Subscription).filter_by(
                user_id=str(user_id),
                show_id=show_id
            ).first()
            
            if existing:
                return False

            # Add new subscription
            subscription = Subscription(
                user_id=str(user_id),
                show_id=show_id,
                show_name=show_name
            )
            session.add(subscription)
            session.commit()
            return True
        finally:
            session.close()

    def remove_subscription(self, user_id: str, show_id: int) -> bool:
        """Remove a show subscription for a user"""
        session = self.Session()
        try:
            subscription = session.query(Subscription).filter_by(
                user_id=str(user_id),
                show_id=show_id
            ).first()
            
            if subscription:
                session.delete(subscription)
                session.commit()
                return True
            return False
        finally:
            session.close()

    async def get_user_subscriptions(self, user_id: str) -> List[Dict]:
        """Get all shows a user is subscribed to"""
        try:
            logger.info(f"Getting subscriptions for user: {user_id}")
            session = await self.async_session()
            async with session as session:
                result = await session.execute(
                    select(self.follows.c.show_title, self.follows.c.show_id)
                    .where(self.follows.c.user_id == user_id)
                )
                shows = result.all()
                logger.info(f"User {user_id} follows {len(shows)} shows: {[show.show_title for show in shows]}")
                return [{'show_title': show.show_title, 'show_id': str(show.show_id)} for show in shows]
        except Exception as e:
            logger.error(f"Error getting user subscriptions: {str(e)}")
            return []

    def get_show_subscribers(self, show_id: int) -> List[str]:
        """Get all users subscribed to a show"""
        session = self.Session()
        try:
            subscriptions = session.query(Subscription).filter_by(
                show_id=show_id
            ).all()
            
            return [sub.user_id for sub in subscriptions]
        finally:
            session.close()

    def is_user_subscribed(self, user_id: str, show_id: int) -> bool:
        """Check if a user is subscribed to a show"""
        session = self.Session()
        try:
            return session.query(Subscription).filter_by(
                user_id=str(user_id),
                show_id=show_id
            ).first() is not None
        finally:
            session.close()

    def get_users_by_show(self, show_name: str) -> List[Dict]:
        """Get all users who follow a specific show."""
        session = self.Session()
        try:
            # Get all users who follow this show
            subscriptions = session.query(Subscription).filter_by(show_name=show_name).all()
            
            if not subscriptions:
                logger.info(f"No users follow {show_name}")
                return []
            
            # Get unique user IDs
            user_ids = list(set(sub.user_id for sub in subscriptions))
            
            # Return user details
            return [{
                'discord_id': user_id,
                'name': f"User {user_id}"  # We don't store usernames, just IDs
            } for user_id in user_ids]
                
        except Exception as e:
            logger.error(f"Error getting users by show: {e}")
            return []
        finally:
            session.close()

    async def get_show_followers(self, show_title: str) -> List[int]:
        """Get all users following a specific show."""
        try:
            logger.info(f"Looking for followers of show: {show_title}")
            session = await self.async_session()
            async with session as session:
                # Get all followers for this show using case-insensitive matching
                result = await session.execute(
                    select(self.follows.c.user_id)
                    .where(self.follows.c.show_title.ilike(show_title))
                )
                followers = result.scalars().all()
                logger.info(f"Found {len(followers)} followers for show: {show_title}")
                return followers
        except Exception as e:
            logger.error(f"Error getting show followers: {str(e)}")
            return []

    async def get_show_followers_by_plex_id(self, plex_id: str) -> List[int]:
        """Get all users following a show by its Plex ID."""
        try:
            logger.info(f"Looking for followers of show with Plex ID: {plex_id}")
            session = await self.async_session()
            async with session as session:
                # Get all followers for this show using Plex ID
                result = await session.execute(
                    select(self.follows.c.user_id)
                    .where(self.follows.c.plex_id == plex_id)
                )
                followers = result.scalars().all()
                logger.info(f"Found {len(followers)} followers for show with Plex ID: {plex_id}")
                return followers
        except Exception as e:
            logger.error(f"Error getting show followers by Plex ID: {str(e)}")
            return []

    async def add_follower(self, user_id: int, show_title: str, show_id: int, plex_id: Optional[str] = None, 
                          tvdb_id: Optional[int] = None, tmdb_id: Optional[int] = None, 
                          imdb_id: Optional[str] = None, guid: Optional[str] = None):
        """Add a new show follower with GUID information."""
        try:
            session = await self.async_session()
            async with session as session:
                await session.execute(
                    self.follows.insert().values(
                        user_id=user_id,
                        show_title=show_title,
                        show_id=show_id,
                        plex_id=plex_id,
                        tvdb_id=tvdb_id,
                        tmdb_id=tmdb_id,
                        imdb_id=imdb_id,
                        guid=guid
                    )
                )
                await session.commit()
                logger.info(f"Added follower {user_id} for show {show_title}")
        except Exception as e:
            logger.error(f"Error adding follower: {str(e)}")
            raise

    async def remove_follower(self, user_id: int, show_title: str) -> bool:
        """Remove a user as a follower of a show."""
        try:
            session = await self.async_session()
            async with session as session:
                # Get all shows the user follows
                result = await session.execute(
                    select(self.follows.c.show_title, self.follows.c.show_id)
                    .where(self.follows.c.user_id == user_id)
                )
                user_shows = result.all()
                
                # Try to find a matching show using case-insensitive comparison
                for show in user_shows:
                    db_title = show.show_title.lower()
                    search_title = show_title.lower()
                    
                    # Try different variations of the title
                    title_variations = [
                        db_title,  # Original title
                        db_title.split(' (')[0].strip(),  # Remove year
                        db_title.split(':')[0].strip(),  # Remove subtitle
                        db_title.replace('&', 'and'),  # Replace & with and
                        db_title.replace('and', '&'),  # Replace and with &
                        db_title.replace(':', ''),  # Remove colons
                        db_title.replace('-', ' '),  # Replace hyphens with spaces
                        db_title.replace('  ', ' ').strip(),  # Remove double spaces
                    ]
                    
                    # Remove duplicates while preserving order
                    title_variations = list(dict.fromkeys(title_variations))
                    
                    if search_title in title_variations:
                        # Found a match, remove the follower
                        stmt = self.follows.delete().where(
                            (self.follows.c.user_id == user_id) &
                            (self.follows.c.show_id == show.show_id)
                        )
                        await session.execute(stmt)
                        await session.commit()
                        return True
                
                return False
        except Exception as e:
            logger.error(f"Error removing follower: {str(e)}")
            return False

    async def get_user_follows(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all shows followed by a user."""
        try:
            session = await self.async_session()
            async with session as session:
                result = await session.execute(
                    select(self.follows.c.show_title, self.follows.c.show_id)
                    .where(self.follows.c.user_id == int(user_id))
                )
                shows = result.all()
                
                # Convert to list of dictionaries
                return [{'show_title': show[0], 'show_id': show[1]} for show in shows]
                
        except Exception as e:
            logger.error(f"Error getting user follows: {str(e)}")
            return []

    async def get_show_followers_by_guid(self, guid: str) -> List[int]:
        """Get all users following a show by its Plex GUID."""
        try:
            logger.info(f"Looking for followers of show with GUID: {guid}")
            session = await self.async_session()
            async with session as session:
                # Parse the GUID to get source and ID
                parsed = GUIDParser.parse_guid(guid)
                if not parsed:
                    logger.warning(f"Invalid GUID format: {guid}")
                    return []
                    
                source, id = parsed
                
                # Build query based on GUID source
                query = select(self.follows.c.user_id)
                
                if source == 'tvdb':
                    query = query.where(self.follows.c.tvdb_id == int(id))
                elif source == 'tmdb':
                    query = query.where(self.follows.c.tmdb_id == int(id))
                elif source == 'imdb':
                    query = query.where(self.follows.c.imdb_id == id)
                else:
                    # For other sources or if parsing failed, try exact GUID match
                    query = query.where(self.follows.c.guid == guid)
                
                result = await session.execute(query)
                followers = result.scalars().all()
                logger.info(f"Found {len(followers)} followers for show with GUID: {guid}")
                return followers
        except Exception as e:
            logger.error(f"Error getting show followers by GUID: {str(e)}")
            return []

    async def update_show_guids(self, show_title: str, plex_id: Optional[str] = None,
                              tvdb_id: Optional[int] = None, tmdb_id: Optional[int] = None,
                              imdb_id: Optional[str] = None, guid: Optional[str] = None):
        """Update GUID information for a show."""
        try:
            session = await self.async_session()
            async with session as session:
                # Build update values
                update_values = {}
                if plex_id is not None:
                    update_values['plex_id'] = plex_id
                if tvdb_id is not None:
                    update_values['tvdb_id'] = tvdb_id
                if tmdb_id is not None:
                    update_values['tmdb_id'] = tmdb_id
                if imdb_id is not None:
                    update_values['imdb_id'] = imdb_id
                if guid is not None:
                    update_values['guid'] = guid
                
                if update_values:
                    await session.execute(
                        self.follows.update()
                        .where(self.follows.c.show_title == show_title)
                        .values(**update_values)
                    )
                    await session.commit()
                    logger.info(f"Updated GUID information for show: {show_title}")
        except Exception as e:
            logger.error(f"Error updating show GUIDs: {str(e)}")
            raise 