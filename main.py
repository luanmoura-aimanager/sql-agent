import os

from agent import run_agent
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import List

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

app = FastAPI()

# Rate limiting (camada IP — aplica ANTES do auth).
#
# Por que middleware e não @limiter.limit decorator?
#   Em FastAPI, o ciclo é: matcheia rota → resolve TODOS os Depends
#   (incluindo verify_token) → SÓ ENTÃO chama a função (que é onde o
#   decorator do slowapi rodaria). Ou seja, decorator roda DEPOIS do auth.
#   Pra rate limit defender contra brute force de token, ele tem que
#   rodar ANTES — e middleware roda fora do ciclo de Depends, antes
#   de qualquer dispatch.
#
# key_func: como identificar quem está fazendo o request.
#   get_remote_address lê request.client.host (IP do cliente que abriu o
#   socket TCP). Storage default é in-memory: um dict no processo do uvicorn.
#   Reinicia → zera. Multi-worker → cada worker tem o seu (problema a
#   resolver com Redis quando entrar deploy multi-instância).
#
# default_limits: aplicam a todas as rotas. /health é exemptado abaixo
# pra não enfiar 429 em health check de load balancer.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute", "500/hour"],
    # headers_enabled liga: X-RateLimit-Limit, X-RateLimit-Remaining,
    # X-RateLimit-Reset e Retry-After nas respostas. Sem isso, cliente
    # que toma 429 não sabe quando retentar.
    headers_enabled=True,
)
app.state.limiter = limiter
# Handler que converte RateLimitExceeded → response 429.
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# Middleware que faz a checagem antes do dispatch da rota.
app.add_middleware(SlowAPIMiddleware)


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
@limiter.exempt
async def health():
    return {"status": "ok"}

@app.post("/query", response_model=QueryResponse)
async def query(body: QueryRequest, _: None = Depends(verify_token)):
    try:
        history = [{"role": m.role, "content": m.content} for m in body.history]
        answer = run_agent(body.question, history)
        return QueryResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
