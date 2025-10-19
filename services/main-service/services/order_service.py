"""Order management service."""
import logging
import time
import random
from typing import Dict, Any, List
from sqlalchemy.orm import Session
import httpx
from opentelemetry import trace

from models import Order, Product
from services.cart_service import CartService
from services.external_service import ExternalServiceClient
from database import SessionLocal
from monitoring import (
    checkout_counter,
    checkout_amount_histogram,
    payment_duration_histogram,
    inventory_reservation_failures_counter,
    orders_delayed_fulfillment_counter,
    orders_cancelled_out_of_stock_counter
)

logger = logging.getLogger(__name__)


class OrderService:
    """Service for managing orders."""

    def __init__(
        self,
        cart_service: CartService,
        external_service: ExternalServiceClient
    ):
        """
        Initialize order service.

        Args:
            cart_service: Cart service instance
            external_service: External service client
        """
        self.cart_service = cart_service
        self.external_service = external_service
        self.tracer = trace.get_tracer(__name__)

    async def process_checkout(
        self,
        db: Session,
        user_id: str,
        payment_method: str,
        country: str
    ) -> Dict[str, Any]:
        """
        Process checkout for user's cart.

        Args:
            db: Database session
            user_id: User identifier
            payment_method: Payment method
            country: Country code

        Returns:
            Checkout result with order details

        Raises:
            ValueError: If cart is empty
            httpx.HTTPError: If payment processing fails
        """
        span = trace.get_current_span()
        span.set_attribute("payment.method", payment_method)
        span.set_attribute("country", country)

        # Simulate processing delay (100-300ms)
        time.sleep(random.uniform(0.1, 0.3))

        # Step 1: Load cart and product data (with DB connection)
        cart_items = self.cart_service.get_cart_items(db, user_id)
        if not cart_items:
            raise ValueError("Cart is empty")

        # Load all product data into memory
        products_data = []
        for item in cart_items:
            with self.tracer.start_as_current_span("db.query.get_product") as db_span:
                db_span.set_attribute("db.operation", "SELECT")
                db_span.set_attribute("db.table", "products")
                db_span.set_attribute("product.id", item.product_id)

                # Occasionally simulate slow database query (5% chance, 500-1500ms)
                if random.random() < 0.05:
                    delay = random.uniform(0.5, 1.5)
                    time.sleep(delay)
                    db_span.set_attribute("db.query.slow", True)
                    db_span.set_attribute("db.query.duration_ms", int(delay * 1000))
                    logger.warning("Slow database query", extra={
                        "product_id": item.product_id,
                        "delay_ms": int(delay * 1000)
                    })

                product = db.query(Product).filter(
                    Product.id == item.product_id
                ).first()

                if product:
                    db_span.set_attribute("db.rows_returned", 1)
                    products_data.append({
                        "product_id": product.id,
                        "product_name": product.name,
                        "price": product.price,
                        "quantity": item.quantity,
                        "cart_item": item
                    })
                else:
                    db_span.set_attribute("db.rows_returned", 0)

        # Remove objects from session to free connection before external calls
        # This prevents holding the connection during slow external API calls
        db.expunge_all()

        # Step 2: Make external API calls (WITHOUT holding DB connection)
        total_amount = 0.0
        order_items = []
        inventory_warnings = []

        # NOTE: Optimistic inventory approach
        # We check inventory availability but DON'T block the order if unavailable.
        # This is intentional to maximize sales (see detailed comment in Step 4).
        for prod_data in products_data:
            # Check inventory availability (advisory only, not blocking)
            inventory_data = await self.external_service.check_inventory(
                product_id=prod_data["product_id"],
                quantity=prod_data["quantity"],
                country=country
            )

            if inventory_data and not inventory_data.get("available", False):
                # Log warning but continue with order
                # Business decision: Capture sale now, fulfill later if needed
                inventory_warnings.append(
                    f"Product {prod_data['product_name']} may be out of stock or delayed"
                )
                logger.warning("Inventory not available in preferred warehouses", extra={
                    "product_id": prod_data['product_id'],
                    "product_name": prod_data['product_name'],
                    "country": country
                })

            total_amount += prod_data["price"] * prod_data["quantity"]
            order_items.append({
                "product_id": prod_data["product_id"],
                "quantity": prod_data["quantity"],
                "price": prod_data["price"],
                "inventory_status": inventory_data,
                "cart_item": prod_data["cart_item"]
            })

        # Check for promotions
        promo_data = await self.external_service.check_promotions(
            user_id, country, total_amount
        )

        if promo_data:
            discount = promo_data.get("discount", 0)
            total_amount -= discount
            logger.info("Applied promotion discount", extra={
                "user_id": user_id,
                "discount_amount": discount,
                "promo_code": promo_data.get("promo_code"),
                "country": country
            })

        # Process payment
        payment_start = time.time()

        try:
            payment_data = await self.external_service.process_payment(
                user_id=user_id,
                amount=total_amount,
                currency="USD",
                country=country,
                payment_method=payment_method
            )

            payment_duration_histogram.record(
                time.time() - payment_start,
                {
                    "country": country,
                    "payment_method": payment_method
                }
            )

        except httpx.HTTPError as e:
            checkout_counter.add(
                1,
                {
                    "country": country,
                    "payment_method": payment_method,
                    "status": "failed"
                }
            )
            logger.error("Payment service error", extra={
                "user_id": user_id,
                "amount": total_amount,
                "payment_method": payment_method,
                "country": country,
                "error": str(e)
            })
            raise

        # Step 3: Create order and update database (use original session)
        # Re-use the dependency-injected session for database writes
        try:
            with self.tracer.start_as_current_span("db.transaction.create_order") as db_span:
                db_span.set_attribute("db.operation", "INSERT")
                db_span.set_attribute("db.table", "orders")
                db_span.set_attribute("user.id", user_id)
                db_span.set_attribute("order.total_amount", total_amount)

                # Create order
                order = Order(
                    user_id=user_id,
                    total_amount=total_amount,
                    country=country,
                    payment_method=payment_method,
                    status="completed"
                )
                db.add(order)

                # Update product stock
                for item_data in order_items:
                    with self.tracer.start_as_current_span("db.query.update_product_stock") as update_span:
                        update_span.set_attribute("db.operation", "UPDATE")
                        update_span.set_attribute("db.table", "products")
                        update_span.set_attribute("product.id", item_data["product_id"])

                        product = db.query(Product).filter(
                            Product.id == item_data["product_id"]
                        ).first()
                        if product:
                            old_stock = product.stock
                            product.stock -= item_data["quantity"]
                            update_span.set_attribute("product.stock.before", old_stock)
                            update_span.set_attribute("product.stock.after", product.stock)
                            update_span.set_attribute("db.rows_affected", 1)

                # Clear cart
                self.cart_service.clear_cart(db, user_id)

                db.commit()
                order_id = order.id
                db_span.set_attribute("order.id", order_id)
        except Exception as e:
            db.rollback()
            logger.error("Failed to create order", extra={
                "user_id": user_id,
                "amount": total_amount,
                "payment_method": payment_method,
                "country": country,
                "error": str(e)
            })
            raise

        # Step 4: Post-commit external calls (without DB connection)
        #
        # OPTIMISTIC INVENTORY STRATEGY:
        # We intentionally process payment BEFORE confirming warehouse inventory availability.
        # This is a business decision to maximize sales conversion:
        #
        # - The inventory-system check earlier (Step 2) is advisory, not blocking
        # - We complete the sale even if specific warehouses show low stock
        # - Post-order reservation may fail, but we've already captured payment
        #
        # Rationale:
        # 1. Inventory often updates quickly (restocks, returns, transfers)
        # 2. We may find product in alternative warehouses
        # 3. Worst case: We fulfill order in 1-2 extra days vs losing the sale
        # 4. Customer experience: "Order confirmed" feels better than "Out of stock"
        #
        # Tradeoff: Occasional fulfillment delays vs higher conversion rate
        #
        # In production, you'd monitor:
        # - Reservation failure rate
        # - Customer complaints about delays
        # - Actual out-of-stock cancellations
        #
        # If metrics are acceptable, this optimistic approach increases revenue.

        # Reserve inventory for order items
        reservation_failures = 0
        for item_data in order_items:
            reservation = await self.external_service.reserve_inventory(
                product_id=item_data["product_id"],
                quantity=item_data["quantity"],
                country=country,
                order_id=order_id
            )
            if reservation:
                logger.info("Reserved inventory", extra={
                    "order_id": order_id,
                    "product_id": item_data['product_id'],
                    "quantity": item_data['quantity'],
                    "reservation_id": reservation.get('reservation_id'),
                    "country": country
                })
            else:
                # Reservation failed - track this critical metric
                reservation_failures += 1
                inventory_reservation_failures_counter.add(
                    1,
                    {
                        "country": country,
                        "product_id": str(item_data["product_id"])
                    }
                )
                logger.error("Inventory reservation failed after payment", extra={
                    "order_id": order_id,
                    "product_id": item_data['product_id'],
                    "quantity": item_data['quantity'],
                    "country": country
                })

        # If any reservations failed, mark order for delayed fulfillment
        if reservation_failures > 0:
            orders_delayed_fulfillment_counter.add(
                1,
                {
                    "country": country,
                    "failure_count": str(reservation_failures)
                }
            )
            logger.warning("Order marked for delayed fulfillment", extra={
                "order_id": order_id,
                "failed_reservations": reservation_failures,
                "country": country
            })

            # In production, this would trigger:
            # - Alternative warehouse lookup
            # - Supplier dropship request
            # - Customer notification of delay
            # - Rarely: Order cancellation + refund
            #
            # Simulate: ~20% of delayed orders eventually get cancelled
            # (customer doesn't want to wait, needs item urgently, etc.)
            if random.random() < 0.20:
                orders_cancelled_out_of_stock_counter.add(
                    1,
                    {
                        "country": country,
                        "failed_reservations": str(reservation_failures)
                    }
                )
                logger.error("Order cancelled due to inventory unavailability", extra={
                    "order_id": order_id,
                    "failed_reservations": reservation_failures,
                    "country": country,
                    "reason": "customer_cancelled_due_to_delay"
                })
            #
            # This should be <0.1% of orders. If higher, the optimistic
            # inventory strategy should be reconsidered.

        # Update CRM (fire and forget)
        await self.external_service.update_crm(
            user_id, order_id, total_amount, country
        )

        # Record metrics
        checkout_counter.add(
            1,
            {
                "country": country,
                "payment_method": payment_method,
                "status": "completed"
            }
        )

        checkout_amount_histogram.record(
            total_amount,
            {
                "country": country,
                "payment_method": payment_method
            }
        )

        logger.info("Checkout completed", extra={
            "user_id": user_id,
            "order_id": order_id,
            "amount": total_amount,
            "payment_method": payment_method,
            "country": country,
            "payment_transaction_id": payment_data.get("transaction_id"),
            "item_count": len(order_items)
        })

        return {
            "order_id": order_id,
            "total_amount": total_amount,
            "payment_transaction_id": payment_data.get("transaction_id")
        }

    def get_user_orders(self, db: Session, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all orders for a user.

        Args:
            db: Database session
            user_id: User identifier

        Returns:
            List of orders
        """
        with self.tracer.start_as_current_span("db.query.get_user_orders") as db_span:
            db_span.set_attribute("db.operation", "SELECT")
            db_span.set_attribute("db.table", "orders")
            db_span.set_attribute("user.id", user_id)

            orders = db.query(Order).filter(Order.user_id == user_id).all()

            db_span.set_attribute("db.rows_returned", len(orders))

            return [
                {
                    "id": order.id,
                    "total_amount": order.total_amount,
                    "country": order.country,
                    "payment_method": order.payment_method,
                    "status": order.status,
                    "created_at": order.created_at.isoformat()
                }
                for order in orders
            ]
