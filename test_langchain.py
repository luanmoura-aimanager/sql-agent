from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
import sqlite3
import json

# ── MODEL ─────────────────────────────────────────────────────────────────
# Before: client = anthropic.Anthropic()
# Now: LangChain manages the client for you
model = ChatAnthropic(model="claude-opus-4-6")

# ── TOOL ──────────────────────────────────────────────────────────────────
# Before: you defined a large dict with name, description, input_schema
# Now: a simple @tool decorator handles all of that automatically
@tool
def run_sql(query: str) -> str:
    """Executes a SQL query against the store database and returns the results.
    Only SELECT queries are allowed."""

    query_upper = query.strip().upper()
    forbidden = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE"]
    for word in forbidden:
        if word in query_upper:
            return f"Forbidden query: operation {word} is not allowed"

    try:
        conn = sqlite3.connect("store.db")
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        conn.close()
        return json.dumps({"columns": columns, "rows": results})
    except Exception as e:
        return f"Error: {str(e)}"

# ── PROMPT ────────────────────────────────────────────────────────────────
prompt = """You are an assistant that answers questions about a store database.

The database has the following tables:

customers (id, name, city, email)
products (id, name, category, price)
orders (id, customer_id, product_id, quantity, order_date)

Always answer in English."""

# ── AGENT ─────────────────────────────────────────────────────────────────
tools = [run_sql]
agent = create_react_agent(model, tools, prompt=prompt)

# ── QUESTION LOOP ─────────────────────────────────────────────────────────
# chat_history accumulates all messages in the conversation
chat_history = []

while True:
    question = input("\nQuestion (or 'exit' to quit): ")
    if question.lower() == "exit":
        break

    # pass the full history along with the new question
    result = agent.invoke({
        "messages": chat_history + [("human", question)]
    })

    answer = result["messages"][-1].content
    print(f"\nAnswer: {answer}")

    # accumulate in history for the next question
    chat_history.append(("human", question))
    chat_history.append(("assistant", answer))
