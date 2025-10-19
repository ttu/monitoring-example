"""Cart management service."""
import logging
import asyncio
import random
from typing import List, Dict, Any
from sqlalchemy.orm import Session
import redis
from opentelemetry import trace

from models import CartItem, Product
from monitoring import cart_additions_counter

logger = logging.getLogger(__name__)


class CartService:
    """Service for managing shopping carts."""

    def __init__(self, redis_client: redis.Redis):
        """
        Initialize cart service.

        Args:
            redis_client: Redis client for caching
        """
        self.redis_client = redis_client
        self.tracer = trace.get_tracer(__name__)

    def add_to_cart(
        self,
        db: Session,
        user_id: str,
        product_id: int,
        quantity: int,
        country: str
    ) -> Dict[str, Any]:
        """
        Add item to user's cart.

        Args:
            db: Database session
            user_id: User identifier
            product_id: Product identifier
            quantity: Quantity to add
            country: Country code

        Returns:
            Result with cart item details

        Raises:
            ValueError: If product not found or insufficient stock
        """
        # FastAPIInstrumentor already creates spans for HTTP endpoints
        span = trace.get_current_span()
        span.set_attribute("product.id", product_id)
        span.set_attribute("quantity", quantity)
        span.set_attribute("country", country)

        # Simulate database query delay (50-200ms)
        import time
        time.sleep(random.uniform(0.05, 0.2))

        # Verify product exists
        with self.tracer.start_as_current_span("db.query.get_product") as db_span:
            db_span.set_attribute("db.operation", "SELECT")
            db_span.set_attribute("db.table", "products")
            db_span.set_attribute("product.id", product_id)

            product = db.query(Product).filter(Product.id == product_id).first()

            if product:
                db_span.set_attribute("db.rows_returned", 1)
            else:
                db_span.set_attribute("db.rows_returned", 0)
                raise ValueError("Product not found")

        # OPTIMISTIC CART APPROACH:
        # We verify the product exists but DON'T check stock availability here.
        # Cart is a "wishlist" - customers can add items regardless of current stock.
        #
        # Rationale:
        # 1. Stock changes frequently (other customers buying, restocks)
        # 2. Checking stock at cart-add time creates poor UX (item appears available,
        #    but shows "out of stock" when adding - then becomes available again)
        # 3. Real availability check happens at checkout when payment is imminent
        # 4. Matches customer expectations: "Add to cart" means "I'm interested"
        #
        # Stock validation happens during checkout via inventory-system.

        # Add to cart
        with self.tracer.start_as_current_span("db.query.insert_cart_item") as db_span:
            db_span.set_attribute("db.operation", "INSERT")
            db_span.set_attribute("db.table", "cart_items")
            db_span.set_attribute("user.id", user_id)
            db_span.set_attribute("product.id", product_id)

            cart_item = CartItem(
                user_id=user_id,
                product_id=product_id,
                quantity=quantity,
                country=country
            )
            db.add(cart_item)
            db.commit()

            db_span.set_attribute("cart_item.id", cart_item.id)

        # Update cache
        cache_key = f"cart:{user_id}"
        with self.tracer.start_as_current_span("cache.incr") as cache_span:
            cache_span.set_attribute("cache.system", "redis")
            cache_span.set_attribute("cache.operation", "INCR")
            cache_span.set_attribute("cache.key", cache_key)

            self.redis_client.incr(cache_key)
            self.redis_client.expire(cache_key, 3600)

            cache_span.set_attribute("cache.ttl", 3600)

        # Record metrics using OpenTelemetry
        cart_additions_counter.add(
            1,
            {
                "country": country,
                "product_id": str(product_id)
            }
        )

        logger.info("Added product to cart", extra={
            "user_id": user_id,
            "product_id": product_id,
            "product_name": product.name,
            "quantity": quantity,
            "country": country
        })

        return {
            "cart_item_id": cart_item.id,
            "product_name": product.name
        }

    def get_cart(self, db: Session, user_id: str) -> Dict[str, Any]:
        """
        Get user's cart contents.

        Args:
            db: Database session
            user_id: User identifier

        Returns:
            Cart contents with items and total
        """
        # Get cart items
        with self.tracer.start_as_current_span("db.query.get_cart_items") as db_span:
            db_span.set_attribute("db.operation", "SELECT")
            db_span.set_attribute("db.table", "cart_items")
            db_span.set_attribute("user.id", user_id)

            cart_items = db.query(CartItem).filter(
                CartItem.user_id == user_id
            ).all()

            db_span.set_attribute("db.rows_returned", len(cart_items))

        items = []
        total = 0.0

        for item in cart_items:
            with self.tracer.start_as_current_span("db.query.get_product") as db_span:
                db_span.set_attribute("db.operation", "SELECT")
                db_span.set_attribute("db.table", "products")
                db_span.set_attribute("product.id", item.product_id)

                product = db.query(Product).filter(
                    Product.id == item.product_id
                ).first()

                if product:
                    db_span.set_attribute("db.rows_returned", 1)
                    item_total = product.price * item.quantity
                    total += item_total
                    items.append({
                        "id": item.id,
                        "product_id": product.id,
                        "product_name": product.name,
                        "price": product.price,
                        "quantity": item.quantity,
                        "subtotal": item_total
                    })
                else:
                    db_span.set_attribute("db.rows_returned", 0)

        return {
            "user_id": user_id,
            "items": items,
            "total": total
        }

    def clear_cart(self, db: Session, user_id: str) -> None:
        """
        Clear user's cart.

        Args:
            db: Database session
            user_id: User identifier
        """
        with self.tracer.start_as_current_span("db.query.delete_cart_items") as db_span:
            db_span.set_attribute("db.operation", "DELETE")
            db_span.set_attribute("db.table", "cart_items")
            db_span.set_attribute("user.id", user_id)

            cart_items = db.query(CartItem).filter(
                CartItem.user_id == user_id
            ).all()

            deleted_count = len(cart_items)
            for item in cart_items:
                db.delete(item)

            db_span.set_attribute("db.rows_affected", deleted_count)

        # Update cache
        cache_key = f"cart:{user_id}"
        with self.tracer.start_as_current_span("cache.delete") as cache_span:
            cache_span.set_attribute("cache.system", "redis")
            cache_span.set_attribute("cache.operation", "DELETE")
            cache_span.set_attribute("cache.key", cache_key)

            self.redis_client.delete(cache_key)

    def get_cart_items(self, db: Session, user_id: str) -> List[CartItem]:
        """
        Get cart items for user.

        Args:
            db: Database session
            user_id: User identifier

        Returns:
            List of cart items
        """
        with self.tracer.start_as_current_span("db.query.get_cart_items") as db_span:
            db_span.set_attribute("db.operation", "SELECT")
            db_span.set_attribute("db.table", "cart_items")
            db_span.set_attribute("user.id", user_id)

            cart_items = db.query(CartItem).filter(CartItem.user_id == user_id).all()

            db_span.set_attribute("db.rows_returned", len(cart_items))

            return cart_items
