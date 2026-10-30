from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from app.exceptions import NotFoundError, ValidationError
from app.repository.order_repo import OrderRepository
from app.repository.restaurant_repo import RestaurantRepository
from app.schemas.order import OrderCreate, OrderResponse, OrderStatus, OrderTrackingResponse
from app.services.broadcaster import OrderBroadcaster, order_broadcaster
from app.services.eta_calculator import calculate_eta

VALID_TRANSITIONS: Dict[OrderStatus, Set[OrderStatus]] = {
    OrderStatus.PLACED: {OrderStatus.PREPARING, OrderStatus.CANCELLED},
    OrderStatus.PREPARING: {OrderStatus.READY},
    OrderStatus.READY: {OrderStatus.PICKED_UP},
    OrderStatus.PICKED_UP: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}


class OrderService:
    """Service layer managing business logic, validations, and transactions for orders."""

    VALID_TRANSITIONS = VALID_TRANSITIONS
    ALLOWED_STATUSES: Set[str] = {s.value for s in OrderStatus}

    def __init__(
        self,
        order_repo: OrderRepository,
        restaurant_repo: RestaurantRepository,
        broadcaster: Optional[OrderBroadcaster] = None,
    ):
        self.order_repo = order_repo
        self.restaurant_repo = restaurant_repo
        self.broadcaster = broadcaster or order_broadcaster

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
        transition_time = datetime.now(timezone.utc)
        created_at = transition_time.isoformat()
        initial_status = OrderStatus.PLACED.value
        avg_prep_minutes = restaurant["avg_prep_minutes"]
        estimated_arrival_at = calculate_eta(
            OrderStatus.PLACED,
            transition_time,
            avg_prep_minutes,
        )

        created_order = self.order_repo.create_order(
            restaurant_id=order_data.restaurant_id,
            status=initial_status,
            total_cents=total_cents,
            address=clean_address,
            created_at=created_at,
            items=items_payload,
            estimated_arrival_at=estimated_arrival_at,
        )

        return OrderResponse.model_validate(created_order)

    def get_order(self, order_id: int) -> OrderResponse:
        """Fetch order by ID or raise NotFoundError if missing."""
        order_data = self.order_repo.get_by_id(order_id)
        if not order_data:
            raise NotFoundError(f"Order with id {order_id} not found")
        return OrderResponse.model_validate(order_data)

    def get_order_tracking(self, order_id: int) -> OrderTrackingResponse:
        """Fetch tracking snapshot and chronological history for an order."""
        tracking_data = self.order_repo.get_tracking(order_id)
        if not tracking_data:
            raise NotFoundError(f"Order with id {order_id} not found")
        return OrderTrackingResponse(**tracking_data)

    def update_order_status(self, order_id: int, status: str) -> OrderResponse:
        """Validate status, enforce FSM transitions, calculate new ETA, and update atomically."""
        # 1. Verify order exists before updating
        existing = self.order_repo.get_by_id(order_id)
        if not existing:
            raise NotFoundError(f"Order with id {order_id} not found")

        # 2. Check if new_status is a valid OrderStatus string/enum
        normalized_status = status.strip().upper() if isinstance(status, str) else status
        try:
            target_status = OrderStatus(normalized_status)
        except (ValueError, AttributeError):
            allowed = ", ".join(sorted([s.value for s in OrderStatus]))
            raise ValidationError(
                f"Invalid status '{status}'. Allowed statuses are: {allowed}"
            )

        # 3. Check current status
        current_status_raw = existing["status"]
        try:
            current_status = OrderStatus(current_status_raw)
        except ValueError:
            current_status = current_status_raw

        current_status_str = (
            current_status.value if isinstance(current_status, OrderStatus) else str(current_status)
        )

        # 4. Check if current status is terminal
        if current_status in (OrderStatus.DELIVERED, OrderStatus.CANCELLED):
            raise ValidationError(
                f"Cannot update order in terminal status '{current_status_str}'"
            )

        # 5. Check transition validity
        allowed_transitions = VALID_TRANSITIONS.get(current_status, set())
        if target_status not in allowed_transitions:
            if target_status == OrderStatus.CANCELLED:
                raise ValidationError(
                    f"Cannot cancel order in status '{current_status_str}'. Cancellation is only permitted when PLACED."
                )
            raise ValidationError(
                f"Cannot transition order from '{current_status_str}' to '{target_status.value}'"
            )

        # 6. Calculate new ETA
        transition_time = datetime.now(timezone.utc)
        timestamp = transition_time.isoformat()

        restaurant_id = existing["restaurant_id"]
        restaurant = self.restaurant_repo.get_by_id(restaurant_id)
        avg_prep_minutes = restaurant["avg_prep_minutes"] if restaurant else 0

        estimated_arrival_at = calculate_eta(target_status, transition_time, avg_prep_minutes)

        # 7. Atomically update status and ETA and record in order_status_history
        updated_order = self.order_repo.update_status_and_eta(
            order_id=order_id,
            status=target_status.value,
            estimated_arrival_at=estimated_arrival_at,
            timestamp=timestamp,
        )
        if not updated_order:
            raise NotFoundError(f"Order with id {order_id} not found")

        # 8. Broadcast live tracking snapshot to active subscribers
        tracking = self.get_order_tracking(order_id)
        self.broadcaster.broadcast(order_id, tracking.model_dump(mode="json"))

        return OrderResponse.model_validate(updated_order)
