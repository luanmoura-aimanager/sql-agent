import sqlite3
import anthropic
import json
import streamlit as st

client = anthropic.Anthropic()

# ── SCHEMA ────────────────────────────────────────────────────────────────
SCHEMA = """
Você é um assistente que responde perguntas sobre um banco de dados de uma loja.

O banco possui as seguintes tabelas:

customers (id, name, city, email)
products (id, name, category, price)
orders (id, customer_id, product_id, quantity, order_date)

Sempre responda em português.
"""

# ── TOOL ──────────────────────────────────────────────────────────────────
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
        return {"error": str(e)}

# ── REACT LOOP ────────────────────────────────────────────────────────────
def ask_agent(messages):
    while True:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=SCHEMA,
            tools=tools,
            messages=messages
        )

        if response.stop_reason == "end_turn":
            return response.content[0].text

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = run_sql(block.input["query"])
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result)
                    })

            messages.append({"role": "user", "content": tool_results})

# ── UI ────────────────────────────────────────────────────────────────────
st.title("🗄️ SQL Agent")
st.caption("Faça perguntas sobre o banco de dados em linguagem natural")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "history" not in st.session_state:
    st.session_state.history = []

for message in st.session_state.history:
    with st.chat_message(message["role"]):
        st.write(message["content"])

question = st.chat_input("Faça uma pergunta sobre os dados...")

if question:
    st.session_state.history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    st.session_state.messages.append({"role": "user", "content": question})

    with st.chat_message("assistant"):
        with st.spinner("Consultando o banco..."):
            answer = ask_agent(st.session_state.messages)
        st.write(answer)

    st.session_state.history.append({"role": "assistant", "content": answer})
    st.session_state.messages.append({"role": "assistant", "content": answer})
