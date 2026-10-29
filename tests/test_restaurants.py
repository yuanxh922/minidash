def test_get_restaurants(client):
    """Test GET /restaurants returns 200 and the 5 seeded restaurants."""
    response = client.get("/restaurants")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 5

    restaurant_names = [r["name"] for r in data]
    assert "Burger Haven" in restaurant_names
    assert "Pasta Paradiso" in restaurant_names
    assert "Tokyo Ramen Bar" in restaurant_names
    assert "Taco Fiesta" in restaurant_names
    assert "Spice of India" in restaurant_names

    first = data[0]
    assert "id" in first
    assert "name" in first
    assert "cuisine" in first
    assert "opens_at" in first
    assert "closes_at" in first
    assert "avg_prep_minutes" in first


def test_get_restaurant_menu_success(client):
    """Test GET /restaurants/{id}/menu returns 200 and items for a valid restaurant."""
    response = client.get("/restaurants/1/menu")
    assert response.status_code == 200

    items = response.json()
    assert isinstance(items, list)
    assert len(items) == 4

    item_names = [item["name"] for item in items]
    assert "Classic Smashburger" in item_names
    assert "Seasoned Fries" in item_names

    first_item = items[0]
    assert first_item["restaurant_id"] == 1
    assert "id" in first_item
    assert "price_cents" in first_item
    assert first_item["price_cents"] > 0


def test_get_restaurant_menu_not_found(client):
    """Test GET /restaurants/{id}/menu returns 404 when restaurant does not exist."""
    response = client.get("/restaurants/9999/menu")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "9999" in data["detail"]
