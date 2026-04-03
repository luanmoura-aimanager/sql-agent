import sqlite3

# SQLite stores the entire database in a single file on disk.
# `sqlite3.connect` creates the file if it doesn't exist yet, or opens it if it does.
conn = sqlite3.connect("store.db")
cursor = conn.cursor()  # a cursor is the handle through which we send SQL commands

# ── TABLE DEFINITIONS ─────────────────────────────────────────────────────
# `CREATE TABLE IF NOT EXISTS` is idempotent — safe to run multiple times
# without raising an error or duplicating the table.

# Customers: the people who place orders in the store.
cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id    INTEGER PRIMARY KEY,  -- unique identifier, auto-indexed by SQLite
        name  TEXT,
        city  TEXT,
        email TEXT
    )
""")

# Products: items available for purchase, with a category and price.
cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id       INTEGER PRIMARY KEY,
        name     TEXT,
        category TEXT,
        price    REAL  -- REAL maps to a 64-bit floating-point number in SQLite
    )
""")

# Orders: the join between customers and products.
# FOREIGN KEY constraints document the relationship even though SQLite doesn't
# enforce them by default (you'd need PRAGMA foreign_keys = ON for enforcement).
cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id          INTEGER PRIMARY KEY,
        customer_id INTEGER,
        product_id  INTEGER,
        quantity    INTEGER,
        order_date  TEXT,  -- stored as ISO-8601 string (YYYY-MM-DD) for easy sorting
        FOREIGN KEY (customer_id) REFERENCES customers(id),
        FOREIGN KEY (product_id)  REFERENCES products(id)
    )
""")

# ── SEED DATA ─────────────────────────────────────────────────────────────
# `executemany` runs the same parameterised statement for each tuple in the list,
# which is faster and safer than building SQL strings with f-strings.

# Five customers spread across Brazilian cities.
cursor.executemany("INSERT INTO customers VALUES (?, ?, ?, ?)", [
    (1, "Ana Silva",     "São Paulo",     "ana@email.com"),
    (2, "Carlos Lima",   "Fortaleza",     "carlos@email.com"),
    (3, "Mariana Souza", "Rio de Janeiro","mariana@email.com"),
    (4, "Pedro Costa",   "Fortaleza",     "pedro@email.com"),
    (5, "Julia Mendes",  "São Paulo",     "julia@email.com"),
])

# Five electronics and furniture products with realistic Brazilian prices (BRL).
cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", [
    (1, "Notebook", "Eletrônicos", 3500.00),
    (2, "Mouse",    "Eletrônicos",   80.00),
    (3, "Cadeira",  "Móveis",       900.00),
    (4, "Monitor",  "Eletrônicos", 1200.00),
    (5, "Teclado",  "Eletrônicos",  150.00),
])

# Eight orders spanning Q1 2024 — enough variety for interesting SQL queries
# like "top products by revenue" or "orders per city".
cursor.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", [
    (1, 1, 1, 1, "2024-01-15"),  # Ana buys a Notebook
    (2, 1, 2, 2, "2024-01-20"),  # Ana buys 2 Mice
    (3, 2, 3, 1, "2024-02-10"),  # Carlos buys a Cadeira
    (4, 3, 4, 1, "2024-02-14"),  # Mariana buys a Monitor
    (5, 4, 5, 3, "2024-03-01"),  # Pedro buys 3 Teclados
    (6, 5, 1, 1, "2024-03-05"),  # Julia buys a Notebook
    (7, 2, 2, 1, "2024-03-10"),  # Carlos buys a Mouse
    (8, 1, 4, 2, "2024-03-15"),  # Ana buys 2 Monitors
])

# `commit` flushes the transaction to disk — without this, changes are lost.
conn.commit()
conn.close()
print("Banco criado com sucesso!")
