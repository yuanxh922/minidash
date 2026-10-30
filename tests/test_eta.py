from datetime import datetime, timedelta, timezone
import pytest
from app.schemas.order import OrderStatus
from app.services.eta_calculator import calculate_eta


def test_calculate_eta_placed_and_preparing():
    """Verify ETA calculation for PLACED and PREPARING statuses (t + avg_prep + 15 min)."""
    anchor = datetime(2026, 10, 29, 12, 0, 0, tzinfo=timezone.utc)
    avg_prep = 20

    # Test with OrderStatus enum
    eta_placed = calculate_eta(OrderStatus.PLACED, anchor, avg_prep)
    assert eta_placed == "2026-10-29T12:35:00+00:00"

    eta_prep = calculate_eta(OrderStatus.PREPARING, anchor, avg_prep)
    assert eta_prep == "2026-10-29T12:35:00+00:00"

    # Test with string values
    assert calculate_eta("PLACED", anchor, avg_prep) == "2026-10-29T12:35:00+00:00"
    assert calculate_eta("PREPARING", anchor, avg_prep) == "2026-10-29T12:35:00+00:00"


def test_calculate_eta_ready_and_picked_up():
    """Verify ETA calculation for READY and PICKED_UP statuses (t + 15 min transit)."""
    anchor = datetime(2026, 10, 29, 12, 20, 0, tzinfo=timezone.utc)
    avg_prep = 20

    # Test with OrderStatus enum
    eta_ready = calculate_eta(OrderStatus.READY, anchor, avg_prep)
    assert eta_ready == "2026-10-29T12:35:00+00:00"

    eta_picked = calculate_eta(OrderStatus.PICKED_UP, anchor, avg_prep)
    assert eta_picked == "2026-10-29T12:35:00+00:00"

    # Test with string values
    assert calculate_eta("READY", anchor, avg_prep) == "2026-10-29T12:35:00+00:00"
    assert calculate_eta("PICKED_UP", anchor, avg_prep) == "2026-10-29T12:35:00+00:00"


def test_calculate_eta_delivered():
    """Verify ETA calculation for DELIVERED status (t, exact delivery timestamp)."""
    anchor = datetime(2026, 10, 29, 12, 34, 50, tzinfo=timezone.utc)
    avg_prep = 20

    # Test with OrderStatus enum and string
    eta_delivered = calculate_eta(OrderStatus.DELIVERED, anchor, avg_prep)
    assert eta_delivered == "2026-10-29T12:34:50+00:00"

    assert calculate_eta("DELIVERED", anchor, avg_prep) == "2026-10-29T12:34:50+00:00"


def test_calculate_eta_cancelled():
    """Verify ETA calculation for CANCELLED status (None)."""
    anchor = datetime(2026, 10, 29, 12, 0, 0, tzinfo=timezone.utc)
    avg_prep = 20

    # Test with OrderStatus enum and string
    assert calculate_eta(OrderStatus.CANCELLED, anchor, avg_prep) is None
    assert calculate_eta("CANCELLED", anchor, avg_prep) is None


def test_create_order_calculates_and_persists_eta(client, db_conn):
    """Verify POST /orders calculates initial ETA and persists estimated_arrival_at."""
    # Restaurant 1 has avg_prep_minutes = 20
    payload = {
        "restaurant_id": 1,
        "address": "789 Pine St",
        "items": [
            {"menu_item_id": 1, "quantity": 1},
        ],
    }
    response = client.post("/orders", json=payload)
    assert response.status_code == 201

    order = response.json()
    order_id = order["id"]
    created_at_str = order["created_at"]
    estimated_arrival_at = order["estimated_arrival_at"]

    assert estimated_arrival_at is not None

    # Calculate expected ETA: created_at + 20 min prep + 15 min transit = +35 min
    created_at_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
    expected_eta = (created_at_dt + timedelta(minutes=35)).isoformat()
    assert estimated_arrival_at == expected_eta

    # Check persistence in database
    cur = db_conn.execute(
        "SELECT estimated_arrival_at FROM orders WHERE id = ?;",
        (order_id,),
    )
    row = cur.fetchone()
    assert row is not None
    assert row["estimated_arrival_at"] == estimated_arrival_at

    # Check GET /orders/{id} returns estimated_arrival_at
    get_res = client.get(f"/orders/{order_id}")
    assert get_res.status_code == 200
    assert get_res.json()["estimated_arrival_at"] == estimated_arrival_at
