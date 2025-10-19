"""External service communication layer."""
import httpx
import logging
import time
from typing import Dict, Any, Optional
from opentelemetry import trace

from config import (
    PAYMENTS_SERVICE_URL,
    PROMOTIONS_SERVICE_URL,
    CRM_SYSTEM_URL,
    INVENTORY_SYSTEM_URL
)
from monitoring import (
    external_inventory_duration_histogram,
    external_crm_duration_histogram
)

logger = logging.getLogger(__name__)


class ExternalServiceClient:
    """Client for communicating with external services."""

    def __init__(self, http_client: httpx.AsyncClient):
        """
        Initialize external service client.

        Args:
            http_client: Async HTTP client
        """
        self.http_client = http_client

    async def check_promotions(
        self,
        user_id: str,
        country: str,
        amount: float
    ) -> Optional[Dict[str, Any]]:
        """
        Check for available promotions.

        Args:
            user_id: User identifier
            country: Country code
            amount: Order amount

        Returns:
            Promotion data if available
        """
        # HTTPXClientInstrumentor already creates spans for HTTP calls
        try:
            response = await self.http_client.post(
                f"{PROMOTIONS_SERVICE_URL}/api/promotions/check",
                json={
                    "user_id": user_id,
                    "country": country,
                    "amount": amount
                }
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning("Promotions service returned non-200 status", extra={
                    "status_code": response.status_code,
                    "user_id": user_id,
                    "country": country,
                    "amount": amount
                })
                return None
        except Exception as e:
            logger.error("Failed to check promotions", extra={
                "user_id": user_id,
                "country": country,
                "amount": amount,
                "error": str(e)
            })
            return None

    async def process_payment(
        self,
        user_id: str,
        amount: float,
        currency: str,
        country: str,
        payment_method: str
    ) -> Optional[Dict[str, Any]]:
        """
        Process payment through payments service.

        Args:
            user_id: User identifier
            amount: Payment amount
            currency: Currency code
            country: Country code
            payment_method: Payment method

        Returns:
            Payment result data

        Raises:
            httpx.HTTPError: If payment service is unavailable
        """
        # HTTPXClientInstrumentor already creates spans for HTTP calls
        response = await self.http_client.post(
            f"{PAYMENTS_SERVICE_URL}/api/payments/process",
            json={
                "user_id": user_id,
                "amount": amount,
                "currency": currency,
                "country": country,
                "payment_method": payment_method
            }
        )
        response.raise_for_status()
        return response.json()

    async def check_inventory(
        self,
        product_id: int,
        quantity: int,
        country: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check inventory availability.

        Args:
            product_id: Product identifier
            quantity: Quantity needed
            country: Country code

        Returns:
            Inventory data if available
        """
        # HTTPXClientInstrumentor already creates spans for HTTP calls
        start_time = time.time()
        status = "success"
        status_code = None
        try:
            response = await self.http_client.post(
                f"{INVENTORY_SYSTEM_URL}/api/inventory/check",
                json={
                    "product_id": product_id,
                    "quantity": quantity,
                    "country": country
                }
            )
            status_code = response.status_code
            if response.status_code == 200:
                return response.json()
            else:
                status = "error"
                logger.warning("Inventory service returned non-200 status", extra={
                    "status_code": response.status_code,
                    "product_id": product_id,
                    "quantity": quantity,
                    "country": country
                })
                return None
        except Exception as e:
            status = "error"
            status_code = 0  # Connection failure
            logger.error("Failed to check inventory", extra={
                "product_id": product_id,
                "quantity": quantity,
                "country": country,
                "error": str(e)
            })
            return None
        finally:
            duration = time.time() - start_time
            external_inventory_duration_histogram.record(
                duration,
                {
                    "operation": "check",
                    "status": status,
                    "status_code": str(status_code) if status_code else "0",
                    "country": country
                }
            )

    async def reserve_inventory(
        self,
        product_id: int,
        quantity: int,
        country: str,
        order_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Reserve inventory for an order.

        Args:
            product_id: Product identifier
            quantity: Quantity to reserve
            country: Country code
            order_id: Order identifier

        Returns:
            Reservation data if successful
        """
        # HTTPXClientInstrumentor already creates spans for HTTP calls
        start_time = time.time()
        status = "success"
        status_code = None
        try:
            response = await self.http_client.post(
                f"{INVENTORY_SYSTEM_URL}/api/inventory/reserve",
                json={
                    "product_id": product_id,
                    "quantity": quantity,
                    "country": country,
                    "order_id": order_id
                }
            )
            status_code = response.status_code
            if response.status_code == 200:
                return response.json()
            else:
                status = "error"
                logger.warning("Inventory reservation failed", extra={
                    "status_code": response.status_code,
                    "product_id": product_id,
                    "quantity": quantity,
                    "country": country,
                    "order_id": order_id
                })
                return None
        except Exception as e:
            status = "error"
            status_code = 0  # Connection failure
            logger.error("Failed to reserve inventory", extra={
                "product_id": product_id,
                "quantity": quantity,
                "country": country,
                "order_id": order_id,
                "error": str(e)
            })
            return None
        finally:
            duration = time.time() - start_time
            external_inventory_duration_histogram.record(
                duration,
                {
                    "operation": "reserve",
                    "status": status,
                    "status_code": str(status_code) if status_code else "0",
                    "country": country
                }
            )

    async def update_crm(
        self,
        user_id: str,
        order_id: int,
        amount: float,
        country: str
    ) -> None:
        """
        Update CRM system with order information.

        Args:
            user_id: User identifier
            order_id: Order identifier
            amount: Order amount
            country: Country code
        """
        # HTTPXClientInstrumentor already creates spans for HTTP calls
        start_time = time.time()
        status = "success"
        status_code = None
        try:
            response = await self.http_client.post(
                f"{CRM_SYSTEM_URL}/api/customer/order",
                json={
                    "user_id": user_id,
                    "order_id": order_id,
                    "amount": amount,
                    "country": country
                }
            )
            status_code = response.status_code
            if response.status_code >= 400:
                status = "error"
                logger.warning("CRM service returned error status", extra={
                    "status_code": response.status_code,
                    "user_id": user_id,
                    "order_id": order_id,
                    "amount": amount,
                    "country": country
                })
        except Exception as e:
            status = "error"
            status_code = 0  # Connection failure
            logger.error("Failed to update CRM", extra={
                "user_id": user_id,
                "order_id": order_id,
                "amount": amount,
                "country": country,
                "error": str(e)
            })
        finally:
            duration = time.time() - start_time
            external_crm_duration_histogram.record(
                duration,
                {
                    "status": status,
                    "status_code": str(status_code) if status_code else "0",
                    "country": country
                }
            )
