import os

from agent import run_agent
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import List

app = FastAPI()

# Lê o token esperado uma vez, no startup. Se a env var não estiver setada,
# fail-fast: o servidor não sobe sem ela. É preferível quebrar no boot
# do que aceitar requests sem auth por engano.
EXPECTED_TOKEN = os.environ["API_TOKEN"]


def verify_token(authorization: str | None = Header(None)) -> None:
    """
    Valida o header Authorization da request.

    Espera o formato 'Bearer <token>'. Compara com EXPECTED_TOKEN
    (lido do env no startup). Rejeita qualquer outra coisa com 401.

    Por que Header(None) e não Header(...)?
      - Header(...) marca o parâmetro como REQUIRED no schema do FastAPI.
        Quando o header falta, o FastAPI corta a request com 422
        (validation error) ANTES de chamar essa função.
      - 422 é semanticamente "request malformada" (schema). O caso
        "cliente não mandou credenciais" é 401 ("unauthorized").
        Manter os dois separados ajuda quem consome a API a tratar os
        casos certo (ex: refresh de token vs corrigir o payload).
      - Header(None) faz o header ser opcional do ponto de vista do
        schema; a checagem de presença vira responsabilidade desta
        função, que devolve 401 consistentemente.
    """
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth scheme")

    token = authorization.removeprefix("Bearer ")
    if token != EXPECTED_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")


class Message(BaseModel):
    role: str      # "user" ou "assistant"
    content: str

class QueryRequest(BaseModel):
    question: str
    history: List[Message] = []   # opcional — default é lista vazia

class QueryResponse(BaseModel):
    answer: str

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest, _: None = Depends(verify_token)):
    try:
        history = [{"role": m.role, "content": m.content} for m in request.history]
        answer = run_agent(request.question, history)
        return QueryResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
