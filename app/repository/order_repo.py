import sqlite3
from typing import List, Optional


class OrderRepository:
    """Repository handling database operations for orders and order items."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def record_status_history(self, order_id: int, status: str, timestamp: str) -> None:
        """Insert a status transition record into order_status_history."""
        self._record_status_history(order_id, status, timestamp)

    def _record_status_history(self, order_id: int, status: str, timestamp: str) -> None:
        self.conn.execute(
            """
            INSERT INTO order_status_history (order_id, status, timestamp)
            VALUES (?, ?, ?)
            """,
            (order_id, status, timestamp),
        )

    def create_order(
        self,
        restaurant_id: int,
        status: str,
        total_cents: int,
        address: str,
        created_at: str,
        items: List[dict],
        estimated_arrival_at: Optional[str] = None,
    ) -> dict:
        """Create an order and its associated order_items atomically in a transaction."""
        with self.conn:
            cursor = self.conn.execute(
                """
                INSERT INTO orders (restaurant_id, status, total_cents, address, created_at, estimated_arrival_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (restaurant_id, status, total_cents, address, created_at, estimated_arrival_at),
            )
            order_id = cursor.lastrowid
            for item in items:
                self.conn.execute(
                    """
                    INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price_cents)
                    VALUES (?, ?, ?, ?)
                    """,
                    (order_id, item["menu_item_id"], item["quantity"], item["unit_price_cents"]),
                )
            self.record_status_history(order_id, status, created_at)

        created = self.get_by_id(order_id)
        if not created:
            raise RuntimeError(f"Failed to retrieve created order with id {order_id}")
        return created

    def get_by_id(self, order_id: int) -> Optional[dict]:
        """Fetch an order with all of its order_items and item names."""
        cursor = self.conn.execute(
            """
            SELECT id, restaurant_id, status, total_cents, address, created_at, estimated_arrival_at
            FROM orders
            WHERE id = ?
            """,
            (order_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        order_data = dict(row)
        items_cursor = self.conn.execute(
            """
            SELECT oi.id, oi.order_id, oi.menu_item_id, m.name, oi.quantity, oi.unit_price_cents
            FROM order_items oi
            JOIN menu_items m ON oi.menu_item_id = m.id
            WHERE oi.order_id = ?
            ORDER BY oi.id ASC
            """,
            (order_id,),
        )
        order_data["items"] = [dict(item_row) for item_row in items_cursor.fetchall()]
        return order_data

    def update_status(self, order_id: int, status: str) -> Optional[dict]:
        """Update an order's status and return the updated order."""
        with self.conn:
            cursor = self.conn.execute(
                """
                UPDATE orders
                SET status = ?
                WHERE id = ?
                """,
                (status, order_id),
            )
            if cursor.rowcount == 0:
                return None

        return self.get_by_id(order_id)

    def update_status_and_eta(
        self,
        order_id: int,
        status: str,
        estimated_arrival_at: Optional[str],
        timestamp: str,
    ) -> Optional[dict]:
        """Atomically update an order's status and ETA, and record to history."""
        with self.conn:
            cursor = self.conn.execute(
                """
                UPDATE orders
                SET status = ?, estimated_arrival_at = ?
                WHERE id = ?
                """,
                (status, estimated_arrival_at, order_id),
            )
            if cursor.rowcount == 0:
                return None

            self.record_status_history(order_id, status, timestamp)

        return self.get_by_id(order_id)

    def get_tracking(self, order_id: int) -> Optional[dict]:
        """Fetch tracking snapshot for an order including current status, ETA, and history."""
        cursor = self.conn.execute(
            """
            SELECT status, estimated_arrival_at
            FROM orders
            WHERE id = ?
            """,
            (order_id,),
        )
        order_row = cursor.fetchone()
        if not order_row:
            return None

        history_cursor = self.conn.execute(
            """
            SELECT status, timestamp
            FROM order_status_history
            WHERE order_id = ?
            ORDER BY id ASC
            """,
            (order_id,),
        )
        history = [
            {"status": row["status"], "timestamp": row["timestamp"]}
            for row in history_cursor.fetchall()
        ]

        return {
            "order_id": order_id,
            "current_status": order_row["status"],
            "estimated_arrival_at": order_row["estimated_arrival_at"],
            "history": history,
        }
