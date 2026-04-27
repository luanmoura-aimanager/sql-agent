from mcp.server.fastmcp import FastMCP
import sqlite3
import os

mcp = FastMCP("sqlite-mcp-server")

DB_PATH = os.environ.get("SQL_AGENT_DB_PATH")
if not DB_PATH:
    raise RuntimeError("Defina SQL_AGENT_DB_PATH")

@mcp.tool()
def get_schema() -> str:
    """
    Retorna o schema do banco: lista de tabelas e suas colunas.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    schema_str = ""
    for table in tables:
        schema_str += f"Table: {table}\n"
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        for col in columns:
            schema_str += f"  - {col[1]} ({col[2]})\n"
        schema_str += "\n"

    conn.close()
    return schema_str


@mcp.tool()
def run_query(sql: str) -> str:
    """
    Executa uma query SELECT no banco e retorna os resultados.
    Apenas SELECT é permitido — qualquer outra operação é rejeitada.
    """
    # 1. Guard: rejeita qualquer coisa que não seja SELECT
    if not sql.strip().upper().startswith("SELECT"):
        return "Error: Only SELECT queries are allowed."

    # 2. Conecta, executa, fetchall, fecha
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(sql)

    columns = [description[0] for description in cursor.description]
    rows = cursor.fetchall()
    conn.close()

    # 3. Formata os resultados em string legível
    if not rows:
        return f"Columns: {', '.join(columns)}\n(no rows returned)"

    total = len(rows)
    truncated = rows[:100]

    output = f"Columns: {', '.join(columns)}\nRows:\n"
    for row in truncated:
        output += " | ".join(str(value) for value in row) + "\n"

    if total > 100:
        output += f"\n(showing first 100 of {total} rows)"
    else:
        output += f"\n({total} rows)"

    return output


if __name__ == "__main__":
    mcp.run(transport="stdio")
