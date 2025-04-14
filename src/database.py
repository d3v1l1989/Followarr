from sqlalchemy import create_engine, Column, Integer, String, select, create_async_engine, MetaData, Table
from sqlalchemy.orm import sessionmaker, declarative_base, AsyncSession
import os
from typing import List, Dict
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

Base = declarative_base()

class Subscription(Base):
    __tablename__ = 'subscriptions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False)
    show_id = Column(Integer, nullable=False)
    show_name = Column(String, nullable=False)

class Database:
    def __init__(self, database_url: str):
        """Initialize the database connection."""
        self.database_url = database_url
        self.engine = create_async_engine(database_url)
        self.metadata = MetaData()
        self.follows = Table(
            'follows',
            self.metadata,
            Column('user_id', Integer, primary_key=True),
            Column('show_title', String, primary_key=True)
        )
        self.async_session_maker = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def async_session(self) -> AsyncSession:
        """Get an async session."""
        return self.async_session_maker()

    def init_db(self):
        # Explicitly touch the file path first to ensure it can be created/accessed
        try:
            db_path_str = self.engine.url.database
            if db_path_str: # Should always be true for sqlite
                db_path = Path(db_path_str)
                logger.info(f"Ensuring database file exists at: {db_path}")
                db_path.parent.mkdir(parents=True, exist_ok=True) # Ensure directory exists
                db_path.touch(exist_ok=True) # Create file if not exists
                logger.info(f"Database file path touched successfully.")
            else:
                logger.warning("Could not determine database file path from engine URL.")
        except Exception as e:
            logger.error(f"Error touching database file path: {e}", exc_info=True)
            # We might still want to proceed and let create_all try
            
        Base.metadata.create_all(self.engine)

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

    def get_user_subscriptions(self, user_id: str) -> List[Dict]:
        """Get all shows a user is subscribed to"""
        session = self.Session()
        try:
            subscriptions = session.query(Subscription).filter_by(
                user_id=str(user_id)
            ).all()
            
            return [
                {
                    'id': sub.show_id,
                    'name': sub.show_name
                }
                for sub in subscriptions
            ]
        finally:
            session.close()

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
            async with self.async_session() as session:
                result = await session.execute(
                    select(self.follows.c.user_id)
                    .where(self.follows.c.show_title == show_title)
                )
                followers = result.scalars().all()
                return followers
        except Exception as e:
            logger.error(f"Error getting show followers: {str(e)}")
            return [] 