"""Products API router."""
from fastapi import APIRouter, Depends, HTTPException, Path, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from opentelemetry import trace

from database import get_db
from models import Product
from schemas import ProductResponse
from monitoring import (
    product_views_counter,
    product_detail_views_counter,
    funnel_stage_counter,
    customer_segment_counter,
    active_users_counter
)
from dependencies import get_redis, get_customer_segmentation
from customer_segmentation import CustomerSegmentationService

router = APIRouter(tags=["products"])


@router.get("/{country}/products", response_model=List[ProductResponse])
async def get_products(
    country: str = Path(..., description="Country code (e.g., us, uk, de, fr, jp, br, in)"),
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    segmentation: CustomerSegmentationService = Depends(get_customer_segmentation)
):
    """
    Get all products available in the specified country.

    In a real e-commerce system, product availability, pricing, and catalog
    vary by country due to:
    - Regional inventory availability
    - Import/export regulations
    - Local pricing strategies
    - Regional product variants

    This endpoint follows REST conventions where the country is part of the URL path,
    similar to real e-commerce APIs:
    - Amazon: /us/products, /de/products
    - eBay: /uk/items, /au/items
    - Stripe: /v1/products (with Stripe-Account header, but conceptually similar)

    Examples:
    - GET /us/products - US product catalog
    - GET /de/products - German product catalog
    - GET /jp/products - Japanese product catalog
    """
    country_upper = country.upper()
    products = db.query(Product).all()

    # Extract user ID from authorization header if present
    user_id = None
    customer_segment = "anonymous"
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        user_id = f"user_{token[:10]}"

        # Track customer activity (async)
        await segmentation.record_activity(user_id, "browse")
        customer_segment = await segmentation.get_customer_segment(user_id)

    # Add country-specific attributes to span
    span = trace.get_current_span()
    span.set_attribute("product.count", len(products))
    span.set_attribute("country", country_upper)
    span.set_attribute("endpoint.type", "product_catalog")
    span.set_attribute("customer.segment", customer_segment)

    # Record metrics
    product_views_counter.add(1, {"country": country_upper})
    active_users_counter.add(1, {"country": country_upper, "segment": customer_segment})

    # Funnel analysis: Stage 1 - Browse Catalog
    funnel_stage_counter.add(1, {
        "stage": "browse_catalog",
        "country": country_upper
    })

    # Customer segmentation
    customer_segment_counter.add(1, {
        "segment": customer_segment,
        "action": "browse_catalog",
        "country": country_upper
    })

    return products


@router.get("/{country}/products/{product_id}", response_model=ProductResponse)
async def get_product(
    country: str = Path(..., description="Country code (e.g., us, uk, de, fr, jp, br, in)"),
    product_id: int = Path(..., description="Product ID"),
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    segmentation: CustomerSegmentationService = Depends(get_customer_segmentation)
):
    """
    Get product details for a specific country.

    Product information may vary by country including:
    - Availability status
    - Pricing (currency, taxes, regional pricing)
    - Product specifications (voltage, plug types, etc.)
    - Shipping options

    Examples:
    - GET /us/products/123 - Product 123 in US market
    - GET /de/products/123 - Product 123 in German market
    """
    country_upper = country.upper()

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Extract user ID and track activity
    user_id = None
    customer_segment = "anonymous"
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        user_id = f"user_{token[:10]}"

        # Track customer activity (async)
        await segmentation.record_activity(user_id, "view_product")
        customer_segment = await segmentation.get_customer_segment(user_id)

    # Add tracing attributes
    span = trace.get_current_span()
    span.set_attribute("product.id", product_id)
    span.set_attribute("country", country_upper)
    span.set_attribute("customer.segment", customer_segment)

    # Record metric for individual product detail views by country
    product_detail_views_counter.add(1, {
        "country": country_upper,
        "product_id": str(product_id),
        "category": product.category
    })

    # Funnel analysis: Stage 2 - View Product Details
    funnel_stage_counter.add(1, {
        "stage": "view_product",
        "country": country_upper,
        "category": product.category
    })

    # Customer segmentation
    customer_segment_counter.add(1, {
        "segment": customer_segment,
        "action": "view_product",
        "country": country_upper
    })

    return product
