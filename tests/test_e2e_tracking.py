import asyncio
from datetime import datetime
import pytest

from scripts import simulate_driver

pytestmark = pytest.mark.anyio


async def test_full_order_live_tracking_e2e(async_client, monkeypatch):
    """End-to-end integration test validating the entire TrackC lifecycle:

    1. Place order via POST /orders and verify PLACED status and initial ETA.
    2. Connect to SSE stream at GET /orders/{id}/tracking/stream and verify PLACED snapshot.
    3. Run driver advancement simulation in background via simulate_driver.run_simulation.
    4. Receive all 4 subsequent event frames (PREPARING, READY, PICKED_UP, DELIVERED) in order.
    5. Verify ETA progression and lock to final delivered timestamp.
    6. Verify SSE stream cleanly terminates on DELIVERED.
    7. Perform short-polling GET /orders/{id}/tracking to verify full audit history and status.
    """
    # 1. Place order via POST /orders
    create_payload = {
        "restaurant_id": 1,
        "address": "742 Evergreen Terrace",
        "items": [
            {"menu_item_id": 1, "quantity": 2},
            {"menu_item_id": 2, "quantity": 1},
        ],
    }
    create_res = await async_client.post("/orders", json=create_payload)
    assert create_res.status_code == 201
    order_data = create_res.json()
    order_id = order_data["id"]
    assert order_data["status"] == "PLACED"
    initial_eta = order_data["estimated_arrival_at"]
    assert initial_eta is not None

    # Verify initial audit history in DB via tracking endpoint before connecting
    pre_poll = await async_client.get(f"/orders/{order_id}/tracking")
    assert pre_poll.status_code == 200
    pre_tracking = pre_poll.json()
    assert pre_tracking["current_status"] == "PLACED"
    assert len(pre_tracking["history"]) == 1
    assert pre_tracking["history"][0]["status"] == "PLACED"

    # 2. Connect to SSE stream
    async with async_client.stream("GET", f"/orders/{order_id}/tracking/stream") as stream:
        assert stream.status_code == 200
        assert stream.headers.get("content-type", "").startswith("text/event-stream")
        assert stream.headers.get("cache-control") == "no-cache"

        # Consume initial event frame (PLACED snapshot)
        initial_event = await stream.read_event(timeout=5.0)
        assert initial_event is not None
        assert initial_event["event"] == "tracking_update"
        init_data = initial_event["data"]
        assert init_data["order_id"] == order_id
        assert init_data["current_status"] == "PLACED"
        assert init_data["estimated_arrival_at"] == initial_eta
        assert len(init_data["history"]) == 1
        assert init_data["history"][0]["status"] == "PLACED"

        # 3. Setup and trigger simulate_driver in background task
        loop = asyncio.get_running_loop()

        def fake_http_request(method: str, url: str, body=None):
            coro = async_client.request(method=method, url=url, json_body=body)
            fut = asyncio.run_coroutine_threadsafe(coro, loop)
            res = fut.result(timeout=10.0)
            try:
                data = res.json()
            except Exception:
                data = {}
            return res.status_code, data

        monkeypatch.setattr(simulate_driver, "_http_request", fake_http_request)

        sim_task = asyncio.create_task(
            asyncio.to_thread(
                simulate_driver.run_simulation,
                order_id=order_id,
                delay=0.02,
                base_url="http://testserver",
            )
        )

        # 4. Receive all 4 subsequent event frames in exact chronological order
        expected_progression = ["PREPARING", "READY", "PICKED_UP", "DELIVERED"]
        received_events = []
        last_eta = datetime.fromisoformat(initial_eta)

        for expected_status in expected_progression:
            event = await stream.read_event(timeout=5.0)
            assert event is not None, f"Timed out waiting for event with status {expected_status}"
            assert event["event"] == "tracking_update"
            data = event["data"]
            assert data["order_id"] == order_id
            assert data["current_status"] == expected_status
            assert data["estimated_arrival_at"] is not None

            # Verify ETA updates: READY/PICKED_UP/DELIVERED should have an ETA <= PLACED/PREPARING ETA
            current_eta = datetime.fromisoformat(data["estimated_arrival_at"])
            if expected_status in ("READY", "DELIVERED"):
                assert current_eta <= last_eta
            last_eta = current_eta

            received_events.append(data)

        # 5. Verify the stream closes cleanly upon DELIVERED
        terminal_frame = await stream.read_event(timeout=2.0)
        assert terminal_frame is None

        # Verify simulation task finished successfully with return code 0
        sim_rc = await sim_task
        assert sim_rc == 0

    # 6. Perform short-polling GET /orders/{id}/tracking to verify final state and audit log
    poll_res = await async_client.get(f"/orders/{order_id}/tracking")
    assert poll_res.status_code == 200
    tracking_data = poll_res.json()
    assert tracking_data["order_id"] == order_id
    assert tracking_data["current_status"] == "DELIVERED"

    history = tracking_data["history"]
    assert len(history) == 5
    full_progression = ["PLACED", "PREPARING", "READY", "PICKED_UP", "DELIVERED"]
    assert [entry["status"] for entry in history] == full_progression

    # Final ETA must lock to the exact DELIVERED transition timestamp
    delivered_entry = history[-1]
    assert delivered_entry["status"] == "DELIVERED"
    assert tracking_data["estimated_arrival_at"] == delivered_entry["timestamp"]


