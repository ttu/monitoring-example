"""Redis-backed rate limiter for production use."""
import logging
import time
from typing import Optional, Tuple
import redis
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from monitoring import rate_limit_exceeded_counter, suspicious_activity_counter

logger = logging.getLogger(__name__)


class RedisRateLimiter(BaseHTTPMiddleware):
    """
    Production-ready rate limiter using Redis for distributed rate limiting.

    Advantages over in-memory rate limiting:
    - Survives service restarts
    - Shared across multiple service instances (horizontal scaling)
    - Atomic operations prevent race conditions
    - Automatic TTL-based cleanup
    - Accurate sliding window implementation

    Implements dual-tier sliding window rate limiting:
    - Per IP: Higher limit (200 req/min) - handles shared IPs
    - Per user: Lower limit (60 req/min) - prevents individual abuse
    """

    def __init__(
        self,
        app,
        redis_client: redis.Redis,
        requests_per_minute_ip: int = 50000, # All request in demo are from a single IP
        requests_per_minute_user: int = 500,
        window_seconds: int = 60
    ):
        """
        Initialize Redis-backed rate limiter.

        Args:
            app: FastAPI application
            redis_client: Redis connection
            requests_per_minute_ip: Max requests per IP per minute
            requests_per_minute_user: Max requests per user per minute
            window_seconds: Sliding window size in seconds
        """
        super().__init__(app)
        self.redis = redis_client
        self.requests_per_minute_ip = requests_per_minute_ip
        self.requests_per_minute_user = requests_per_minute_user
        self.window_seconds = window_seconds

    def _check_rate_limit(
        self,
        key: str,
        limit: int,
        window: int
    ) -> Tuple[bool, int]:
        """
        Check rate limit using Redis sorted set (sliding window).

        Algorithm:
        1. Remove timestamps older than window
        2. Count requests in window
        3. Add current request
        4. Set TTL

        Args:
            key: Redis key for this limit (e.g., "rate:ip:192.168.1.1")
            limit: Maximum requests allowed
            window: Time window in seconds

        Returns:
            Tuple of (is_allowed, current_count)
        """
        try:
            current_time = time.time()
            window_start = current_time - window

            pipe = self.redis.pipeline()

            # Remove old entries (sliding window)
            pipe.zremrangebyscore(key, 0, window_start)

            # Count requests in window
            pipe.zcard(key)

            # Add current request with timestamp as score
            pipe.zadd(key, {str(current_time): current_time})

            # Set TTL to window + 1 second (auto cleanup)
            pipe.expire(key, window + 1)

            results = pipe.execute()

            # Get count BEFORE adding current request
            count = results[1]

            is_allowed = count < limit

            return is_allowed, count + 1

        except redis.RedisError as e:
            logger.error(f"Redis rate limit error: {e}")
            # Fail open: allow request if Redis is unavailable
            return True, 0

    async def dispatch(self, request: Request, call_next):
        """
        Process request with Redis-backed dual-tier rate limiting.

        Args:
            request: Incoming request
            call_next: Next middleware in chain

        Returns:
            Response or 429 if rate limited
        """
        # Get client IP
        client_ip = request.client.host
        if "x-forwarded-for" in request.headers:
            client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()

        # Extract user ID from auth header
        user_id = None
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            user_id = f"user_{token[:10]}"

        # --- IP-based rate limiting ---
        ip_key = f"rate:ip:{client_ip}"
        ip_allowed, ip_count = self._check_rate_limit(
            ip_key,
            self.requests_per_minute_ip,
            self.window_seconds
        )

        if not ip_allowed:
            rate_limit_exceeded_counter.add(1, {
                "limit_type": "ip",
                "client_ip": client_ip
            })
            logger.warning(
                f"Rate limit exceeded for IP {client_ip}: "
                f"{ip_count}/{self.requests_per_minute_ip} requests"
            )
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded for IP. Maximum {self.requests_per_minute_ip} requests per minute.",
                headers={"Retry-After": str(self.window_seconds)}
            )

        # --- User-based rate limiting ---
        if user_id:
            user_key = f"rate:user:{user_id}"
            user_allowed, user_count = self._check_rate_limit(
                user_key,
                self.requests_per_minute_user,
                self.window_seconds
            )

            if not user_allowed:
                rate_limit_exceeded_counter.add(1, {
                    "limit_type": "user",
                    "user_id": user_id
                })
                logger.warning(
                    f"Rate limit exceeded for user {user_id}: "
                    f"{user_count}/{self.requests_per_minute_user} requests"
                )
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for user. Maximum {self.requests_per_minute_user} requests per minute.",
                    headers={"Retry-After": str(self.window_seconds)}
                )

        # Process request
        response = await call_next(request)

        # Detect suspicious activity patterns
        await self._detect_suspicious_activity(request, response, client_ip, user_id)

        return response

    async def _detect_suspicious_activity(
        self,
        request: Request,
        response,
        client_ip: str,
        user_id: Optional[str]
    ):
        """
        Detect suspicious activity patterns using Redis.

        Patterns:
        - Credential stuffing: 5+ failed auths in 5 minutes
        - Endpoint scanning: 10+ 404s in 5 minutes
        - Abuse: 20+ 4xx errors in 5 minutes
        """
        try:
            current_time = time.time()
            window = 300  # 5 minutes

            # Pattern 1: Credential stuffing (401s)
            if response.status_code == 401:
                key = f"suspicious:401:{client_ip}"
                self.redis.zadd(key, {str(current_time): current_time})
                self.redis.expire(key, window + 1)

                count = self.redis.zcount(key, current_time - window, current_time)
                if count >= 5:
                    suspicious_activity_counter.add(1, {
                        "type": "credential_stuffing",
                        "client_ip": client_ip
                    })
                    logger.warning(
                        f"Suspicious activity: Credential stuffing from {client_ip} "
                        f"({count} failed auths in 5 min)"
                    )

            # Pattern 2: Endpoint scanning (404s)
            if response.status_code == 404:
                key = f"suspicious:404:{client_ip}"
                self.redis.zadd(key, {str(current_time): current_time})
                self.redis.expire(key, window + 1)

                count = self.redis.zcount(key, current_time - window, current_time)
                if count >= 10:
                    suspicious_activity_counter.add(1, {
                        "type": "endpoint_scanning",
                        "client_ip": client_ip
                    })
                    logger.warning(
                        f"Suspicious activity: Endpoint scanning from {client_ip} "
                        f"({count} 404s in 5 min)"
                    )

            # Pattern 3: General abuse (4xx errors)
            if 400 <= response.status_code < 500:
                key = f"suspicious:4xx:{client_ip}"
                self.redis.zadd(key, {str(current_time): current_time})
                self.redis.expire(key, window + 1)

                count = self.redis.zcount(key, current_time - window, current_time)
                if count >= 20:
                    suspicious_activity_counter.add(1, {
                        "type": "abuse",
                        "client_ip": client_ip
                    })
                    logger.warning(
                        f"Suspicious activity: Abuse from {client_ip} "
                        f"({count} 4xx errors in 5 min)"
                    )

        except redis.RedisError as e:
            logger.error(f"Error detecting suspicious activity: {e}")
