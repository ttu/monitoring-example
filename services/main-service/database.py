"""Database connection and session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import logging

from config import DATABASE_URL
from models import Base, Product

logger = logging.getLogger(__name__)

# Create engine with connection pool settings
engine = create_engine(
    DATABASE_URL,
    pool_size=10,  # Moderate pool size for 50 concurrent users
    max_overflow=20,  # Increased overflow for burst traffic
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_timeout=30,  # Wait max 30 seconds for a connection
    echo_pool=False  # Set to True for debugging connection pool
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for getting database session.

    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables and seed data."""
    Base.metadata.create_all(bind=engine)

    # Seed data if empty
    db = SessionLocal()
    try:
        if db.query(Product).count() == 0:
            products = [
                Product(name="Laptop", price=999.99, stock=50, category="Electronics"),
                Product(name="Smartphone", price=599.99, stock=100, category="Electronics"),
                Product(name="Headphones", price=99.99, stock=200, category="Electronics"),
                Product(name="Desk Chair", price=199.99, stock=30, category="Furniture"),
                Product(name="Monitor", price=299.99, stock=75, category="Electronics"),
                Product(name="Keyboard", price=79.99, stock=150, category="Electronics"),
                Product(name="Mouse", price=29.99, stock=300, category="Electronics"),
                Product(name="Webcam", price=89.99, stock=100, category="Electronics"),
            ]
            db.add_all(products)
            db.commit()
            logger.info("Seeded database with sample products")
    finally:
        db.close()
