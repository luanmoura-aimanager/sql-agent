import os
import streamlit as st
from typing import TypedDict, Annotated
from operator import add  # used by LangGraph to merge list fields across state updates
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.prebuilt import create_react_agent  # high-level helper that builds a ReAct loop
from langgraph.graph import StateGraph, END         # primitives to define and terminate the graph
from langgraph.checkpoint.memory import MemorySaver  # in-memory store for conversation checkpoints
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ── MODELO ────────────────────────────────────────────────────────────────
# Haiku is the fastest / cheapest Claude model — good for routing decisions
# and SQL queries where latency matters more than creative depth.
model = ChatAnthropic(model="claude-haiku-4-5-20251001")

DB_PATH = os.environ.get("SQL_AGENT_DB_PATH", "store.db")  # default pra local

# ── SCHEMA ────────────────────────────────────────────────────────────────
# This is the system prompt for the SQL sub-agent.
# Instead of hardcoding the schema, we describe the available MCP tools and
# let the agent discover the schema dynamically by calling get_schema.
SCHEMA = """Você é um assistente que responde perguntas sobre um banco de dados de uma loja.

Você tem duas ferramentas disponíveis:
- get_schema: descobre quais tabelas e colunas existem no banco
- run_query: executa uma query SELECT no banco

Sempre que precisar dos dados, primeiro descubra o schema (se ainda não souber), depois escreva a query.

Sempre responda em português."""

def call_mcp_tool(tool_name: str, arguments: dict) -> str:
    """Chama uma tool no servidor MCP local e retorna o resultado como string."""
    
    async def _call():
        # 1. Define como subir o servidor
        server_params = StdioServerParameters(
            command="python",
            args=["mcp/sqlite-mcp-server.py"],
            env={"SQL_AGENT_DB_PATH": DB_PATH}
        )
        
        # 2. Abre o cliente, sessão, chama a tool, fecha
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return result.content[0].text
    
    return asyncio.run(_call())

# ── TOOL ──────────────────────────────────────────────────────────────────
# @tool turns a plain Python function into a LangChain tool that the agent
# can call by name. The docstring becomes the tool description the LLM sees.
@tool
def get_schema() -> str:
    """Descobre o schema do banco: lista de tabelas e suas colunas."""
    return call_mcp_tool("get_schema", {})

@tool
def run_query(sql: str) -> str:
    """Executa uma query SELECT no banco e retorna os resultados.
    Apenas SELECT é permitido."""
    return call_mcp_tool("run_query", {"sql": sql})

# ── SQL AGENT (create_react_agent) ────────────────────────────────────────
# create_react_agent builds a ReAct (Reason + Act) loop automatically.
# The loop: think → call tool → observe result → think again → answer.
# We pass `prompt=SCHEMA` so the SQL context is always in the system prompt.
sql_react_agent = create_react_agent(model, [get_schema, run_query], prompt=SCHEMA)

# ── STATE ─────────────────────────────────────────────────────────────────
# LangGraph passes a single typed dict (State) between all graph nodes.
# `Annotated[list, add]` tells LangGraph to *append* new messages rather
# than replace the whole list — this is how conversation history accumulates.
class State(TypedDict):
    messages: Annotated[list, add]  # full conversation history, grows over turns
    needs_sql: str                  # routing decision: "YES" or "NO"

# ── NÓS ───────────────────────────────────────────────────────────────────
# Each node is a plain function that receives the current State and returns
# a partial State dict. LangGraph merges the partial dict into the current
# state before passing it to the next node.

