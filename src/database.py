from sqlalchemy import create_engine, Column, Integer, String, Table, MetaData, ForeignKey, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from typing import List, Dict, Optional

Base = declarative_base()

class Subscription(Base):
    __tablename__ = 'subscriptions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False)
    show_id = Column(Integer, nullable=False)
    show_name = Column(String, nullable=False)

class Database:
    def __init__(self):
        self.engine = create_async_engine(
            os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///data/followarr.db'),
            echo=True
        )
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def add_subscription(self, user_id: str, show_id: int, show_name: str) -> bool:
        """Add a show subscription for a user"""
        async with self.async_session() as session:
            # Check if subscription already exists
            stmt = select(Subscription).where(
                Subscription.user_id == str(user_id),
                Subscription.show_id == show_id
            )
            result = await session.execute(stmt)
            if result.scalar_one_or_none():
                return False

            # Add new subscription
            subscription = Subscription(
                user_id=str(user_id),
                show_id=show_id,
                show_name=show_name
            )
            session.add(subscription)
            await session.commit()
            return True

    async def remove_subscription(self, user_id: str, show_id: int) -> bool:
        """Remove a show subscription for a user"""
        async with self.async_session() as session:
            stmt = select(Subscription).where(
                Subscription.user_id == str(user_id),
                Subscription.show_id == show_id
            )
            result = await session.execute(stmt)
            subscription = result.scalar_one_or_none()
            
            if subscription:
                await session.delete(subscription)
                await session.commit()
                return True
            return False

    async def get_user_subscriptions(self, user_id: str) -> List[Dict]:
        """Get all shows a user is subscribed to"""
        async with self.async_session() as session:
            stmt = select(Subscription).where(Subscription.user_id == str(user_id))
            result = await session.execute(stmt)
            subscriptions = result.scalars().all()
            
            return [
                {
                    'id': sub.show_id,
                    'name': sub.show_name
                }
                for sub in subscriptions
            ]

    async def get_show_subscribers(self, show_id: int) -> List[str]:
        """Get all users subscribed to a show"""
        async with self.async_session() as session:
            stmt = select(Subscription).where(Subscription.show_id == show_id)
            result = await session.execute(stmt)
            subscriptions = result.scalars().all()
            
            return [sub.user_id for sub in subscriptions]

    async def is_user_subscribed(self, user_id: str, show_id: int) -> bool:
        """Check if a user is subscribed to a show"""
        async with self.async_session() as session:
            stmt = select(Subscription).where(
                Subscription.user_id == str(user_id),
                Subscription.show_id == show_id
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None 