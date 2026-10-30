import json
import sqlite3
from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse

from app.database import get_db
from app.repository.order_repo import OrderRepository
from app.repository.restaurant_repo import RestaurantRepository
from app.schemas.order import OrderCreate, OrderResponse, OrderStatus, OrderStatusUpdate, OrderTrackingResponse
from app.services.broadcaster import order_broadcaster
from app.services.order_service import OrderService

router = APIRouter()


def get_order_service(conn: sqlite3.Connection = Depends(get_db)) -> OrderService:
    order_repo = OrderRepository(conn)
    restaurant_repo = RestaurantRepository(conn)
    return OrderService(order_repo, restaurant_repo)


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    order_in: OrderCreate,
    service: OrderService = Depends(get_order_service),
):
    """Place a new order for a restaurant."""
    return service.create_order(order_in)


@router.get("/{id}", response_model=OrderResponse)
def get_order(
    id: int,
    service: OrderService = Depends(get_order_service),
):
    """Retrieve an order by its ID."""
    return service.get_order(id)


@router.get("/{id}/tracking", response_model=OrderTrackingResponse)
def get_order_tracking(
    id: int,
    service: OrderService = Depends(get_order_service),
):
    """Retrieve live order tracking snapshot and history."""
    return service.get_order_tracking(id)


@router.get("/{id}/tracking/stream")
async def stream_order_tracking(
    id: int,
    service: OrderService = Depends(get_order_service),
):
    """Stream live order tracking updates using Server-Sent Events (SSE)."""
    # 1. Check order existence and get initial snapshot (raises NotFoundError / 404 if missing)
    snapshot = service.get_order_tracking(id)
    initial_payload = snapshot.model_dump(mode="json")
    is_terminal = snapshot.current_status in (OrderStatus.DELIVERED, OrderStatus.CANCELLED)

    async def event_generator():
        # Yield initial snapshot immediately
        if is_terminal:
            yield f"event: tracking_update\ndata: {json.dumps(initial_payload)}\n\n"
            return

        queue = order_broadcaster.register_listener(id)
        try:
            yield f"event: tracking_update\ndata: {json.dumps(initial_payload)}\n\n"
            while True:
                payload = await queue.get()
                yield f"event: tracking_update\ndata: {json.dumps(payload)}\n\n"
                status_val = payload.get("current_status")
                if isinstance(status_val, OrderStatus):
                    status_val = status_val.value
                if status_val in (OrderStatus.DELIVERED.value, OrderStatus.CANCELLED.value):
                    break
        finally:
            order_broadcaster.unregister_listener(id, queue)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=headers,
    )


@router.patch("/{id}/status", response_model=OrderResponse)
def update_order_status(
    id: int,
    status_update: OrderStatusUpdate,
    service: OrderService = Depends(get_order_service),
):
    """Update the status of an existing order."""
    return service.update_order_status(id, status_update.status)
