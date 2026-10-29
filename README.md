# MiniDash

MiniDash is a lightweight baseline food-delivery REST API built in Python using **FastAPI** and **SQLite**. It demonstrates a clean, layered architecture and provides core ordering capabilities including restaurant discovery, menu exploration, order creation, order tracking, and status progression.

---

## 🏛 Layered Architecture

MiniDash strictly separates concerns across three primary architectural layers:

```
MiniDash/
├── app/
│   ├── __init__.py
│   ├── config.py              # Configuration & database path
│   ├── database.py            # SQLite connection, DDL, and auto-seeding
│   ├── exceptions.py          # Domain-level exceptions (NotFoundError, ValidationError)
│   ├── main.py                # FastAPI app setup, exception handlers, routers
│   ├── schemas/               # Pydantic validation & response models
│   │   ├── __init__.py
│   │   ├── restaurant.py
│   │   └── order.py
│   ├── repository/            # Data access layer (SQL queries & transactions)
│   │   ├── __init__.py
│   │   ├── restaurant_repo.py
│   │   └── order_repo.py
│   ├── services/              # Business logic & validation layer
│   │   ├── __init__.py
│   │   ├── restaurant_service.py
│   │   └── order_service.py
│   └── routes/                # HTTP API endpoints & routing
│       ├── __init__.py
│       ├── restaurant_routes.py
│       └── order_routes.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # Pytest fixtures & isolated test DB setup
│   ├── test_client.py         # Zero-dependency ASGI test client
│   ├── test_restaurants.py    # Tests for restaurant & menu endpoints
│   └── test_orders.py         # Tests for order endpoints
├── requirements.txt           # fastapi, uvicorn, pytest
└── README.md
```

1. **Routes (`app/routes/`)**: Receives HTTP requests, coordinates with FastAPI dependency injection, validates parameters, and delegates business tasks to the service layer.
2. **Services (`app/services/`)**: Enforces business logic and domain invariants:
   - Verifies restaurant existence before order placement or menu lookups.
   - Ensures all ordered items belong to the requested restaurant.
   - Calculates total price from persisted menu item unit prices.
   - Validates order status transitions against allowed lifecycle states.
3. **Repository (`app/repository/`)**: Executes raw SQLite operations with `sqlite3.Row` and foreign key constraints enabled. Atomic operations (such as creating an order and its items) execute inside transactions.

---

## 🗄 Database Schema

The database uses SQLite with 4 tables:

- **`restaurants`**: `(id, name, cuisine, opens_at, closes_at, avg_prep_minutes)`
- **`menu_items`**: `(id, restaurant_id, name, price_cents)`
- **`orders`**: `(id, restaurant_id, status, total_cents, address, created_at)`
- **`order_items`**: `(id, order_id, menu_item_id, quantity, unit_price_cents)`

### Seeded Restaurants
On initial startup, 5 restaurants with realistic menus are automatically seeded:
1. **Burger Haven** (American, 10:00 - 22:00, 20 min prep)
2. **Pasta Paradiso** (Italian, 11:00 - 22:30, 25 min prep)
3. **Tokyo Ramen Bar** (Japanese, 11:30 - 23:00, 15 min prep)
4. **Taco Fiesta** (Mexican, 09:30 - 21:30, 15 min prep)
5. **Spice of India** (Indian, 12:00 - 22:00, 30 min prep)

---

## 🚀 Quickstart & Run Instructions

### 1. Prerequisites
- Python 3.10+ (Standard library `sqlite3` is included with Python)

### 2. Setup Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
Only the 3 required packages are included:
```bash
pip install -r requirements.txt
```

### 4. Run the API Server
Start the development server with Uvicorn:
```bash
uvicorn app.main:app --reload --port 8000
```

Once running:
- **Interactive OpenAPI Documentation (Swagger UI)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Documentation**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 🧪 Running Tests

MiniDash includes comprehensive tests covering every endpoint and validation rule.

Run the test suite using pytest:
```bash
pytest
```

To run with verbose output:
```bash
pytest -v
```

> **Note**: Tests run against an isolated, temporary SQLite database generated per test run and use a standard library ASGI test client, ensuring zero extra dependencies and no test interference with development databases.

---

## 📡 API Reference & Endpoints

### 1. `GET /restaurants`
List all available restaurants.

