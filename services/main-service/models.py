"""Database models for the main service."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Product(Base):
    """Product model."""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    price = Column(Float)
    stock = Column(Integer)
    category = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class CartItem(Base):
    """Cart item model."""
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    product_id = Column(Integer)
    quantity = Column(Integer)
    country = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class Order(Base):
    """Order model."""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    total_amount = Column(Float)
    country = Column(String)
    payment_method = Column(String)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
