import pytest


pytestmark = pytest.mark.anyio


async def test_sse_headers_and_initial_snapshot(async_client):
    """Test connecting to /orders/{id}/tracking/stream verifies headers and initial snapshot."""
    # 1. Create a test order
    create_res = await async_client.post(
        "/orders",
        json={
            "restaurant_id": 1,
            "address": "123 Main St",
            "items": [{"menu_item_id": 1, "quantity": 2}],
        },
    )
    assert create_res.status_code == 201
    order_id = create_res.json()["id"]

    # 2. Connect to tracking stream
    async with async_client.stream("GET", f"/orders/{order_id}/tracking/stream") as stream:
        assert stream.status_code == 200
        content_type = stream.headers.get("content-type", "")
        assert content_type.startswith("text/event-stream")
        assert stream.headers.get("cache-control") == "no-cache"
        assert stream.headers.get("connection") == "keep-alive"

        # 3. Read first frame and verify initial state
        first_event = await stream.read_event()
        assert first_event is not None
        assert first_event["event"] == "tracking_update"
        assert "event: tracking_update" in first_event["raw"]

        data = first_event["data"]
        assert data["order_id"] == order_id
        assert data["current_status"] == "PLACED"
        assert data["estimated_arrival_at"] is not None
        assert len(data["history"]) == 1
        assert data["history"][0]["status"] == "PLACED"


async def test_sse_reactive_push_on_status_change(async_client):
    """Test that PATCH /orders/{id}/status pushes a new event frame to active stream subscribers."""
    # 1. Create order
    create_res = await async_client.post(
        "/orders",
        json={
            "restaurant_id": 1,
            "address": "456 Oak St",
            "items": [{"menu_item_id": 1, "quantity": 1}],
        },
    )
    assert create_res.status_code == 201
    order_id = create_res.json()["id"]

    # 2. Connect to stream
    async with async_client.stream("GET", f"/orders/{order_id}/tracking/stream") as stream:
        # First event is initial snapshot
        first_event = await stream.read_event()
        assert first_event is not None
        assert first_event["data"]["current_status"] == "PLACED"

        # 3. Patch status to PREPARING
        patch_res = await async_client.patch(
            f"/orders/{order_id}/status",
            json={"status": "PREPARING"},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["status"] == "PREPARING"

        # 4. Stream subscriber receives pushed event frame
        second_event = await stream.read_event()
        assert second_event is not None
        assert second_event["event"] == "tracking_update"
        assert second_event["data"]["order_id"] == order_id
        assert second_event["data"]["current_status"] == "PREPARING"
        assert len(second_event["data"]["history"]) == 2
        assert second_event["data"]["history"][1]["status"] == "PREPARING"


async def test_sse_stream_closes_on_terminal_state(async_client):
    """Test that advancing order to DELIVERED emits the final frame and cleanly terminates the stream."""
    # 1. Create order
    create_res = await async_client.post(
        "/orders",
        json={
            "restaurant_id": 1,
            "address": "789 Pine St",
            "items": [{"menu_item_id": 1, "quantity": 1}],
        },
    )
    assert create_res.status_code == 201
    order_id = create_res.json()["id"]

    # 2. Connect to stream and advance lifecycle to DELIVERED
    async with async_client.stream("GET", f"/orders/{order_id}/tracking/stream") as stream:
        init_event = await stream.read_event()
        assert init_event["data"]["current_status"] == "PLACED"

        # Advance through valid transitions
        for next_status in ["PREPARING", "READY", "PICKED_UP", "DELIVERED"]:
            patch_res = await async_client.patch(
                f"/orders/{order_id}/status",
                json={"status": next_status},
            )
            assert patch_res.status_code == 200

            event = await stream.read_event()
            assert event is not None
            assert event["event"] == "tracking_update"
            assert event["data"]["current_status"] == next_status

        # 3. Stream should cleanly terminate upon reaching DELIVERED
        terminal_eof = await stream.read_event(timeout=2.0)
        assert terminal_eof is None

    # 4. Connect to an already terminal order (CANCELLED) and verify immediate termination after initial frame
    cancel_order = await async_client.post(
        "/orders",
        json={
            "restaurant_id": 1,
            "address": "321 Elm St",
            "items": [{"menu_item_id": 1, "quantity": 1}],
        },
    )
    cancel_id = cancel_order.json()["id"]
    cancel_patch = await async_client.patch(
        f"/orders/{cancel_id}/status",
        json={"status": "CANCELLED"},
    )
    assert cancel_patch.status_code == 200

    async with async_client.stream("GET", f"/orders/{cancel_id}/tracking/stream") as stream:
        assert stream.status_code == 200
        terminal_event = await stream.read_event()
        assert terminal_event is not None
        assert terminal_event["data"]["current_status"] == "CANCELLED"

        # Verify immediate EOF
        assert await stream.read_event(timeout=2.0) is None


async def test_sse_order_not_found(async_client):
    """Test that requesting the SSE stream for a non-existent order ID returns HTTP 404."""
    # Test via direct get
    res = await async_client.get("/orders/99999/tracking/stream")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()

    # Test via stream
    async with async_client.stream("GET", "/orders/99999/tracking/stream") as stream:
        assert stream.status_code == 404
        data = await stream.json()
        assert "not found" in data["detail"].lower()
