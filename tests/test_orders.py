def test_create_order_success(client):
    """Test POST /orders successfully places an order and calculates total_cents."""
    # Restaurant 1 has menu items: Classic Smashburger (1099) and Seasoned Fries (499)
    # Total for 2 burgers and 1 fries = 2 * 1099 + 1 * 499 = 2198 + 499 = 2697
    payload = {
        "restaurant_id": 1,
        "address": "456 Elm St, Suite 2",
        "items": [
            {"menu_item_id": 1, "quantity": 2},
            {"menu_item_id": 3, "quantity": 1},
        ],
    }
    response = client.post("/orders", json=payload)
    assert response.status_code == 201

    order = response.json()
    assert order["id"] is not None
    assert order["restaurant_id"] == 1
    assert order["status"] == "PENDING"
    assert order["address"] == "456 Elm St, Suite 2"
    assert order["total_cents"] == 2697
    assert "created_at" in order
    assert len(order["items"]) == 2

    # Check item details
    item1 = order["items"][0]
    assert item1["menu_item_id"] == 1
    assert item1["quantity"] == 2
    assert item1["unit_price_cents"] == 1099
    assert item1["name"] == "Classic Smashburger"


def test_create_order_nonexistent_restaurant(client):
    """Test POST /orders returns 404 if restaurant does not exist."""
    payload = {
        "restaurant_id": 9999,
        "address": "123 Main St",
        "items": [{"menu_item_id": 1, "quantity": 1}],
    }
    response = client.post("/orders", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "9999" in data["detail"]


def test_create_order_item_from_wrong_restaurant(client):
    """Test POST /orders returns 400 if menu item belongs to another restaurant."""
    # Restaurant 1 menu items are 1..4. Menu item 5 belongs to Restaurant 2.
    payload = {
        "restaurant_id": 1,
        "address": "123 Main St",
        "items": [
            {"menu_item_id": 1, "quantity": 1},
            {"menu_item_id": 5, "quantity": 1},
        ],
    }
    response = client.post("/orders", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "does not belong" in data["detail"]


def test_create_order_nonexistent_menu_item(client):
    """Test POST /orders returns 400 if menu item ID does not exist."""
    payload = {
        "restaurant_id": 1,
        "address": "123 Main St",
        "items": [{"menu_item_id": 9999, "quantity": 1}],
    }
    response = client.post("/orders", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"]


def test_create_order_invalid_quantity(client):
    """Test POST /orders returns 422 if quantity is <= 0."""
    payload = {
        "restaurant_id": 1,
        "address": "123 Main St",
        "items": [{"menu_item_id": 1, "quantity": 0}],
    }
    response = client.post("/orders", json=payload)
    assert response.status_code == 422


def test_create_order_empty_address(client):
    """Test POST /orders returns 400 if address is blank."""
    payload = {
        "restaurant_id": 1,
        "address": "   ",
        "items": [{"menu_item_id": 1, "quantity": 1}],
    }
    response = client.post("/orders", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data


def test_get_order_success(client):
    """Test GET /orders/{id} retrieves placed order."""
    # Place an order first
    create_res = client.post(
        "/orders",
        json={
            "restaurant_id": 2,
            "address": "789 Pine Rd",
            "items": [{"menu_item_id": 5, "quantity": 2}],
        },
    )
    assert create_res.status_code == 201
    created_id = create_res.json()["id"]

    # Now retrieve it
    get_res = client.get(f"/orders/{created_id}")
    assert get_res.status_code == 200
    order = get_res.json()
    assert order["id"] == created_id
    assert order["restaurant_id"] == 2
    assert order["address"] == "789 Pine Rd"
    assert len(order["items"]) == 1
    assert order["items"][0]["menu_item_id"] == 5


def test_get_order_not_found(client):
    """Test GET /orders/{id} returns 404 for non-existent order."""
    response = client.get("/orders/9999")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "9999" in data["detail"]


def test_update_order_status_success(client):
    """Test PATCH /orders/{id}/status successfully updates status."""
    create_res = client.post(
        "/orders",
        json={
            "restaurant_id": 1,
            "address": "100 Broadway",
            "items": [{"menu_item_id": 1, "quantity": 1}],
        },
    )
    assert create_res.status_code == 201
    order_id = create_res.json()["id"]

    # Update to PREPARING
    patch_res = client.patch(f"/orders/{order_id}/status", json={"status": "PREPARING"})
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "PREPARING"

    # Update to OUT_FOR_DELIVERY
    patch_res2 = client.patch(f"/orders/{order_id}/status", json={"status": "OUT_FOR_DELIVERY"})
    assert patch_res2.status_code == 200
    assert patch_res2.json()["status"] == "OUT_FOR_DELIVERY"

    # Verify through GET
    get_res = client.get(f"/orders/{order_id}")
    assert get_res.json()["status"] == "OUT_FOR_DELIVERY"


def test_update_order_status_invalid(client):
    """Test PATCH /orders/{id}/status returns 400 for invalid status string."""
    create_res = client.post(
        "/orders",
        json={
            "restaurant_id": 1,
            "address": "100 Broadway",
            "items": [{"menu_item_id": 1, "quantity": 1}],
        },
    )
    order_id = create_res.json()["id"]

    patch_res = client.patch(f"/orders/{order_id}/status", json={"status": "FLYING_DRONE"})
    assert patch_res.status_code == 400
    data = patch_res.json()
    assert "detail" in data
    assert "Invalid status" in data["detail"]


def test_update_order_status_not_found(client):
    """Test PATCH /orders/{id}/status returns 404 for non-existent order."""
    response = client.patch("/orders/9999/status", json={"status": "DELIVERED"})
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "9999" in data["detail"]
