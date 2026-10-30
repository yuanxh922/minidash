import re
from datetime import datetime


ISO_8601_UTC_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]00:00)$"
)


def _create_order(client, restaurant_id=1):
    payload = {
        "restaurant_id": restaurant_id,
        "address": "123 Elm Street",
        "items": [
            {"menu_item_id": 1, "quantity": 1},
        ],
    }
    response = client.post("/orders", json=payload)
    assert response.status_code == 201
    return response.json()


def test_get_tracking_success_chronological_history(client):
    """Test GET /orders/{id}/tracking returns live snapshot with chronological history."""
    # 1. Places order (PLACED), advances to PREPARING, then READY
    order = _create_order(client)
    order_id = order["id"]

    res_prep = client.patch(f"/orders/{order_id}/status", json={"status": "PREPARING"})
    assert res_prep.status_code == 200

    res_ready = client.patch(f"/orders/{order_id}/status", json={"status": "READY"})
    assert res_ready.status_code == 200

    # 2. Calls GET /orders/{id}/tracking
    response = client.get(f"/orders/{order_id}/tracking")

    # 3. Asserts HTTP 200
    assert response.status_code == 200
    data = response.json()

    # 4. Asserts current_status == "READY", order_id == id
    assert data["order_id"] == order_id
    assert data["current_status"] == "READY"
    assert data["estimated_arrival_at"] is not None
    assert ISO_8601_UTC_PATTERN.match(data["estimated_arrival_at"])

    # 5. Asserts history array has 3 items in chronological order: PLACED, PREPARING, READY
    history = data["history"]
    assert len(history) == 3
    assert history[0]["status"] == "PLACED"
    assert history[1]["status"] == "PREPARING"
    assert history[2]["status"] == "READY"

    # 6. Asserts timestamps are ISO 8601 UTC format
    for item in history:
        assert ISO_8601_UTC_PATTERN.match(item["timestamp"]), (
            f"Timestamp '{item['timestamp']}' does not match ISO 8601 UTC pattern"
        )
        parsed_dt = datetime.fromisoformat(item["timestamp"])
        assert parsed_dt.tzinfo is not None


def test_get_tracking_not_found(client):
    """Test GET /orders/99999/tracking returns 404 when order does not exist."""
    response = client.get("/orders/99999/tracking")
    assert response.status_code == 404
    data = response.json()
    assert data.get("detail") == "Order with id 99999 not found"


def test_get_tracking_cancelled_order_has_null_eta(client):
    """Test GET /orders/{id}/tracking for cancelled order returns CANCELLED and null ETA."""
    # Places order, cancels it, queries GET /orders/{id}/tracking
    order = _create_order(client)
    order_id = order["id"]

    cancel_res = client.patch(f"/orders/{order_id}/status", json={"status": "CANCELLED"})
    assert cancel_res.status_code == 200

    response = client.get(f"/orders/{order_id}/tracking")
    assert response.status_code == 200
    data = response.json()

    # Asserts current_status == "CANCELLED" and estimated_arrival_at is None
    assert data["order_id"] == order_id
    assert data["current_status"] == "CANCELLED"
    assert data["estimated_arrival_at"] is None

    # History should contain PLACED and CANCELLED
    assert len(data["history"]) == 2
    assert data["history"][0]["status"] == "PLACED"
    assert data["history"][1]["status"] == "CANCELLED"
    for item in data["history"]:
        assert ISO_8601_UTC_PATTERN.match(item["timestamp"])
