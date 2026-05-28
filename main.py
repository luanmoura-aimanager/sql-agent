import ipaddress
import os

from agent import run_agent
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from pydantic import BaseModel
from typing import List

from slowapi import Limiter, _rate_limit_exceeded_handler  # noqa: PLC2701
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

app = FastAPI()


# Resolução de IP do cliente respeitando X-Forwarded-For — mas só
# quando o request veio de um proxy confiável.
#
# Por que não usar slowapi.util.get_ipaddr direto?
#   get_ipaddr lê X-Forwarded-For SEM verificar a origem. Qualquer
#   cliente pode mandar 'X-Forwarded-For: 1.2.3.4' e burlar o rate
#   limit por IP (basta variar o header a cada request). É o footgun
#   clássico de quem ativa XFF sem trust model.
#
# Modelo de confiança:
#   TRUSTED_PROXIES é uma env var opcional, lista de IPs separados por
#   vírgula (ex: "10.0.0.5,10.0.0.6"). Só quando request.client.host
#   estiver nessa lista é que XFF é respeitado; caso contrário, fica
#   valendo o peer IP (request.client.host). Vazio/não setado =
#   comportamento pre-XFF, idêntico ao get_remote_address.
#
# Quando setar:
#   Em deploy atrás de nginx/ALB/Cloudflare, colocar os IPs internos
#   dos proxies. Em dev local (sem proxy), deixar vazio.
#
# XFF format: "client, proxy1, proxy2" — o IP do cliente real é o
# primeiro (leftmost). Trim de espaços; header malformado → fallback peer.
#
# Normalização: IPs são comparados em forma canônica (ip_address().compressed)
# pra evitar mismatch por casing/zero-compression no IPv6 — "2001:DB8::1"
# bate "2001:db8::1". Strings que não parseiam como IP (ex: "testclient" do
# TestClient, ou typos no env var) caem no fallback raw; isso preserva a
# comparação literal em dev e mantém typos como entradas inertes (não
# casam com nenhum peer real, então não criam bypass).
def _normalize_ip(value: str) -> str:
    try:
        return ipaddress.ip_address(value).compressed
    except ValueError:
        return value


def _parse_trusted_proxies(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {_normalize_ip(ip.strip()) for ip in raw.split(",") if ip.strip()}


TRUSTED_PROXIES = _parse_trusted_proxies(os.environ.get("TRUSTED_PROXIES"))


def get_client_ip(request: Request) -> str:
    # request.client pode ser None em estados anômalos do ASGI (cliente
    # desconectado antes do dispatch). Cai num bucket compartilhado
    # "unknown" — não é bypass (sem peer real, sem como rotear a quota).
    peer = request.client.host if request.client else "unknown"
    peer = _normalize_ip(peer)
    # Re-lê o módulo em runtime pra que testes (e SIGHUP-style reloads
    # eventuais) possam alterar TRUSTED_PROXIES sem reimportar o módulo.
    trusted = globals()["TRUSTED_PROXIES"]
    if peer not in trusted:
        return peer
    xff = request.headers.get("x-forwarded-for", "")
    first = xff.split(",")[0].strip()
    return first or peer


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
# key_func: get_client_ip (definida acima) — XFF-aware com trust check.
#   Storage default é in-memory: um dict no processo do uvicorn.
#   Reinicia → zera. Multi-worker → cada worker tem o seu (problema a
#   resolver com Redis quando entrar deploy multi-instância).
#
# default_limits: aplicam a todas as rotas. /health é exemptado abaixo
# pra não enfiar 429 em health check de load balancer.
limiter = Limiter(
    key_func=get_client_ip,
    default_limits=["60/minute", "500/hour"],
    # headers_enabled liga: X-RateLimit-Limit, X-RateLimit-Remaining,
    # X-RateLimit-Reset e Retry-After nas respostas. Sem isso, cliente
    # que toma 429 não sabe quando retentar.
    headers_enabled=True,
)
app.state.limiter = limiter
# Handler que converte RateLimitExceeded → response 429.
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def get_token_key(request: Request) -> str:
    """Extrai o bearer token do header Authorization como chave do rate limit."""
    auth = request.headers.get("authorization", "")
    return f"token:{auth.removeprefix('Bearer ').strip()}"


# Limiter separado para rate limit por TOKEN (camada pós-auth).
#
# Por que um segundo Limiter e não reusar o mesmo `limiter`?
#   SlowAPIMiddleware._should_exempt() pula rotas que estão em
#   limiter._route_limits. Se usarmos @limiter.limit no /query,
#   o middleware para de verificar os default limits (60/min IP) para
#   essa rota — os dois layers entram em conflito.
#   Com um Limiter separado, /query NÃO aparece em limiter._route_limits,
#   então o middleware continua aplicando o IP limit normalmente.
#   O decorator do token_limiter roda depois do auth (Depends) e aplica
#   o limit por token de forma independente.
token_limiter = Limiter(
    key_func=get_token_key,
    default_limits=[],
    headers_enabled=True,
)

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
@token_limiter.limit("30/minute;200/hour")
async def query(request: Request, response: Response, body: QueryRequest, _: None = Depends(verify_token)):
    try:
        history = [{"role": m.role, "content": m.content} for m in body.history]
        answer = run_agent(body.question, history)
        return QueryResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