**Request:**
```bash
curl -X GET http://127.0.0.1:8000/restaurants
```

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "name": "Burger Haven",
    "cuisine": "American",
    "opens_at": "10:00",
    "closes_at": "22:00",
    "avg_prep_minutes": 20
  },
  {
    "id": 2,
    "name": "Pasta Paradiso",
    "cuisine": "Italian",
    "opens_at": "11:00",
    "closes_at": "22:30",
    "avg_prep_minutes": 25
  }
]
```

---

### 2. `GET /restaurants/{id}/menu`
Retrieve the menu for a given restaurant.

**Request:**
```bash
curl -X GET http://127.0.0.1:8000/restaurants/1/menu
```

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "restaurant_id": 1,
    "name": "Classic Smashburger",
    "price_cents": 1099
  },
  {
    "id": 2,
    "restaurant_id": 1,
    "name": "Double Bacon Burger",
    "price_cents": 1499
  },
  {
    "id": 3,
    "restaurant_id": 1,
    "name": "Seasoned Fries",
    "price_cents": 499
  },
  {
    "id": 4,
    "restaurant_id": 1,
    "name": "Vanilla Shake",
    "price_cents": 599
  }
]
```

**Errors:**
- `404 Not Found` if the restaurant does not exist.

---

### 3. `POST /orders`
Place a new food order.

**Request:**
```bash
curl -X POST http://127.0.0.1:8000/orders \
  -H "Content-Type: application/json" \
  -d '{
    "restaurant_id": 1,
    "address": "123 Main St, Apt 4B",
    "items": [
      {
        "menu_item_id": 1,
        "quantity": 2
      },
      {
        "menu_item_id": 3,
        "quantity": 1
      }
    ]
  }'
```

**Response (201 Created):**
```json
{
  "id": 1,
  "restaurant_id": 1,
  "status": "PENDING",
  "total_cents": 2697,
  "address": "123 Main St, Apt 4B",
  "created_at": "2026-10-29T15:20:00.000000+00:00",
  "items": [
    {
      "id": 1,
      "order_id": 1,
      "menu_item_id": 1,
      "name": "Classic Smashburger",
      "quantity": 2,
      "unit_price_cents": 1099
    },
    {
      "id": 2,
      "order_id": 1,
      "menu_item_id": 3,
      "name": "Seasoned Fries",
      "quantity": 1,
      "unit_price_cents": 499
    }
  ]
}
```

**Errors:**
- `404 Not Found` if the restaurant does not exist.
- `400 Bad Request` if any item is not found, does not belong to the restaurant, or if the address is empty.
- `422 Unprocessable Entity` if request fields or item quantities are invalid (e.g. quantity `<= 0`).

---

### 4. `GET /orders/{id}`
Retrieve order details and line items by ID.

**Request:**
```bash
curl -X GET http://127.0.0.1:8000/orders/1
```

**Response (200 OK):**
```json
{
  "id": 1,
  "restaurant_id": 1,
  "status": "PENDING",
  "total_cents": 2697,
  "address": "123 Main St, Apt 4B",
  "created_at": "2026-10-29T15:20:00.000000+00:00",
  "items": [
    {
      "id": 1,
      "order_id": 1,
      "menu_item_id": 1,
      "name": "Classic Smashburger",
      "quantity": 2,
      "unit_price_cents": 1099
    },
    {
      "id": 2,
      "order_id": 1,
      "menu_item_id": 3,
      "name": "Seasoned Fries",
      "quantity": 1,
      "unit_price_cents": 499
    }
  ]
}
```

**Errors:**
- `404 Not Found` if order does not exist.

---

### 5. `PATCH /orders/{id}/status`
Update an order's status.

**Allowed Statuses:**
- `PENDING`
- `PREPARING`
- `OUT_FOR_DELIVERY`
- `DELIVERED`
- `CANCELLED`

**Request:**
```bash
curl -X PATCH http://127.0.0.1:8000/orders/1/status \
  -H "Content-Type: application/json" \
  -d '{
    "status": "PREPARING"
  }'
```

**Response (200 OK):**
```json
{
  "id": 1,
  "restaurant_id": 1,
  "status": "PREPARING",
  "total_cents": 2697,
  "address": "123 Main St, Apt 4B",
  "created_at": "2026-10-29T15:20:00.000000+00:00",
  "items": [
    {
      "id": 1,
      "order_id": 1,
      "menu_item_id": 1,
      "name": "Classic Smashburger",
      "quantity": 2,
      "unit_price_cents": 1099
    },
    {
      "id": 2,
      "order_id": 1,
      "menu_item_id": 3,
      "name": "Seasoned Fries",
      "quantity": 1,
      "unit_price_cents": 499
    }
  ]
}
```

**Errors:**
- `404 Not Found` if order does not exist.
- `400 Bad Request` if an invalid status value is supplied.
