import sqlite3
from typing import List, Optional


class RestaurantRepository:
    """Repository handling database operations for restaurants and menu items."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_all(self) -> List[dict]:
        """Fetch all restaurants sorted by ID."""
        cursor = self.conn.execute(
            """
            SELECT id, name, cuisine, opens_at, closes_at, avg_prep_minutes
            FROM restaurants
            ORDER BY id ASC
            """
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_by_id(self, restaurant_id: int) -> Optional[dict]:
        """Fetch a single restaurant by ID."""
        cursor = self.conn.execute(
            """
            SELECT id, name, cuisine, opens_at, closes_at, avg_prep_minutes
            FROM restaurants
            WHERE id = ?
            """,
            (restaurant_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_menu(self, restaurant_id: int) -> List[dict]:
        """Fetch all menu items belonging to a given restaurant."""
        cursor = self.conn.execute(
            """
            SELECT id, restaurant_id, name, price_cents
            FROM menu_items
            WHERE restaurant_id = ?
            ORDER BY id ASC
            """,
            (restaurant_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_menu_items_by_ids(self, item_ids: List[int]) -> List[dict]:
        """Fetch multiple menu items by their IDs."""
        if not item_ids:
            return []
        placeholders = ",".join("?" for _ in item_ids)
        cursor = self.conn.execute(
            f"""
            SELECT id, restaurant_id, name, price_cents
            FROM menu_items
            WHERE id IN ({placeholders})
            """,
            item_ids,
        )
        return [dict(row) for row in cursor.fetchall()]
