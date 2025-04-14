from sqlalchemy import Column, Integer, String, select, MetaData, Table
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os
from typing import List, Dict
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class Subscription:
    __tablename__ = 'subscriptions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False)
    show_id = Column(Integer, nullable=False)
    show_name = Column(String, nullable=False)

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
        
        # Define the follows table
        self.follows = Table(
            'follows',
            self.metadata,
            Column('user_id', Integer, primary_key=True),
            Column('show_title', String, primary_key=True)
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
                await conn.run_sync(self.metadata.create_all)
            logger.info("Database tables created successfully")
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

    async def add_follower(self, user_id: int, show_title: str) -> bool:
        """Add a user as a follower of a show."""
        try:
            async with self.async_session() as session:
                stmt = self.follows.insert().values(
                    user_id=user_id,
                    show_title=show_title
                )
                await session.execute(stmt)
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding follower: {str(e)}")
            return False

    async def remove_follower(self, user_id: int, show_title: str) -> bool:
        """Remove a user as a follower of a show."""
        try:
            async with self.async_session() as session:
                stmt = self.follows.delete().where(
                    (self.follows.c.user_id == user_id) &
                    (self.follows.c.show_title == show_title)
                )
                result = await session.execute(stmt)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error removing follower: {str(e)}")
            return False

    async def get_user_follows(self, user_id: int) -> List[str]:
        """Get all shows a user is following."""
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(self.follows.c.show_title)
                    .where(self.follows.c.user_id == user_id)
                )
                shows = result.scalars().all()
                return shows
        except Exception as e:
            logger.error(f"Error getting user follows: {str(e)}")
            return [] 