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


def test_fsm_happy_path_lifecycle(client):
    """Test full happy path lifecycle: PLACED -> PREPARING -> READY -> PICKED_UP -> DELIVERED."""
    order = _create_order(client)
    order_id = order["id"]
    assert order["status"] == "PLACED"
    placed_eta = order["estimated_arrival_at"]
    assert placed_eta is not None

    # PLACED -> PREPARING
    res = client.patch(f"/orders/{order_id}/status", json={"status": "PREPARING"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "PREPARING"
    preparing_eta = data["estimated_arrival_at"]
    assert preparing_eta is not None

    # PREPARING -> READY
    res = client.patch(f"/orders/{order_id}/status", json={"status": "READY"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "READY"
    ready_eta = data["estimated_arrival_at"]
    assert ready_eta is not None

    # READY -> PICKED_UP
    res = client.patch(f"/orders/{order_id}/status", json={"status": "PICKED_UP"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "PICKED_UP"
    picked_up_eta = data["estimated_arrival_at"]
    assert picked_up_eta is not None

    # PICKED_UP -> DELIVERED
    res = client.patch(f"/orders/{order_id}/status", json={"status": "DELIVERED"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "DELIVERED"
    delivered_eta = data["estimated_arrival_at"]
    assert delivered_eta is not None


def test_fsm_cancellation_allowed_only_in_placed(client):
    """Test cancellation is allowed in PLACED but rejected with 400 from PREPARING."""
    # 1. PLACED -> CANCELLED succeeds
    order1 = _create_order(client)
    order1_id = order1["id"]
    res1 = client.patch(f"/orders/{order1_id}/status", json={"status": "CANCELLED"})
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] == "CANCELLED"
    assert data1["estimated_arrival_at"] is None

    # 2. PREPARING -> CANCELLED fails with 400
    order2 = _create_order(client)
    order2_id = order2["id"]
    prep_res = client.patch(f"/orders/{order2_id}/status", json={"status": "PREPARING"})
    assert prep_res.status_code == 200

    cancel_res = client.patch(f"/orders/{order2_id}/status", json={"status": "CANCELLED"})
    assert cancel_res.status_code == 400
    detail = cancel_res.json()["detail"]
    assert "Cannot cancel order" in detail or "Cancellation is only permitted when PLACED" in detail


def test_fsm_rejects_skipping_stages(client, db_conn):
    """Test that skipping stages (e.g., PLACED -> READY) returns 400 and does not change DB."""
    order = _create_order(client)
    order_id = order["id"]

    res = client.patch(f"/orders/{order_id}/status", json={"status": "READY"})
    assert res.status_code == 400
    assert "detail" in res.json()

    # Verify orders table remains unchanged
    cur = db_conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,))
    row = cur.fetchone()
    assert row["status"] == "PLACED"

    # Verify order_status_history has only 1 row (initial PLACED creation)
    cur = db_conn.execute("SELECT status FROM order_status_history WHERE order_id = ?", (order_id,))
    history_rows = cur.fetchall()
    assert len(history_rows) == 1
    assert history_rows[0]["status"] == "PLACED"


def test_fsm_rejects_terminal_state_modifications(client):
    """Test that DELIVERED and CANCELLED reject further transitions with 400."""
    # DELIVERED order cannot be modified
    order1 = _create_order(client)
    order1_id = order1["id"]
    client.patch(f"/orders/{order1_id}/status", json={"status": "PREPARING"})
    client.patch(f"/orders/{order1_id}/status", json={"status": "READY"})
    client.patch(f"/orders/{order1_id}/status", json={"status": "PICKED_UP"})
    client.patch(f"/orders/{order1_id}/status", json={"status": "DELIVERED"})

    res_delivered_to_pickup = client.patch(f"/orders/{order1_id}/status", json={"status": "PICKED_UP"})
    assert res_delivered_to_pickup.status_code == 400

    res_delivered_to_cancelled = client.patch(f"/orders/{order1_id}/status", json={"status": "CANCELLED"})
    assert res_delivered_to_cancelled.status_code == 400

    # CANCELLED order cannot be modified
    order2 = _create_order(client)
    order2_id = order2["id"]
    res_cancel = client.patch(f"/orders/{order2_id}/status", json={"status": "CANCELLED"})
    assert res_cancel.status_code == 200

    res_cancelled_to_prep = client.patch(f"/orders/{order2_id}/status", json={"status": "PREPARING"})
    assert res_cancelled_to_prep.status_code == 400


def test_fsm_rejects_invalid_status_string(client):
    """Test that PATCH with invalid status string returns 400 listing valid statuses."""
    order = _create_order(client)
    order_id = order["id"]

    res = client.patch(f"/orders/{order_id}/status", json={"status": "COOKING"})
    assert res.status_code == 400
    detail = res.json()["detail"]
    assert "COOKING" in detail
    for valid_status in ["PLACED", "PREPARING", "READY", "PICKED_UP", "DELIVERED", "CANCELLED"]:
        assert valid_status in detail
