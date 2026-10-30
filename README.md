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
│   ├── database.py            # SQLite connection, DDL migrations, and auto-seeding
│   ├── exceptions.py          # Domain exceptions (NotFoundError, ValidationError, ConflictError)
│   ├── main.py                # FastAPI app setup, exception handlers, routers
│   ├── static/
│   │   └── index.html         # Responsive vanilla single-page UI (ordering & live SSE tracking)
│   ├── schemas/               # Pydantic validation & response models
│   │   ├── __init__.py
│   │   ├── restaurant.py      # Restaurant & menu response schemas
│   │   └── order.py           # Order, OrderStatus enum, ETA, tracking snapshot & history models
│   ├── repository/            # Data access layer (SQL queries & atomic transactions)
│   │   ├── __init__.py
│   │   ├── restaurant_repo.py # Restaurant & menu queries
│   │   └── order_repo.py      # Atomic order creation, FSM updates & tracking history
│   ├── services/              # Business logic & domain engine layer
│   │   ├── __init__.py
│   │   ├── restaurant_service.py # Restaurant & menu business logic
│   │   ├── order_service.py      # Order placement, FSM lifecycle & tracking queries
│   │   ├── eta_calculator.py     # Pure deterministic ETA calculation engine (Track C)
│   │   └── broadcaster.py        # In-memory pub/sub for real-time SSE streaming (Track C)
│   └── routes/                # HTTP API & streaming endpoints
│       ├── __init__.py
│       ├── frontend_routes.py   # Web frontend & dashboard routes
│       ├── restaurant_routes.py # Restaurant & menu REST endpoints
│       └── order_routes.py      # Order CRUD, tracking snapshot & SSE stream
├── docs/                      # Engineering specifications & reports
│   ├── requirements.md        # EARS acceptance criteria & requirements
│   ├── design.md              # Architectural design & FSM state machine
│   ├── tasks.md               # 8-slice test-driven implementation plan
│   ├── REFLECTION_PROMPTS.md  # Section 7 reflection responses (Markdown)
│   ├── reflection_prompts.html# Printable reflection report source
│   └── reflection_prompts.pdf # Compiled reflection report (PDF)
├── scripts/
│   └── simulate_driver.py     # Driver advancement simulator CLI (Track C)
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # Pytest fixtures & isolated test DB setup
│   ├── test_client.py         # Zero-dependency ASGI test client
│   ├── test_frontend.py       # Tests for frontend UI & content negotiation
│   ├── test_restaurants.py    # Tests for restaurant & menu endpoints
│   ├── test_orders.py         # Tests for order endpoints
│   ├── test_schema.py         # Schema & migration tests (Slice 1)
│   ├── test_eta.py            # Deterministic ETA engine tests (Slice 3)
│   ├── test_fsm.py            # FSM transition tests (Slice 4)
│   ├── test_tracking.py       # Tracking snapshot tests (Slice 5)
│   ├── test_sse.py            # Server-Sent Events tests (Slice 6)
│   ├── test_simulator.py      # Driver simulator CLI tests (Slice 7)
│   └── test_e2e_tracking.py   # Full lifecycle E2E & regression tests (Slice 8)
├── AI_LOG.md                  # Comprehensive AI interaction log
├── requirements.txt           # fastapi, uvicorn, pytest
└── README.md
```

1. **Routes (`app/routes/`)**: Receives HTTP and streaming requests, coordinates FastAPI dependency injection, validates parameters, and delegates business workflows to the service layer:
   - Exposes REST endpoints for restaurant discovery and order management.
   - Provides live order tracking polling snapshot (`GET /orders/{id}/tracking`).
   - Serves reactive Server-Sent Events stream (`GET /orders/{id}/tracking/stream`) with `text/event-stream`.
2. **Services (`app/services/`)**: Enforces core domain invariants, lifecycle state machines, and real-time event broadcasting:
   - **Order Lifecycle FSM**: Strictly enforces valid forward state transitions (`PLACED` -> `PREPARING` -> `READY` -> `PICKED_UP` -> `DELIVERED`), conditional cancellation (`PLACED` only), and immutable terminal states (`DELIVERED`, `CANCELLED`).
   - **Deterministic ETA Engine (`eta_calculator.py`)**: Pure functional calculator computing estimated arrival times based on restaurant preparation baseline, line item count, and current status transit offsets.
   - **In-Memory Broadcaster (`broadcaster.py`)**: Thread-safe pub/sub engine using `asyncio.Queue` to push live status updates to active SSE clients with guaranteed subscriber cleanup on disconnect.
   - **Cart & Restaurant Invariants**: Verifies restaurant hours and item association, calculating total pricing from database unit prices.
3. **Repository (`app/repository/`)**: Executes raw SQLite operations with `sqlite3.Row` and foreign key constraints enabled. Wraps state updates and audit logging inside atomic database transactions (`BEGIN IMMEDIATE ... COMMIT / ROLLBACK`), ensuring `orders` and `order_status_history` are updated synchronously with zero partial writes.

---

## 🗄 Database Schema

The database uses SQLite with 5 tables:

- **`restaurants`**: `(id, name, cuisine, opens_at, closes_at, avg_prep_minutes)`
- **`menu_items`**: `(id, restaurant_id, name, price_cents)`
- **`orders`**: `(id, restaurant_id, status, total_cents, address, created_at, estimated_arrival_at)`
- **`order_items`**: `(id, order_id, menu_item_id, quantity, unit_price_cents)`
- **`order_status_history`**: `(id, order_id, status, timestamp)` &mdash; indexed on `order_id` to provide a strictly chronological audit history of lifecycle events.

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
- **Interactive Web Frontend**: [http://127.0.0.1:8000/ui](http://127.0.0.1:8000/ui) (or [http://127.0.0.1:8000/](http://127.0.0.1:8000/) directly in any browser)
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
  "status": "PLACED",
  "total_cents": 2697,
  "address": "123 Main St, Apt 4B",
  "created_at": "2026-10-29T15:20:00.000000+00:00",
  "estimated_arrival_at": "2026-10-29T15:46:00+00:00",
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
  "status": "PLACED",
  "total_cents": 2697,
  "address": "123 Main St, Apt 4B",
  "created_at": "2026-10-29T15:20:00.000000+00:00",
  "estimated_arrival_at": "2026-10-29T15:46:00+00:00",
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
Update an order's status following strict finite state machine (FSM) lifecycle transitions.

**Allowed Statuses:**
- `PLACED` (initial state)
- `PREPARING`
- `READY`
- `PICKED_UP`
- `DELIVERED` (terminal state)
- `CANCELLED` (terminal state, allowed only from `PLACED`)

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
  "estimated_arrival_at": "2026-10-29T15:46:00+00:00",
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
- `400 Bad Request` if an unrecognized status string is supplied.
- `404 Not Found` if order does not exist.
- `409 Conflict` if the requested transition violates the FSM transition rules or attempts to modify a terminal order (`DELIVERED` or `CANCELLED`).

---

### 6. `GET /orders/{id}/tracking`
Retrieve the current live tracking snapshot, dynamic ETA, and full chronological status history for an order.

**Request:**
```bash
curl -X GET http://127.0.0.1:8000/orders/1/tracking
```

**Response (200 OK):**
```json
{
  "order_id": 1,
  "current_status": "PREPARING",
  "estimated_arrival_at": "2026-10-29T15:46:00+00:00",
  "history": [
    {
      "status": "PLACED",
      "timestamp": "2026-10-29T15:20:00+00:00"
    },
    {
      "status": "PREPARING",
      "timestamp": "2026-10-29T15:24:00+00:00"
    }
  ]
}
```

**Errors:**
- `404 Not Found` if order does not exist.

---

### 7. `GET /orders/{id}/tracking/stream`
Stream real-time tracking events for an order using Server-Sent Events (SSE). Emits the current snapshot immediately upon connection, pushes events on status transitions, and automatically terminates the stream when the order reaches a terminal state (`DELIVERED` or `CANCELLED`).

**Request:**
```bash
curl -N -H "Accept: text/event-stream" http://127.0.0.1:8000/orders/1/tracking/stream
```

**Stream Output (`text/event-stream`):**
```
data: {"order_id": 1, "current_status": "PREPARING", "estimated_arrival_at": "2026-10-29T15:46:00+00:00", "history": [{"status": "PLACED", "timestamp": "2026-10-29T15:20:00+00:00"}, {"status": "PREPARING", "timestamp": "2026-10-29T15:24:00+00:00"}]}

