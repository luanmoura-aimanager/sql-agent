import os
import sys
import asyncio
from typing import TypedDict, Annotated
from operator import add
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph, END
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

model = ChatAnthropic(model="claude-haiku-4-5-20251001")

DB_PATH = os.environ.get("SQL_AGENT_DB_PATH", "store.db")

ROUTER_PROMPT = """You are a routing assistant for a store database application that has
a SQLite database with `customers`, `products`, and `orders` tables.

Your only job: decide if the user's message is in scope of this database
system, regardless of whether the system can fulfill it. The downstream
sql_agent has a SELECT-only guard and will refuse destructive operations,
report empty results for nonexistent data, and inspect the schema for
metadata questions. Don't try to anticipate any of that.

Answer YES if the message:
- Asks about data that could plausibly live in customers/products/orders
  (counts, lists, aggregations, comparisons, even with absurd filters
  like 'on Mars' or 'in 1850')
- Mentions the schema (tables, columns, data types)
- Issues a command on the database (DROP, DELETE, TRUNCATE, UPDATE,
  INSERT, ALTER) — even if the command is destructive
- References any field or column, including ones that may not exist
  ('credit score', 'birthdate'), since checking the schema is what
  the sql_agent does

Answer NO if the message is unrelated to the database system:
- General knowledge questions (what is SQL, how does X work)
- Greetings, small talk
- Topics not connected to the store's data model

Answer with exactly one word: YES or NO."""


SQL_AGENT_PROMPT = """You are an assistant that answers questions about a store database.

You have two tools available:
- get_schema: discovers which tables and columns exist in the database
- run_query: executes a SELECT query on the database

When you need data, first discover the schema (if you don't know it yet),
then write the query.

Always answer in English."""


def call_mcp_tool(tool_name: str, arguments: dict) -> str:
    """Calls a tool on the local MCP server and returns the result as a string."""
    async def _call():
        env = os.environ.copy()
        env["SQL_AGENT_DB_PATH"] = DB_PATH
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["mcp/sqlite-mcp-server.py"],
            env=env,
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return result.content[0].text

    return asyncio.run(_call())


@tool
def get_schema() -> str:
    """Descobre o schema do banco: lista de tabelas e suas colunas."""
    return call_mcp_tool("get_schema", {})


@tool
def run_query(sql: str) -> str:
    """Executa uma query SELECT no banco e retorna os resultados.
    Apenas SELECT é permitido."""
    return call_mcp_tool("run_query", {"sql": sql})

class State(TypedDict):
    messages: Annotated[list, add]
    needs_sql: str


sql_react_agent = create_react_agent(model, [get_schema, run_query], prompt=SQL_AGENT_PROMPT)


# função router — usar ROUTER_PROMPT em vez do system inline
def router(state: State) -> State:
    last_message = state["messages"][-1].content
    messages = [
        SystemMessage(content=ROUTER_PROMPT),
        HumanMessage(content=last_message),
    ]
    result = model.invoke(messages)
    decision = result.content.strip().upper()
    needs_sql = "YES" if "YES" in decision else "NO"
    return {"needs_sql": needs_sql}


def sql_agent(state: State) -> State:
    result = sql_react_agent.invoke({"messages": state["messages"]})
    answer = result["messages"][-1].content
    return {"messages": [AIMessage(content=answer)]}


def direct(state: State) -> State:
    messages = [SystemMessage(content="You are a helpful assistant. Answer in English.")] + state["messages"]
    result = model.invoke(messages)
    return {"messages": [AIMessage(content=result.content)]}


def route_decision(state: State) -> str:
    return state["needs_sql"]


builder = StateGraph(State)
builder.add_node("router", router)
builder.add_node("sql_agent", sql_agent)
builder.add_node("direct", direct)
builder.set_entry_point("router")
builder.add_conditional_edges("router", route_decision, {"YES": "sql_agent", "NO": "direct"})
builder.add_edge("sql_agent", END)
builder.add_edge("direct", END)

graph = builder.compile()


def run_agent(question: str, chat_history: list) -> str:
    """Run the agent for a single turn.

    chat_history: list of {"role": "user"/"assistant", "content": str} dicts
    representing previous turns. Returns the agent's answer as a plain string.
    """
    messages = []
    for msg in chat_history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=question))

    result = graph.invoke({"messages": messages})
    return result["messages"][-1].content
