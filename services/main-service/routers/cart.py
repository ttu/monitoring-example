"""Cart API router."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas import AddToCartRequest, AddToCartResponse, CartResponse
from auth import verify_token, get_user_id_from_token
from dependencies import get_cart_service, get_customer_segmentation
from monitoring import funnel_stage_counter, customer_segment_counter

router = APIRouter(prefix="/cart", tags=["cart"])


@router.post("/add", response_model=AddToCartResponse)
async def add_to_cart(
    request: AddToCartRequest,
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
    cart_service = Depends(get_cart_service),
    segmentation = Depends(get_customer_segmentation)
):
    """Add item to cart - requires authentication."""
    user_id = get_user_id_from_token(token)

    try:
        result = cart_service.add_to_cart(
            db=db,
            user_id=user_id,
            product_id=request.product_id,
            quantity=request.quantity,
            country=request.country
        )

        # Track customer activity and segment (async)
        await segmentation.record_activity(user_id, "add_to_cart")
        customer_segment = await segmentation.get_customer_segment(user_id)

        # Funnel analysis: Stage 3 - Add to Cart
        funnel_stage_counter.add(1, {
            "stage": "add_to_cart",
            "country": request.country
        })

        # Customer segmentation
        customer_segment_counter.add(1, {
            "segment": customer_segment,
            "action": "add_to_cart",
            "country": request.country
        })

        return {
            "message": "Item added to cart",
            "cart_item_id": result["cart_item_id"],
            "product_name": result["product_name"]
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=CartResponse)
async def get_cart(
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
    cart_service = Depends(get_cart_service)
):
    """Get user's cart - requires authentication."""
    user_id = get_user_id_from_token(token)
    return cart_service.get_cart(db, user_id)
