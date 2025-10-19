"""Security monitoring and rate limiting."""
import logging
import time
from typing import Dict, Tuple
from collections import defaultdict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from monitoring import rate_limit_exceeded_counter, suspicious_activity_counter

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware to prevent abuse.

    Implements dual-tier sliding window rate limiting:
    - Per IP: Higher limit (200 req/min) - handles shared IPs (corporate, CGNAT)
    - Per user: Lower limit (60 req/min) - prevents individual user abuse

    Rationale:
    - IP-based limits must be high since many users may share same IP:
      * Corporate networks (100s of employees)
      * ISP CGNAT (Carrier-Grade NAT - 1000s of customers)
      * Public WiFi (coffee shops, airports)
    - User-based limits are stricter since we can identify individual users
      * Prevents single user from monopolizing resources
      * More granular abuse detection
    """

    def __init__(
        self,
        app,
        requests_per_minute_ip: int = 200,
        requests_per_minute_user: int = 60
    ):
        """
        Initialize rate limiter.

        Args:
            app: FastAPI application
            requests_per_minute_ip: Maximum requests per IP per minute (shared IPs)
            requests_per_minute_user: Maximum requests per authenticated user per minute
        """
        super().__init__(app)
        self.requests_per_minute_ip = requests_per_minute_ip
        self.requests_per_minute_user = requests_per_minute_user
        self.request_counts: Dict[str, list] = defaultdict(list)
        
    async def dispatch(self, request: Request, call_next):
        """
        Process request with dual-tier rate limiting.

        Checks both IP-based and user-based rate limits.

        Args:
            request: Incoming request
            call_next: Next middleware in chain

        Returns:
            Response or 429 if rate limited
        """
        # Get client IP (handle proxy headers)
        client_ip = request.client.host
        if "x-forwarded-for" in request.headers:
            client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()

        # Extract user ID from authorization header if present
        user_id = None
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            # Extract user ID from token (same logic as auth.py)
            user_id = f"user_{token[:10]}"

        current_time = time.time()

        # --- IP-based rate limiting (high limit for shared IPs) ---
        ip_key = f"ip:{client_ip}"
        self.request_counts[ip_key] = [
            timestamp for timestamp in self.request_counts[ip_key]
            if current_time - timestamp < 60
        ]

        if len(self.request_counts[ip_key]) >= self.requests_per_minute_ip:
            rate_limit_exceeded_counter.add(1, {
                "endpoint": request.url.path,
                "limit_type": "ip",
                "client_ip": client_ip
            })

            logger.warning("IP rate limit exceeded", extra={
                "client_ip": client_ip,
                "endpoint": request.url.path,
                "requests_in_minute": len(self.request_counts[ip_key]),
                "limit": self.requests_per_minute_ip
            })

            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded for IP. Maximum {self.requests_per_minute_ip} requests per minute.",
                headers={"Retry-After": "60"}
            )

        self.request_counts[ip_key].append(current_time)

        # --- User-based rate limiting (strict limit per authenticated user) ---
        if user_id:
            user_key = f"user:{user_id}"
            self.request_counts[user_key] = [
                timestamp for timestamp in self.request_counts[user_key]
                if current_time - timestamp < 60
            ]

            if len(self.request_counts[user_key]) >= self.requests_per_minute_user:
                rate_limit_exceeded_counter.add(1, {
                    "endpoint": request.url.path,
                    "limit_type": "user",
                    "user_id": user_id
                })

                logger.warning("User rate limit exceeded", extra={
                    "user_id": user_id,
                    "client_ip": client_ip,
                    "endpoint": request.url.path,
                    "requests_in_minute": len(self.request_counts[user_key]),
                    "limit": self.requests_per_minute_user
                })

                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for user. Maximum {self.requests_per_minute_user} requests per minute.",
                    headers={"Retry-After": "60"}
                )

            self.request_counts[user_key].append(current_time)

        # Continue processing
        response = await call_next(request)

        # Detect suspicious patterns
        await self._detect_suspicious_activity(request, response, client_ip, user_id)

        return response
    
    async def _detect_suspicious_activity(
        self,
        request: Request,
        response,
        client_ip: str
    ):
        """
        Detect suspicious activity patterns.
        
        Args:
            request: The request
            response: The response
            client_ip: Client IP address
        """
        # Pattern 1: High rate of 401s (credential stuffing)
        if response.status_code == 401:
            recent_401s = sum(
                1 for _ in self.request_counts.get(f"{client_ip}_401", [])
                if time.time() - _ < 300  # Last 5 minutes
            )
            
            if recent_401s >= 5:
                suspicious_activity_counter.add(1, {
                    "type": "credential_stuffing",
                    "client_ip": client_ip
                })
                logger.error("Suspicious activity detected: Possible credential stuffing", extra={
                    "client_ip": client_ip,
                    "failed_auth_count": recent_401s,
                    "endpoint": request.url.path
                })
            
            # Track 401 for this IP
            if f"{client_ip}_401" not in self.request_counts:
                self.request_counts[f"{client_ip}_401"] = []
            self.request_counts[f"{client_ip}_401"].append(time.time())
        
        # Pattern 2: Accessing non-existent endpoints (scanning)
        if response.status_code == 404:
            recent_404s = sum(
                1 for _ in self.request_counts.get(f"{client_ip}_404", [])
                if time.time() - _ < 300  # Last 5 minutes
            )
            
            if recent_404s >= 10:
                suspicious_activity_counter.add(1, {
                    "type": "endpoint_scanning",
                    "client_ip": client_ip
                })
                logger.error("Suspicious activity detected: Possible endpoint scanning", extra={
                    "client_ip": client_ip,
                    "not_found_count": recent_404s,
                    "endpoint": request.url.path
                })
            
            # Track 404 for this IP
            if f"{client_ip}_404" not in self.request_counts:
                self.request_counts[f"{client_ip}_404"] = []
            self.request_counts[f"{client_ip}_404"].append(time.time())
        
        # Pattern 3: High rate of 4xx errors (abuse)
        if 400 <= response.status_code < 500:
            recent_4xx = sum(
                1 for _ in self.request_counts.get(f"{client_ip}_4xx", [])
                if time.time() - _ < 300  # Last 5 minutes
            )
            
            if recent_4xx >= 20:
                suspicious_activity_counter.add(1, {
                    "type": "abuse",
                    "client_ip": client_ip
                })
                logger.error("Suspicious activity detected: High rate of client errors", extra={
                    "client_ip": client_ip,
                    "error_count": recent_4xx,
                    "status_code": response.status_code
                })
            
            # Track 4xx for this IP
            if f"{client_ip}_4xx" not in self.request_counts:
                self.request_counts[f"{client_ip}_4xx"] = []
            self.request_counts[f"{client_ip}_4xx"].append(time.time())