def router(state: State) -> State:
    """Classify whether the user question needs a SQL query or can be answered
    directly. This keeps the expensive sql_react_agent idle for simple chitchat."""
    last_message = state["messages"][-1].content
    # Ask the model to answer with exactly YES or NO — cheap single-turn call.
    messages = [
        SystemMessage(content="""You are a routing assistant for a store database application.
            The application has access to a SQLite database with customers, products, and orders tables.
            Your job is to decide if the user's question should be answered by querying this database.

            Answer YES if the question asks about: customers, products, orders, sales, cities, prices, quantities, or any store data.
            Answer NO if the question is general knowledge, greetings, or unrelated to the store.

            Answer with exactly one word: YES or NO."""),
        HumanMessage(content=last_message)
    ]
    result = model.invoke(messages)
    # Normalise to "YES" / "NO" regardless of extra whitespace or mixed case.
    decision = result.content.strip().upper()
    needs_sql = "YES" if "YES" in decision else "NO"
    return {"needs_sql": needs_sql}

def sql_agent(state: State) -> State:
    """Invoke the ReAct SQL sub-agent with the full message history and return
    its final answer as a new AIMessage appended to the state.
    The agent utilizes an MCP tool to access the database, so it doesn't need direct DB access here."""
    result = sql_react_agent.invoke({"messages": state["messages"]})
    # The last message in result["messages"] is the agent's final text reply.
    answer = result["messages"][-1].content
    return {"messages": [AIMessage(content=answer)]}

def direct(state: State) -> State:
    """Answer questions that don't need database access — greetings, general
    knowledge, follow-up clarifications, etc."""
    messages = [
        SystemMessage(content="You are a helpful assistant. Answer in English."),
    ] + state["messages"]  # prepend system prompt to the full history
    result = model.invoke(messages)
    return {"messages": [AIMessage(content=result.content)]}

def route_decision(state: State) -> str:
    """Edge function: tells LangGraph which branch to take after the router node.
    Must return a key that matches one of the conditional_edges mapping below."""
    return state["needs_sql"]  # "YES" → sql_agent, "NO" → direct

# ── GRAFO ─────────────────────────────────────────────────────────────────
# StateGraph is a directed graph where each node is a function and edges
# define the execution order. Conditional edges allow dynamic branching.
builder = StateGraph(State)

# Register nodes by name — the name is also used in edge declarations.
builder.add_node("router", router)
builder.add_node("sql_agent", sql_agent)
builder.add_node("direct", direct)

# Every request enters the graph at the "router" node.
builder.set_entry_point("router")

# After "router" runs, call `route_decision` to pick the next node.
builder.add_conditional_edges(
    "router",
    route_decision,
    {
        "YES": "sql_agent",  # question needs data → run SQL sub-agent
        "NO": "direct",      # question is general → answer directly
    }
)

# Both terminal nodes flow to END, which signals LangGraph to stop.
builder.add_edge("sql_agent", END)
builder.add_edge("direct", END)

# MemorySaver stores the state after each graph run so that, when the same
# thread_id is used again, the full conversation history is restored.
memory = MemorySaver()

# Compile the builder into an executable graph, wiring in the checkpointer.
graph = builder.compile(checkpointer=memory)

# ── UI ────────────────────────────────────────────────────────────────────
st.title("🗄️ SQL Agent")
st.caption("Ask questions about the database in natural language")

# st.session_state persists across Streamlit reruns (each user interaction
# causes a full script rerun, so we store mutable data in session_state).
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []  # list of {"role": ..., "content": ...} dicts

if "thread_id" not in st.session_state:
    # A fixed thread_id ties all messages to the same MemorySaver checkpoint,
    # giving the agent a continuous memory across multiple questions.
    st.session_state.thread_id = "streamlit-session"

# Replay all previous messages so the chat UI shows the full conversation.
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# st.chat_input blocks until the user submits; returns None on page load.
question = st.chat_input("Ask a question about the data...")

if question:
    # Show the user's message immediately, before the agent responds.
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            # Pass the thread_id so LangGraph can load/save the checkpoint.
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            result = graph.invoke(
                {"messages": [HumanMessage(content=question)]},
                config=config
            )
            # The final node always appends an AIMessage; grab its text content.
            answer = result["messages"][-1].content
        st.write(answer)

    # Persist this turn to session_state so it appears on the next rerun.
    st.session_state.chat_history.append({"role": "user", "content": question})
    st.session_state.chat_history.append({"role": "assistant", "content": answer})
