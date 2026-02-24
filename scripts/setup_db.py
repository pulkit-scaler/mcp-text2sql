"""
Create the sample SQLite database used by the Text2SQL MCP demo.

Run once:  uv run python scripts/setup_db.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "sample.db"


def setup() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Remove old DB so the script is idempotent
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # ── employees (from the Colab demo) ──────────────────────────
    cur.execute("""
        CREATE TABLE employees (
            id        INTEGER PRIMARY KEY,
            name      TEXT    NOT NULL,
            department TEXT   NOT NULL,
            salary    REAL   NOT NULL,
            city      TEXT   NOT NULL
        );
    """)
    cur.executemany(
        "INSERT INTO employees (id, name, department, salary, city) VALUES (?, ?, ?, ?, ?)",
        [
            (1, "Alice",  "Engineering", 95000,  "Berlin"),
            (2, "Bob",    "Engineering", 88000,  "Berlin"),
            (3, "Carol",  "Marketing",  72000,  "Prague"),
            (4, "David",  "Marketing",  68000,  "Prague"),
            (5, "Eve",    "Engineering", 102000, "London"),
            (6, "Frank",  "Sales",      61000,  "London"),
            (7, "Grace",  "Sales",      59000,  "Berlin"),
            (8, "Heidi",  "Engineering", 97000,  "Prague"),
        ],
    )

    # ── customers (supports the Colab's "How many customers pay in EUR?" demo) ──
    cur.execute("""
        CREATE TABLE customers (
            id        INTEGER PRIMARY KEY,
            name      TEXT    NOT NULL,
            country   TEXT    NOT NULL,
            currency  TEXT    NOT NULL,
            balance   REAL   NOT NULL
        );
    """)
    cur.executemany(
        "INSERT INTO customers (id, name, country, currency, balance) VALUES (?, ?, ?, ?, ?)",
        [
            (1,  "Acme GmbH",        "Germany",       "EUR", 15400.50),
            (2,  "Prague Widgets",    "Czech Republic", "CZK", 342000.00),
            (3,  "Berlin Tech",       "Germany",       "EUR", 88200.00),
            (4,  "London Analytics",  "UK",            "GBP", 45000.00),
            (5,  "CZ Solutions",      "Czech Republic", "CZK", 198000.00),
            (6,  "Euro Supplies",     "France",        "EUR", 23100.75),
            (7,  "Nordic Data",       "Sweden",        "SEK", 67000.00),
            (8,  "Praha Services",    "Czech Republic", "CZK", 410000.00),
            (9,  "Milan Corp",        "Italy",         "EUR", 54200.00),
            (10, "Swiss Holdings",    "Switzerland",   "CHF", 120000.00),
        ],
    )

    # ── orders (for multi-table JOIN queries) ────────────────────
    cur.execute("""
        CREATE TABLE orders (
            id           INTEGER PRIMARY KEY,
            customer_id  INTEGER NOT NULL,
            product      TEXT    NOT NULL,
            amount       REAL   NOT NULL,
            order_date   TEXT    NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );
    """)
    cur.executemany(
        "INSERT INTO orders (id, customer_id, product, amount, order_date) VALUES (?, ?, ?, ?, ?)",
        [
            (1, 1,  "Widget A",   2500.00, "2024-11-15"),
            (2, 1,  "Widget B",   1800.00, "2025-01-10"),
            (3, 2,  "Gadget X",   5400.00, "2025-02-01"),
            (4, 3,  "Widget A",   3200.00, "2025-01-20"),
            (5, 4,  "Service Pro", 9000.00, "2025-03-05"),
            (6, 5,  "Gadget X",   2700.00, "2024-12-22"),
            (7, 6,  "Widget B",   1100.00, "2025-02-14"),
            (8, 9,  "Service Pro", 6500.00, "2025-01-30"),
            (9, 3,  "Gadget Y",   4100.00, "2025-03-12"),
            (10, 7, "Widget A",   1900.00, "2025-02-28"),
        ],
    )

    conn.commit()
    conn.close()

    print(f"✅ Database created at {DB_PATH}")
    print(f"   Tables: employees, customers, orders")
    print(f"   Rows:   8 employees, 10 customers, 10 orders")


if __name__ == "__main__":
    setup()
