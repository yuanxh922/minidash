import sqlite3
from typing import List
from fastapi import APIRouter, Depends

from app.database import get_db
from app.repository.restaurant_repo import RestaurantRepository
from app.schemas.restaurant import RestaurantResponse, MenuItemResponse
from app.services.restaurant_service import RestaurantService

router = APIRouter()


def get_restaurant_service(conn: sqlite3.Connection = Depends(get_db)) -> RestaurantService:
    repo = RestaurantRepository(conn)
    return RestaurantService(repo)


@router.get("", response_model=List[RestaurantResponse])
def get_restaurants(service: RestaurantService = Depends(get_restaurant_service)):
    """Retrieve list of all restaurants."""
    return service.list_restaurants()


@router.get("/{id}/menu", response_model=List[MenuItemResponse])
def get_restaurant_menu(id: int, service: RestaurantService = Depends(get_restaurant_service)):
    """Retrieve the menu items for a specific restaurant by its ID."""
    return service.get_restaurant_menu(id)
