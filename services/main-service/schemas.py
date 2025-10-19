"""Pydantic schemas for request/response validation."""
from pydantic import BaseModel, ConfigDict
from typing import List


class ProductCreate(BaseModel):
    """Schema for creating a product."""
    name: str
    price: float
    stock: int
    category: str


class ProductResponse(BaseModel):
    """Schema for product response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price: float
    stock: int
    category: str


class AddToCartRequest(BaseModel):
    """Schema for add to cart request."""
    product_id: int
    quantity: int
    country: str


class AddToCartResponse(BaseModel):
    """Schema for add to cart response."""
    message: str
    cart_item_id: int
    product_name: str


class CartItemResponse(BaseModel):
    """Schema for cart item in response."""
    id: int
    product_id: int
    product_name: str
    price: float
    quantity: int
    subtotal: float


class CartResponse(BaseModel):
    """Schema for cart response."""
    user_id: str
    items: List[CartItemResponse]
    total: float


class CheckoutRequest(BaseModel):
    """Schema for checkout request."""
    payment_method: str
    country: str


class CheckoutResponse(BaseModel):
    """Schema for checkout response."""
    message: str
    order_id: int
    total_amount: float
    payment_transaction_id: str


class OrderResponse(BaseModel):
    """Schema for order response."""
    id: int
    total_amount: float
    country: str
    payment_method: str
    status: str
    created_at: str


class OrdersListResponse(BaseModel):
    """Schema for orders list response."""
    orders: List[OrderResponse]
