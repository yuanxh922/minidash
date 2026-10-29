from typing import List
from app.exceptions import NotFoundError
from app.repository.restaurant_repo import RestaurantRepository
from app.schemas.restaurant import RestaurantResponse, MenuItemResponse


class RestaurantService:
    """Service layer managing business logic for restaurants and menus."""

    def __init__(self, repo: RestaurantRepository):
        self.repo = repo

    def list_restaurants(self) -> List[RestaurantResponse]:
        """Retrieve all restaurants."""
        rows = self.repo.get_all()
        return [RestaurantResponse.model_validate(row) for row in rows]

    def get_restaurant(self, restaurant_id: int) -> RestaurantResponse:
        """Retrieve a single restaurant by ID, raising NotFoundError if missing."""
        row = self.repo.get_by_id(restaurant_id)
        if not row:
            raise NotFoundError(f"Restaurant with id {restaurant_id} not found")
        return RestaurantResponse.model_validate(row)

    def get_restaurant_menu(self, restaurant_id: int) -> List[MenuItemResponse]:
        """Retrieve all menu items for a restaurant, ensuring the restaurant exists first."""
        self.get_restaurant(restaurant_id)  # Enforces 404 if restaurant doesn't exist
        items = self.repo.get_menu(restaurant_id)
        return [MenuItemResponse.model_validate(item) for item in items]
