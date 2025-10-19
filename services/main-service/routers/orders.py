"""Orders API router."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import httpx

from database import get_db
from schemas import CheckoutRequest, CheckoutResponse, OrdersListResponse
from auth import verify_token, get_user_id_from_token
from dependencies import get_order_service, get_customer_segmentation
from monitoring import funnel_stage_counter, customer_segment_counter

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    request: CheckoutRequest,
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
    order_service = Depends(get_order_service),
    segmentation = Depends(get_customer_segmentation)
):
    """Checkout and process payment - requires authentication."""
    user_id = get_user_id_from_token(token)

    try:
        result = await order_service.process_checkout(
            db=db,
            user_id=user_id,
            payment_method=request.payment_method,
            country=request.country
        )

        # Track customer activity and segment (async)
        await segmentation.record_activity(user_id, "checkout", result.get("total_amount"))
        customer_segment = await segmentation.get_customer_segment(user_id)

        # Funnel analysis: Stage 4 - Checkout Complete
        funnel_stage_counter.add(1, {
            "stage": "checkout_complete",
            "country": request.country,
            "payment_method": request.payment_method
        })

        # Customer segmentation
        customer_segment_counter.add(1, {
            "segment": customer_segment,
            "action": "checkout",
            "country": request.country
        })

        return {
            "message": "Checkout successful",
            **result
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPError:
        raise HTTPException(status_code=500, detail="Payment service unavailable")


@router.get("", response_model=OrdersListResponse)
async def get_orders(
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
    order_service = Depends(get_order_service)
):
    """Get user's orders - requires authentication."""
    user_id = get_user_id_from_token(token)
    orders = order_service.get_user_orders(db, user_id)

    return {"orders": orders}
