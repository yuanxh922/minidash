import sqlite3
from typing import Generator, Optional
from app.config import DATABASE_PATH

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS restaurants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cuisine TEXT NOT NULL,
    opens_at TEXT NOT NULL,
    closes_at TEXT NOT NULL,
    avg_prep_minutes INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS menu_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurant_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    price_cents INTEGER NOT NULL,
    FOREIGN KEY (restaurant_id) REFERENCES restaurants (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurant_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    total_cents INTEGER NOT NULL,
    address TEXT NOT NULL,
    created_at TEXT NOT NULL,
    estimated_arrival_at TEXT,
    FOREIGN KEY (restaurant_id) REFERENCES restaurants (id)
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    menu_item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price_cents INTEGER NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
    FOREIGN KEY (menu_item_id) REFERENCES menu_items (id)
);

CREATE TABLE IF NOT EXISTS order_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_order_status_history_order_id ON order_status_history (order_id);
"""

INITIAL_RESTAURANTS_SEED = [
    {
        "name": "Burger Haven",
        "cuisine": "American",
        "opens_at": "10:00",
        "closes_at": "22:00",
        "avg_prep_minutes": 20,
        "menu": [
            {"name": "Classic Smashburger", "price_cents": 1099},
            {"name": "Double Bacon Burger", "price_cents": 1499},
            {"name": "Seasoned Fries", "price_cents": 499},
            {"name": "Vanilla Shake", "price_cents": 599},
        ],
    },
    {
        "name": "Pasta Paradiso",
        "cuisine": "Italian",
        "opens_at": "11:00",
        "closes_at": "22:30",
        "avg_prep_minutes": 25,
        "menu": [
            {"name": "Margherita Pizza", "price_cents": 1550},
            {"name": "Rigatoni Bolognese", "price_cents": 1850},
            {"name": "Garlic Bread", "price_cents": 550},
            {"name": "Tiramisu", "price_cents": 800},
        ],
    },
    {
        "name": "Tokyo Ramen Bar",
        "cuisine": "Japanese",
        "opens_at": "11:30",
        "closes_at": "23:00",
        "avg_prep_minutes": 15,
        "menu": [
            {"name": "Tonkotsu Ramen", "price_cents": 1650},
            {"name": "Spicy Miso Ramen", "price_cents": 1700},
            {"name": "Pan-Fried Gyoza", "price_cents": 750},
            {"name": "Japanese Green Tea", "price_cents": 350},
        ],
    },
    {
        "name": "Taco Fiesta",
        "cuisine": "Mexican",
        "opens_at": "09:30",
        "closes_at": "21:30",
        "avg_prep_minutes": 15,
        "menu": [
            {"name": "Birria Tacos (3 pcs)", "price_cents": 1399},
            {"name": "California Burrito", "price_cents": 1299},
            {"name": "Chips & Fresh Guacamole", "price_cents": 649},
            {"name": "Horchata", "price_cents": 450},
        ],
    },
    {
        "name": "Spice of India",
        "cuisine": "Indian",
        "opens_at": "12:00",
        "closes_at": "22:00",
        "avg_prep_minutes": 30,
        "menu": [
            {"name": "Chicken Tikka Masala", "price_cents": 1699},
            {"name": "Garlic Naan", "price_cents": 399},
            {"name": "Vegetable Biryani", "price_cents": 1450},
            {"name": "Mango Lassi", "price_cents": 499},
        ],
    },
]


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Create a new SQLite connection configured with Row factory and foreign keys."""
    target_path = db_path or DATABASE_PATH
    conn = sqlite3.connect(target_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize database tables."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.executescript(CREATE_TABLES_SQL)
            # Idempotent column migration: ensure estimated_arrival_at exists on orders
            cursor = conn.execute("PRAGMA table_info(orders);")
            columns = [row["name"] for row in cursor.fetchall()]
            if "estimated_arrival_at" not in columns:
                conn.execute("ALTER TABLE orders ADD COLUMN estimated_arrival_at TEXT;")
    finally:
        conn.close()


def seed_db(db_path: Optional[str] = None) -> None:
    """Seed initial restaurants and menu items if restaurants table is empty."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            count = conn.execute("SELECT COUNT(*) AS cnt FROM restaurants").fetchone()["cnt"]
            if count == 0:
                for r in INITIAL_RESTAURANTS_SEED:
                    cur = conn.execute(
                        """
                        INSERT INTO restaurants (name, cuisine, opens_at, closes_at, avg_prep_minutes)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (r["name"], r["cuisine"], r["opens_at"], r["closes_at"], r["avg_prep_minutes"]),
                    )
                    restaurant_id = cur.lastrowid
                    for item in r["menu"]:
                        conn.execute(
                            """
                            INSERT INTO menu_items (restaurant_id, name, price_cents)
                            VALUES (?, ?, ?)
                            """,
                            (restaurant_id, item["name"], item["price_cents"]),
                        )
    finally:
        conn.close()


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency that provides a database connection per request."""
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()