def test_existing_endpoints_regression(client):
    """Comprehensive regression suite covering all existing MiniDash core endpoints:

    - Health check: GET /
    - Restaurants: GET /restaurants, GET /restaurants/{id}/menu, invalid menu lookup
    - Orders: POST /orders, validation errors (nonexistent restaurant, wrong item, blank address, invalid qty)
    - Order retrieval: GET /orders/{id}, GET /orders/{nonexistent}
    - Status management: PATCH /orders/{id}/status, invalid status string, invalid state skips, not found
    - Order tracking: GET /orders/{id}/tracking, GET /orders/{nonexistent}/tracking
    """
    # 1. Health check
    health_res = client.get("/")
    assert health_res.status_code == 200
    assert health_res.json() == {"app": "MiniDash", "status": "ok"}

    # 2. Restaurants list
    rest_res = client.get("/restaurants")
    assert rest_res.status_code == 200
    restaurants = rest_res.json()
    assert isinstance(restaurants, list)
    assert len(restaurants) == 5
    first_rest = restaurants[0]
    for required_key in ["id", "name", "cuisine", "opens_at", "closes_at", "avg_prep_minutes"]:
        assert required_key in first_rest

    # 3. Restaurant menu lookup (valid & invalid)
    menu_res = client.get("/restaurants/1/menu")
    assert menu_res.status_code == 200
    menu_items = menu_res.json()
    assert isinstance(menu_items, list)
    assert len(menu_items) >= 1
    for item in menu_items:
        assert item["restaurant_id"] == 1
        assert "name" in item
        assert "price_cents" in item

    invalid_menu_res = client.get("/restaurants/99999/menu")
    assert invalid_menu_res.status_code == 404

    # 4. Order placement happy path
    create_payload = {
        "restaurant_id": 1,
        "address": "100 Broadway",
        "items": [
            {"menu_item_id": 1, "quantity": 2},
        ],
    }
    create_res = client.post("/orders", json=create_payload)
    assert create_res.status_code == 201
    order = create_res.json()
    order_id = order["id"]
    assert order["status"] == "PLACED"
    assert order["address"] == "100 Broadway"
    assert order["restaurant_id"] == 1
    assert "estimated_arrival_at" in order
    assert len(order["items"]) == 1

    # 5. Order placement validation errors
    # Nonexistent restaurant
    bad_rest = client.post("/orders", json={
        "restaurant_id": 99999,
        "address": "123 Main St",
        "items": [{"menu_item_id": 1, "quantity": 1}],
    })
    assert bad_rest.status_code == 404

    # Menu item from different restaurant (Item 5 belongs to Restaurant 2, not 1)
    wrong_item = client.post("/orders", json={
        "restaurant_id": 1,
        "address": "123 Main St",
        "items": [{"menu_item_id": 5, "quantity": 1}],
    })
    assert wrong_item.status_code == 400

    # Nonexistent menu item
    missing_item = client.post("/orders", json={
        "restaurant_id": 1,
        "address": "123 Main St",
        "items": [{"menu_item_id": 99999, "quantity": 1}],
    })
    assert missing_item.status_code == 400

    # Blank address
    blank_addr = client.post("/orders", json={
        "restaurant_id": 1,
        "address": "   ",
        "items": [{"menu_item_id": 1, "quantity": 1}],
    })
    assert blank_addr.status_code == 400

    # Invalid item quantity (<= 0)
    zero_qty = client.post("/orders", json={
        "restaurant_id": 1,
        "address": "123 Main St",
        "items": [{"menu_item_id": 1, "quantity": 0}],
    })
    assert zero_qty.status_code == 422

    # 6. Order retrieval (valid & invalid)
    get_res = client.get(f"/orders/{order_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == order_id

    missing_order = client.get("/orders/99999")
    assert missing_order.status_code == 404

    # 7. Status patch valid & invalid
    # Valid transition PLACED -> PREPARING
    patch_prep = client.patch(f"/orders/{order_id}/status", json={"status": "PREPARING"})
    assert patch_prep.status_code == 200
    assert patch_prep.json()["status"] == "PREPARING"

    # Invalid transition (skipping READY to DELIVERED)
    bad_skip = client.patch(f"/orders/{order_id}/status", json={"status": "DELIVERED"})
    assert bad_skip.status_code == 400

    # Invalid status string
    bad_status = client.patch(f"/orders/{order_id}/status", json={"status": "FLYING"})
    assert bad_status.status_code == 400

    # Nonexistent order status patch
    bad_order_patch = client.patch("/orders/99999/status", json={"status": "PREPARING"})
    assert bad_order_patch.status_code == 404

    # 8. Order tracking endpoint (valid & invalid)
    tracking_res = client.get(f"/orders/{order_id}/tracking")
    assert tracking_res.status_code == 200
    track_body = tracking_res.json()
    assert track_body["order_id"] == order_id
    assert track_body["current_status"] == "PREPARING"
    assert len(track_body["history"]) == 2

    missing_tracking = client.get("/orders/99999/tracking")
    assert missing_tracking.status_code == 404
