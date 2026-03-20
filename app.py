import sqlite3
import json
import streamlit as st
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

# ── MODELO ────────────────────────────────────────────────────────────────
model = ChatAnthropic(model="claude-opus-4-6")

# ── PROMPT ────────────────────────────────────────────────────────────────
SCHEMA = """Você é um assistente que responde perguntas sobre um banco de dados de uma loja.

O banco possui as seguintes tabelas:

customers (id, name, city, email)
products (id, name, category, price)
orders (id, customer_id, product_id, quantity, order_date)

Sempre responda em português."""

# ── TOOL ──────────────────────────────────────────────────────────────────
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

# ── AGENTE ────────────────────────────────────────────────────────────────
tools = [run_sql]
agent = create_react_agent(model, tools, prompt=SCHEMA)

# ── UI ────────────────────────────────────────────────────────────────────
st.title("🗄️ SQL Agent")
st.caption("Faça perguntas sobre o banco de dados em linguagem natural")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "display_history" not in st.session_state:
    st.session_state.display_history = []

for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.write(message["content"])

question = st.chat_input("Faça uma pergunta sobre os dados...")

if question:
    st.session_state.display_history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Consultando o banco..."):
            result = agent.invoke({
                "messages": st.session_state.chat_history + [("human", question)]
            })
            answer = result["messages"][-1].content
        st.write(answer)

    st.session_state.display_history.append({"role": "assistant", "content": answer})
    st.session_state.chat_history.append(("human", question))
    st.session_state.chat_history.append(("assistant", answer))
