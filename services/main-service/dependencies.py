"""Dependency injection for services."""
from typing import Any
import redis
import httpx
from fastapi import Request

from services.cart_service import CartService
from services.order_service import OrderService
from services.external_service import ExternalServiceClient
from customer_segmentation import CustomerSegmentationService


def get_redis_client(request: Request) -> Any:
    """Get Redis client from app state."""
    return request.app.state.redis_client


def get_redis(request: Request) -> redis.Redis:
    """Get Redis client (alias for compatibility)."""
    return request.app.state.redis_client


def get_customer_segmentation(request: Request) -> CustomerSegmentationService:
    """Get customer segmentation service with async Redis client."""
    async_redis_client = request.app.state.async_redis_client
    return CustomerSegmentationService(async_redis_client)


def get_http_client(request: Request) -> Any:
    """Get HTTP client from app state."""
    return request.app.state.http_client


def get_cart_service(
    redis_client: Any = None,
    request: Request = None
) -> CartService:
    """Get cart service instance."""
    if redis_client is None:
        redis_client = request.app.state.redis_client
    return CartService(redis_client)


def get_external_service(
    http_client: Any = None,
    request: Request = None
) -> ExternalServiceClient:
    """Get external service client."""
    if http_client is None:
        http_client = request.app.state.http_client
    return ExternalServiceClient(http_client)


def get_order_service(request: Request) -> OrderService:
    """Get order service instance."""
    cart_service = get_cart_service(request=request)
    external_service = get_external_service(request=request)
    return OrderService(cart_service, external_service)
