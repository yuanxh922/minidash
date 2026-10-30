from enum import Enum
from typing import List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrderStatus(str, Enum):
    PLACED = "PLACED"
    PREPARING = "PREPARING"
    READY = "READY"
    PICKED_UP = "PICKED_UP"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


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


class TrackingHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: OrderStatus
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp of status transition")


class OrderTrackingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    order_id: int
    current_status: OrderStatus
    estimated_arrival_at: Optional[str] = Field(
        None, description="ISO 8601 UTC estimated arrival time, null if cancelled"
    )
    history: List[TrackingHistoryItem] = Field(
        ..., description="Chronological list of all status transitions"
    )


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    restaurant_id: int
    status: Union[OrderStatus, str]
    total_cents: int
    address: str
    created_at: str
    estimated_arrival_at: Optional[str] = None
    items: List[OrderItemResponse]

    @field_validator("status", mode="before")
    @classmethod
    def parse_status(cls, v):
        if isinstance(v, str):
            try:
                return OrderStatus(v)
            except ValueError:
                return v
        return v
