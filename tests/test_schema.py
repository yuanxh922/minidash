import pytest
from pydantic import ValidationError as PydanticValidationError

from app.schemas.order import (
    OrderStatus,
    OrderTrackingResponse,
    TrackingHistoryItem,
    OrderResponse,
    OrderStatusUpdate,
)


def test_order_status_history_table_exists(db_conn):
    """Verify order_status_history table and index exist with correct schema."""
    # 1. Query sqlite_master for table order_status_history
    cur = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='order_status_history';"
    )
    table_row = cur.fetchone()
    assert table_row is not None, "Table 'order_status_history' does not exist in sqlite_master"
    assert table_row["name"] == "order_status_history"

    # 2. Verify column structure: id (INTEGER, PK), order_id (INTEGER, NOT NULL), status (TEXT, NOT NULL), timestamp (TEXT, NOT NULL)
    cur = db_conn.execute("PRAGMA table_info(order_status_history);")
    columns = {row["name"]: row for row in cur.fetchall()}

    assert "id" in columns, "Column 'id' missing from order_status_history"
    assert columns["id"]["type"].upper() == "INTEGER"
    assert columns["id"]["pk"] >= 1

    assert "order_id" in columns, "Column 'order_id' missing from order_status_history"
    assert columns["order_id"]["type"].upper() == "INTEGER"
    assert columns["order_id"]["notnull"] == 1

    assert "status" in columns, "Column 'status' missing from order_status_history"
    assert columns["status"]["type"].upper() == "TEXT"
    assert columns["status"]["notnull"] == 1

    assert "timestamp" in columns, "Column 'timestamp' missing from order_status_history"
    assert columns["timestamp"]["type"].upper() == "TEXT"
    assert columns["timestamp"]["notnull"] == 1

    # 3. Query PRAGMA index_list('order_status_history') and verify idx_order_status_history_order_id exists
    cur = db_conn.execute("PRAGMA index_list('order_status_history');")
    indexes = [row["name"] for row in cur.fetchall()]
    assert "idx_order_status_history_order_id" in indexes, (
        f"Index 'idx_order_status_history_order_id' not found in indexes: {indexes}"
    )


def test_orders_table_has_estimated_arrival_at_column(db_conn):
    """Verify orders table has estimated_arrival_at column with TEXT type."""
    cur = db_conn.execute("PRAGMA table_info(orders);")
    columns = {row["name"]: row for row in cur.fetchall()}
    assert "estimated_arrival_at" in columns, "Column 'estimated_arrival_at' missing from orders"
    assert columns["estimated_arrival_at"]["type"].upper() == "TEXT"


def test_order_status_enum_and_schemas():
    """Verify OrderStatus enum values, Pydantic validation, and tracking schema serialization."""
    # 1. Instantiates OrderStatus with all valid statuses and asserts exact string values
    expected_statuses = {
        "PLACED": "PLACED",
        "PREPARING": "PREPARING",
        "READY": "READY",
        "PICKED_UP": "PICKED_UP",
        "DELIVERED": "DELIVERED",
        "CANCELLED": "CANCELLED",
    }
    for name, value in expected_statuses.items():
        enum_member = OrderStatus[name]
        assert enum_member.value == value
        assert OrderStatus(value) == enum_member

    assert len(OrderStatus) == 6

    # 2. Validates that invalid status string raises ValidationError in Pydantic
    with pytest.raises(PydanticValidationError):
        TrackingHistoryItem(status="INVALID_STATUS", timestamp="2026-10-30T12:00:00Z")

    with pytest.raises(PydanticValidationError):
        OrderTrackingResponse(
            order_id=1,
            current_status="INVALID_STATUS",
            estimated_arrival_at=None,
            history=[],
        )

    # 3. Serializes and deserializes OrderTrackingResponse and TrackingHistoryItem ensuring valid ISO timestamps
    valid_ts = "2026-10-30T14:30:00Z"
    history_item = TrackingHistoryItem(status=OrderStatus.PLACED, timestamp=valid_ts)
    assert history_item.status == OrderStatus.PLACED
    assert history_item.timestamp == valid_ts

    tracking_data = {
        "order_id": 42,
        "current_status": "PLACED",
        "estimated_arrival_at": "2026-10-30T15:05:00Z",
        "history": [
            {"status": "PLACED", "timestamp": valid_ts}
        ],
    }

    response_obj = OrderTrackingResponse.model_validate(tracking_data)
    assert response_obj.order_id == 42
    assert response_obj.current_status == OrderStatus.PLACED
    assert response_obj.estimated_arrival_at == "2026-10-30T15:05:00Z"
    assert len(response_obj.history) == 1
    assert response_obj.history[0].status == OrderStatus.PLACED
    assert response_obj.history[0].timestamp == valid_ts

    dumped = response_obj.model_dump()
    assert dumped["order_id"] == 42
    assert dumped["current_status"] == "PLACED"
    assert dumped["estimated_arrival_at"] == "2026-10-30T15:05:00Z"
    assert dumped["history"][0]["status"] == "PLACED"

    # Verify OrderResponse includes estimated_arrival_at
    order_resp = OrderResponse(
        id=1,
        restaurant_id=2,
        status=OrderStatus.PLACED,
        total_cents=1500,
        address="123 Main St",
        created_at="2026-10-30T14:00:00Z",
        estimated_arrival_at="2026-10-30T14:35:00Z",
        items=[],
    )
    assert order_resp.status == OrderStatus.PLACED
    assert order_resp.estimated_arrival_at == "2026-10-30T14:35:00Z"

    # Verify OrderResponse estimated_arrival_at defaults to None
    order_resp_default = OrderResponse(
        id=2,
        restaurant_id=2,
        status=OrderStatus.PLACED,
        total_cents=1000,
        address="456 Elm St",
        created_at="2026-10-30T14:00:00Z",
        items=[],
    )
    assert order_resp_default.estimated_arrival_at is None

    # Ensure OrderStatusUpdate.status remains str so unrecognized statuses reach service layer
    update = OrderStatusUpdate(status="UNRECOGNIZED_STATUS")
    assert update.status == "UNRECOGNIZED_STATUS"


def test_init_db_migration_idempotent_and_upgrades_existing_schema(tmp_path):
    """Verify init_db() is idempotent and correctly migrates an existing orders table without estimated_arrival_at."""
    from pathlib import Path
    import sqlite3
    from app.database import init_db, get_db_connection

    test_db_file = str(tmp_path / "legacy.db")

    # 1. Create legacy orders table without estimated_arrival_at column
    legacy_conn = sqlite3.connect(test_db_file)
    legacy_conn.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            restaurant_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            total_cents INTEGER NOT NULL,
            address TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    legacy_conn.commit()
    legacy_conn.close()

    # 2. Run init_db which should detect the missing column and add it
    init_db(test_db_file)

    conn = get_db_connection(test_db_file)
    cur = conn.execute("PRAGMA table_info(orders);")
    columns = {row["name"]: row for row in cur.fetchall()}
    assert "estimated_arrival_at" in columns
    assert columns["estimated_arrival_at"]["type"].upper() == "TEXT"
    conn.close()

    # 3. Run init_db a second time to ensure idempotency (no exception raised on existing column)
    init_db(test_db_file)

