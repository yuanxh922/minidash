from datetime import datetime, timezone
from typing import List, Set
from app.exceptions import NotFoundError, ValidationError
from app.repository.order_repo import OrderRepository
from app.repository.restaurant_repo import RestaurantRepository
from app.schemas.order import OrderCreate, OrderResponse, OrderStatus


class OrderService:
    """Service layer managing business logic, validations, and transactions for orders."""

    ALLOWED_STATUSES: Set[str] = {
        OrderStatus.PLACED.value,
        OrderStatus.PREPARING.value,
        OrderStatus.READY.value,
        OrderStatus.PICKED_UP.value,
        OrderStatus.DELIVERED.value,
        OrderStatus.CANCELLED.value,
        "PENDING",
        "OUT_FOR_DELIVERY",
    }

    def __init__(self, order_repo: OrderRepository, restaurant_repo: RestaurantRepository):
        self.order_repo = order_repo
        self.restaurant_repo = restaurant_repo

    def create_order(self, order_data: OrderCreate) -> OrderResponse:
        """Validate restaurant, menu items, address, compute total, and create order."""
        # 1. Validate address
        clean_address = order_data.address.strip()
        if not clean_address:
            raise ValidationError("Delivery address cannot be empty")

        # 2. Check restaurant existence
        restaurant = self.restaurant_repo.get_by_id(order_data.restaurant_id)
        if not restaurant:
            raise NotFoundError(f"Restaurant with id {order_data.restaurant_id} not found")

        # 3. Check items presence
        if not order_data.items:
            raise ValidationError("Order must contain at least one item")

        # 4. Fetch menu items to validate existence and restaurant ownership
        unique_item_ids = list({item.menu_item_id for item in order_data.items})
        db_items = self.restaurant_repo.get_menu_items_by_ids(unique_item_ids)
        items_map = {item["id"]: item for item in db_items}

        for item in order_data.items:
            if item.menu_item_id not in items_map:
                raise ValidationError(f"Menu item with id {item.menu_item_id} not found")

            db_item = items_map[item.menu_item_id]
            if db_item["restaurant_id"] != order_data.restaurant_id:
                raise ValidationError(
                    f"Menu item '{db_item['name']}' (id {db_item['id']}) does not belong to restaurant {order_data.restaurant_id}"
                )

        # 5. Calculate total_cents and prepare order_items payload
        total_cents = 0
        items_payload = []
        for item in order_data.items:
            db_item = items_map[item.menu_item_id]
            unit_price = db_item["price_cents"]
            total_cents += unit_price * item.quantity
            items_payload.append(
                {
                    "menu_item_id": item.menu_item_id,
                    "quantity": item.quantity,
                    "unit_price_cents": unit_price,
                }
            )

        # 6. Save order atomically in repository
        created_at = datetime.now(timezone.utc).isoformat()
        initial_status = OrderStatus.PLACED.value

        created_order = self.order_repo.create_order(
            restaurant_id=order_data.restaurant_id,
            status=initial_status,
            total_cents=total_cents,
            address=clean_address,
            created_at=created_at,
            items=items_payload,
        )

        return OrderResponse.model_validate(created_order)

    def get_order(self, order_id: int) -> OrderResponse:
        """Fetch order by ID or raise NotFoundError if missing."""
        order_data = self.order_repo.get_by_id(order_id)
        if not order_data:
            raise NotFoundError(f"Order with id {order_id} not found")
        return OrderResponse.model_validate(order_data)

    def update_order_status(self, order_id: int, status: str) -> OrderResponse:
        """Validate status, check order existence, and update status."""
        normalized_status = status.strip().upper()
        if normalized_status not in self.ALLOWED_STATUSES:
            allowed = ", ".join(sorted(self.ALLOWED_STATUSES))
            raise ValidationError(
                f"Invalid status '{status}'. Allowed statuses are: {allowed}"
            )

        # Verify order exists before updating
        existing = self.order_repo.get_by_id(order_id)
        if not existing:
            raise NotFoundError(f"Order with id {order_id} not found")

        updated_order = self.order_repo.update_status(order_id, normalized_status)
        return OrderResponse.model_validate(updated_order)
