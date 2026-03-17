import sqlite3

# cria (ou abre) o arquivo do banco
conn = sqlite3.connect("store.db")
cursor = conn.cursor()

# cria tabela de clientes
cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY,
        name TEXT,
        city TEXT,
        email TEXT
    )
""")

# cria tabela de produtos
cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT,
        category TEXT,
        price REAL
    )
""")

# cria tabela de pedidos
cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY,
        customer_id INTEGER,
        product_id INTEGER,
        quantity INTEGER,
        order_date TEXT,
        FOREIGN KEY (customer_id) REFERENCES customers(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    )
""")

# insere clientes
cursor.executemany("INSERT INTO customers VALUES (?, ?, ?, ?)", [
    (1, "Ana Silva",    "São Paulo",    "ana@email.com"),
    (2, "Carlos Lima",  "Fortaleza",    "carlos@email.com"),
    (3, "Mariana Souza","Rio de Janeiro","mariana@email.com"),
    (4, "Pedro Costa",  "Fortaleza",    "pedro@email.com"),
    (5, "Julia Mendes", "São Paulo",    "julia@email.com"),
])

# insere produtos
cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", [
    (1, "Notebook",   "Eletrônicos", 3500.00),
    (2, "Mouse",      "Eletrônicos",   80.00),
    (3, "Cadeira",    "Móveis",       900.00),
    (4, "Monitor",    "Eletrônicos", 1200.00),
    (5, "Teclado",    "Eletrônicos",  150.00),
])

# insere pedidos
cursor.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", [
    (1, 1, 1, 1, "2024-01-15"),
    (2, 1, 2, 2, "2024-01-20"),
    (3, 2, 3, 1, "2024-02-10"),
    (4, 3, 4, 1, "2024-02-14"),
    (5, 4, 5, 3, "2024-03-01"),
    (6, 5, 1, 1, "2024-03-05"),
    (7, 2, 2, 1, "2024-03-10"),
    (8, 1, 4, 2, "2024-03-15"),
])

conn.commit()
conn.close()
print("Banco criado com sucesso!")
