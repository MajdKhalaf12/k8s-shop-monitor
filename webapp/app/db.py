import os
import sqlite3
from pathlib import Path

DB_PATH = os.environ.get("DB_PATH", "/app/data/shop.db")

PRODUCTS = [
    (1, "Espresso Beans", 12.99, "Single-origin dark roast beans"),
    (2, "Ceramic Mug", 8.50, "Hand-glazed 350ml mug"),
    (3, "Pour Over Kit", 34.00, "Glass carafe with filter set"),
    (4, "Cold Brew Bottle", 18.75, "1L insulated brew bottle"),
]

USERS = [
    ("admin", "secret123"),
    ("barista", "brew2024"),
]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                description TEXT
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            );
            """
        )
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO products (id, name, price, description) VALUES (?, ?, ?, ?)",
                PRODUCTS,
            )
            conn.executemany(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                USERS,
            )
            conn.commit()
    finally:
        conn.close()
