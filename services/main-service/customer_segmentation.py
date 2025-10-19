"""Customer segmentation logic for analytics and personalization."""
from typing import Dict, Optional
from datetime import datetime, timedelta
import redis.asyncio as redis
import logging

logger = logging.getLogger(__name__)


class CustomerSegmentationService:
    """
    Tracks customer behavior and assigns segments for analytics.

    Segments:
    - new: First-time visitor (no previous activity)
    - returning: Has activity in last 30 days
    - vip: High-value customer (>$500 total spend or >5 orders)
    - at_risk: Was active but no activity in 30-90 days
    - churned: No activity in 90+ days
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.ttl_days = 90  # Track customer data for 90 days

    def _get_customer_key(self, user_id: str) -> str:
        """Generate Redis key for customer data."""
        return f"customer:{user_id}"

    async def get_customer_segment(self, user_id: str) -> str:
        """
        Determine customer segment based on behavior.

        Returns:
            str: Segment name (new, returning, vip, at_risk, churned)
        """
        try:
            key = self._get_customer_key(user_id)
            customer_data = await self.redis_client.hgetall(key)

            if not customer_data:
                # First time visitor
                return "new"

            # Handle Redis byte strings (decode if bytes, else use as-is for redis-py 5.x)
            data = {
                (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
                for k, v in customer_data.items()
            }

            # Get last activity
            last_activity_str = data.get("last_activity")
            if not last_activity_str:
                return "new"

            last_activity = datetime.fromisoformat(last_activity_str)
            days_since_activity = (datetime.now() - last_activity).days

            # Get customer metrics
            total_spend = float(data.get("total_spend", 0))
            order_count = int(data.get("order_count", 0))

            # VIP customers: High spend or frequent buyers
            if total_spend > 500 or order_count > 5:
                return "vip"

            # Activity-based segmentation
            if days_since_activity <= 30:
                return "returning"
            elif days_since_activity <= 90:
                return "at_risk"
            else:
                return "churned"

        except Exception as e:
            logger.error(f"Error getting customer segment: {e}")
            return "unknown"

    async def record_activity(
        self,
        user_id: str,
        activity_type: str,
        amount: Optional[float] = None
    ) -> None:
        """
        Record customer activity and update segment data.

        Args:
            user_id: Customer identifier
            activity_type: Type of activity (browse, view_product, add_to_cart, checkout)
            amount: Transaction amount (for checkouts)
        """
        try:
            key = self._get_customer_key(user_id)
            pipe = self.redis_client.pipeline()

            # Update last activity
            pipe.hset(key, "last_activity", datetime.now().isoformat())

            # Increment activity counter
            activity_key = f"activity_{activity_type}"
            pipe.hincrby(key, activity_key, 1)

            # Update spend and order count for checkouts
            if activity_type == "checkout" and amount:
                pipe.hincrbyfloat(key, "total_spend", amount)
                pipe.hincrby(key, "order_count", 1)

            # Set TTL
            pipe.expire(key, self.ttl_days * 24 * 60 * 60)

            await pipe.execute()

        except Exception as e:
            logger.error(f"Error recording customer activity: {e}")

    async def get_customer_stats(self, user_id: str) -> Dict:
        """
        Get customer statistics for analytics.

        Returns:
            dict: Customer stats including segment, spend, activity counts
        """
        try:
            key = self._get_customer_key(user_id)
            customer_data = await self.redis_client.hgetall(key)

            if not customer_data:
                return {
                    "segment": "new",
                    "total_spend": 0,
                    "order_count": 0,
                    "activities": {}
                }

            # Handle Redis byte strings (decode if bytes, else use as-is for redis-py 5.x)
            data = {
                (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
                for k, v in customer_data.items()
            }

            # Extract activities
            activities = {
                k.replace("activity_", ""): int(v)
                for k, v in data.items()
                if k.startswith("activity_")
            }

            return {
                "segment": await self.get_customer_segment(user_id),
                "total_spend": float(data.get("total_spend", 0)),
                "order_count": int(data.get("order_count", 0)),
                "last_activity": data.get("last_activity"),
                "activities": activities
            }

        except Exception as e:
            logger.error(f"Error getting customer stats: {e}")
            return {"segment": "unknown", "error": str(e)}
