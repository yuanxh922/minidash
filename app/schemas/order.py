from typing import List
from pydantic import BaseModel, ConfigDict, Field


class OrderItemCreate(BaseModel):
    menu_item_id: int = Field(..., gt=0, description="The menu item ID to order")
    quantity: int = Field(..., gt=0, description="Quantity of items, must be greater than 0")


class OrderCreate(BaseModel):
    restaurant_id: int = Field(..., gt=0, description="Restaurant ID where order is placed")
    address: str = Field(..., min_length=1, description="Delivery address")
    items: List[OrderItemCreate] = Field(..., min_length=1, description="List of items in the order")


class OrderStatusUpdate(BaseModel):
    status: str = Field(..., min_length=1, description="Target status for the order")


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_id: int
    menu_item_id: int
    name: str
    quantity: int
    unit_price_cents: int


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    restaurant_id: int
    status: str
    total_cents: int
    address: str
    created_at: str
    items: List[OrderItemResponse]
