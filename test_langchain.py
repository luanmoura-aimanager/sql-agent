from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
import sqlite3
import json

# ── MODELO ────────────────────────────────────────────────────────────────
# Antes: client = anthropic.Anthropic()
# Agora: LangChain gerencia o cliente por você
model = ChatAnthropic(model="claude-opus-4-6")

# ── TOOL ──────────────────────────────────────────────────────────────────
# Antes: você definia um dicionário grande com name, description, input_schema
# Agora: um simples decorador @tool faz tudo isso automaticamente
@tool
def run_sql(query: str) -> str:
    """Executa uma query SQL no banco de dados da loja e retorna os resultados.
    Apenas queries SELECT são permitidas."""

    query_upper = query.strip().upper()
    forbidden = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE"]
    for word in forbidden:
        if word in query_upper:
            return f"Query proibida: operação {word} não é permitida"

    try:
        conn = sqlite3.connect("store.db")
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        conn.close()
        return json.dumps({"columns": columns, "rows": results})
    except Exception as e:
        return f"Erro: {str(e)}"

# ── PROMPT ────────────────────────────────────────────────────────────────
prompt = """Você é um assistente que responde perguntas sobre um banco de dados de uma loja.

O banco possui as seguintes tabelas:

customers (id, name, city, email)
products (id, name, category, price)
orders (id, customer_id, product_id, quantity, order_date)

Sempre responda em português."""

# ── AGENTE ────────────────────────────────────────────────────────────────
tools = [run_sql]
agent = create_react_agent(model, tools, prompt=prompt)

# ── LOOP DE PERGUNTAS ─────────────────────────────────────────────────────
while True:
    question = input("\nPergunta (ou 'sair' para terminar): ")
    if question.lower() == "sair":
        break

    result = agent.invoke({
        "messages": [("human", question)]
    })

    print(f"\nResposta: {result['messages'][-1].content}")
