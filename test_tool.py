import sqlite3
import anthropic
import json

client = anthropic.Anthropic()

# ── 1. DEFINIÇÃO DA TOOL ──────────────────────────────────────────────────
# Aqui você está dizendo ao Claude: "você tem acesso a esta ferramenta"
# Claude não executa a tool — ele apenas DECIDE quando e como chamá-la
tools = [
    {
        "name": "run_sql",
        "description": "Executa uma query SQL no banco de dados da loja e retorna os resultados",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A query SQL a ser executada"
                }
            },
            "required": ["query"]
        }
    }
]

# ── 2. FUNÇÃO REAL QUE EXECUTA O SQL ─────────────────────────────────────
# Esta função roda no SEU computador, não no Claude
def run_sql(query):
    conn = sqlite3.connect("store.db")
    cursor = conn.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    columns = [description[0] for description in cursor.description]
    conn.close()
    return {"columns": columns, "rows": results}

# ── 3. PERGUNTA DO USUÁRIO ────────────────────────────────────────────────
# question = "Quais clientes são de Fortaleza?"
question = input("Pergunta: ")

print(f"Pergunta: {question}\n")

# ── 4. PRIMEIRA CHAMADA AO CLAUDE ────────────────────────────────────────
# Claude recebe a pergunta e a lista de tools disponíveis
response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": question}]
)

print(f"Claude decidiu: {response.stop_reason}\n")

# ── 5. CLAUDE PEDIU PARA USAR UMA TOOL? ──────────────────────────────────
if response.stop_reason == "tool_use":
    # extrai qual tool e com quais argumentos
    tool_call = next(block for block in response.content if block.type == "tool_use")
    print(f"Tool chamada: {tool_call.name}")
    print(f"Query gerada pelo Claude: {tool_call.input['query']}\n")

    # executa a tool de verdade
    result = run_sql(tool_call.input["query"])
    print(f"Resultado do banco: {result}\n")

    # ── 6. SEGUNDA CHAMADA: devolve o resultado pro Claude ────────────────
    # Agora Claude formula a resposta final com base no resultado real
    final_response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        tools=tools,
        messages=[
            {"role": "user", "content": question},
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": tool_call.id, "content": json.dumps(result)}
            ]}
        ]
    )

    print(f"Resposta final: {final_response.content[0].text}")