data: {"order_id": 1, "current_status": "READY", "estimated_arrival_at": "2026-10-29T15:44:00+00:00", "history": [{"status": "PLACED", "timestamp": "2026-10-29T15:20:00+00:00"}, {"status": "PREPARING", "timestamp": "2026-10-29T15:24:00+00:00"}, {"status": "READY", "timestamp": "2026-10-29T15:29:00+00:00"}]}
```

---

### 8. `GET /ui` & `GET /` (Web Frontend)
Serves the responsive single-page application for restaurant browsing, interactive order placement, and live real-time order tracking with Server-Sent Events.

- **URL**: `http://127.0.0.1:8000/ui` or `http://127.0.0.1:8000/` (when accessed via a browser)
- **Features**:
  - Restaurant discovery with cuisine tags, hours, and average prep time.
  - Interactive menu selection with real-time cart subtotal calculation.
  - One-click order submission with delivery address validation.
  - Live tracking view with visual 5-stage FSM progress stepper and live ETA display.
  - Real-time reactive updates via Server-Sent Events (`EventSource`).
  - Interactive simulation controls: advance stage, cancel order, and auto-simulate delivery.

---

## 🚗 Driver Simulator CLI

MiniDash provides an automated driver advancement simulator CLI to step an active order through all remaining lifecycle stages (`PLACED` -> `PREPARING` -> `READY` -> `PICKED_UP` -> `DELIVERED`).

```bash
# Advance order #1 with a 1.5s delay between status transitions
python -m scripts.simulate_driver --order-id 1 --delay 1.5

# Advance order #1 against custom base URL with verbose logging
python -m scripts.simulate_driver --order-id 1 --base-url http://127.0.0.1:8000 --verbose
```
