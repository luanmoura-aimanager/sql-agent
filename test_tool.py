import sqlite3
import anthropic
import json

client = anthropic.Anthropic()

# ── SCHEMA DO BANCO ───────────────────────────────────────────────────────
# Injetamos a estrutura do banco no system prompt
# Assim o Claude sabe exatamente quais tabelas e colunas existem
# sem precisar consultar o sqlite_master toda vez
SCHEMA = """
Você é um assistente que responde perguntas sobre um banco de dados de uma loja.

O banco possui as seguintes tabelas:

customers (id, name, city, email)
products (id, name, category, price)
orders (id, customer_id, product_id, quantity, order_date)

Sempre responda em português.
"""

# ── TOOL ─────────────────────────────────────────────────────────────────
tools = [
    {
        "name": "run_sql",
        "description": "Executa uma query SQL no banco de dados e retorna os resultados",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A query SQL a ser executada. Apenas SELECT é permitido."
                }
            },
            "required": ["query"]
        }
    }
]

# ── EXECUÇÃO DO SQL ───────────────────────────────────────────────────────
def run_sql(query):
    # proteção contra queries perigosas
    query_upper = query.strip().upper()
    forbidden = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE"]
    for word in forbidden:
        if word in query_upper:
            return {"error": f"Query proibida: operação {word} não é permitida"}

    try:
        conn = sqlite3.connect("store.db")
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        conn.close()
        return {"columns": columns, "rows": results}
    except Exception as e:
        # devolve o erro pro Claude se autocorrigir
        return {"error": str(e)}

# ── REACT LOOP ────────────────────────────────────────────────────────────
def ask_agent(question):
    print(f"\nPergunta: {question}\n")

    messages = [{"role": "user", "content": question}]

    # loop: continua enquanto Claude precisar usar tools
    while True:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=SCHEMA,
            tools=tools,
            messages=messages
        )

        # Claude terminou — tem a resposta final
        if response.stop_reason == "end_turn":
            print(f"Resposta: {response.content[0].text}")
            break

        # Claude quer usar uma tool
        if response.stop_reason == "tool_use":
            # adiciona a resposta do Claude ao histórico
            messages.append({"role": "assistant", "content": response.content})

            # processa cada tool que o Claude pediu
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"→ SQL gerado: {block.input['query']}")
                    result = run_sql(block.input["query"])
                    print(f"→ Resultado: {result}\n")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result)
                    })

            # devolve os resultados pro Claude e continua o loop
            messages.append({"role": "user", "content": tool_results})

# ── ENTRADA DO USUÁRIO ────────────────────────────────────────────────────
while True:
    question = input("Pergunta (ou 'sair' para terminar): ")
    if question.lower() == "sair":
        break
    ask_agent(question)
