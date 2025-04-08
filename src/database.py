from sqlalchemy import create_engine, Column, Integer, String, select
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()

class Subscription(Base):
    __tablename__ = 'subscriptions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False)
    show_id = Column(Integer, nullable=False)
    show_name = Column(String, nullable=False)

class Database:
    def __init__(self):
        # Use absolute path inside the container for clarity
        database_url = os.getenv('DATABASE_URL', 'sqlite:////app/data/followarr.db')
        logger.info(f"Using database URL: {database_url}")
        
        # Ensure the directory exists before creating the engine
        db_dir = os.path.dirname(database_url.replace('sqlite:///', ''))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
            
        self.engine = create_engine(database_url)
        self.Session = sessionmaker(bind=self.engine)

    def init_db(self):
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