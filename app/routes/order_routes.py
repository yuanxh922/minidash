import sqlite3
from fastapi import APIRouter, Depends, status

from app.database import get_db
from app.repository.order_repo import OrderRepository
from app.repository.restaurant_repo import RestaurantRepository
from app.schemas.order import OrderCreate, OrderResponse, OrderStatusUpdate
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


@router.patch("/{id}/status", response_model=OrderResponse)
def update_order_status(
    id: int,
    status_update: OrderStatusUpdate,
    service: OrderService = Depends(get_order_service),
):
    """Update the status of an existing order."""
    return service.update_order_status(id, status_update.status)
