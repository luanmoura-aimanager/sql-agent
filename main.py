import ipaddress
import logging
import os
import time
import uuid

from agent import run_agent
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from pydantic import BaseModel
from typing import List

from slowapi import Limiter, _rate_limit_exceeded_handler  # noqa: PLC2701
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from logging_config import hash_text, request_id_var, setup_logging
from cost_callback import init_accumulator, read_accumulator, reset_accumulator
import db
import pricing

# Setup do logging acontece no import — antes de qualquer logger.info()
# em outros módulos. Idempotente (chamadas repetidas em teste não
# duplicam handlers).
setup_logging()
log = logging.getLogger("sql_agent.api")

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


# request_id middleware — gera UUID4 por request e disponibiliza:
#   - via ContextVar (logs do scope herdam automaticamente o id)
#   - via response header X-Request-ID (cliente pode citar em suporte)
#
# Por que NÃO aceitar X-Request-ID do cliente?
#   Vetor de log forge: cliente podia mandar id de outra request pra
#   poluir auditoria. Se precisar correlacionar com chamador upstream
#   no futuro, validar como UUID e marcar 'client_supplied=true' no log.
#
# Por que @app.middleware("http") e não BaseHTTPMiddleware classe?
#   Equivalente sintático; o decorator é mais ergonômico pra closures
#   curtas como essa.
#
# Ordem de execução: middlewares FastAPI são LIFO — o último registrado
# roda primeiro. Esse aqui é registrado DEPOIS do SlowAPIMiddleware, então
# roda PRIMEIRO no request — e o ContextVar já está setado quando o
# SlowAPI faz o rate limit check (se a gente decidir logar 429s no futuro).
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = str(uuid.uuid4())
    token = request_id_var.set(rid)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        # reset() é importante: em ambiente single-thread async, o
        # ContextVar carrega o último valor pra fora do scope se a
        # gente não der reset. Não vaza entre tasks (cada task tem o seu
        # copy-on-write), mas vaza dentro da mesma task pós-request.
        request_id_var.reset(token)


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
    # Latency: perf_counter (monotonic, alta resolução). Não usa
    # time.time() pra evitar pulos por NTP sync.
    t0 = time.perf_counter()
    q_hash = hash_text(body.question)
    # token_hash = fingerprint do Bearer pra agregar cost por cliente sem
    # guardar o token em texto. Mesma função do logging_config.
    bearer = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    token_hash = hash_text(bearer)
    # Inicializa o cost accumulator no scope do request. O ContextVar
    # leva os totais por copy-on-write (não vaza entre tasks asyncio).
    # init/reset bracketa só o trecho do agent — middleware não precisa
    # saber disso, isolando a camada de billing do resto.
    acc_token = init_accumulator(token_hash=token_hash)
    try:
        history = [{"role": m.role, "content": m.content} for m in body.history]
        answer = run_agent(body.question, history)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        acc = read_accumulator() or {}
        input_tokens = int(acc.get("input_tokens", 0))
        output_tokens = int(acc.get("output_tokens", 0))
        model_name = acc.get("model_name")
        call_count = int(acc.get("call_count", 0))

        # Cost calc + INSERT só fazem sentido se o agente realmente
        # chamou algum LLM (call_count > 0) e o callback conseguiu
        # identificar o modelo. Sem isso, gravar linha com model_name
        # NULL ou cost 0 seria poluir a tabela.
        cost_usd = None
        pricing_version = pricing.get_version()
        if call_count > 0 and model_name:
            cost_usd = pricing.calculate_cost_usd(
                model_name, input_tokens, output_tokens
            )
            # Sync INSERT — await dentro do handler. Trade-off real
            # (response latency inclui DB write; DB lento → response
            # lenta) é tema de Path C (async + degradação) deferido
            # pra Cap 4+. Hoje sync é o pattern didático correto e
            # produção pequena sobrevive bem com isso.
            async with db.engine.begin() as conn:
                await conn.execute(
                    db.cost_events.insert(),
                    {
                        "request_id": uuid.UUID(request_id_var.get()),
                        "token_hash": token_hash,
                        "model_name": model_name,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "cost_usd": cost_usd,
                        "pricing_version": pricing_version,
                    },
                )

        # INFO: categoria A (latência, status) + categoria B com hash.
        # Cost fields entram aqui pra log aggregator agrupar por token_hash
        # sem precisar de query no DB ("quanto X gastou na última hora?"
        # via Datadog/Loki SUM em vez de query no Postgres).
        log.info(
            "query_handled",
            extra={
                "q_hash": q_hash,
                "answer_len": len(answer),
                "history_len": len(body.history),
                "latency_ms": latency_ms,
                "status": 200,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": str(cost_usd) if cost_usd is not None else None,
                "model_name": model_name,
                "pricing_version": pricing_version,
                "llm_call_count": call_count,
            },
        )
        # DEBUG: texto completo de question e answer. Só sai se o root
        # logger estiver em DEBUG (env var LOG_LEVEL ou setup explícito
        # em incident response). isEnabledFor evita o custo de montar
        # o extra se ninguém vai consumir.
        if log.isEnabledFor(logging.DEBUG):
            log.debug(
                "query_debug",
                extra={
                    "question_text": body.question,
                    "answer_text": answer,
                },
            )
        return QueryResponse(answer=answer)
    except Exception as e:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        log.exception(
            "query_failed",
            extra={
                "q_hash": q_hash,
                "latency_ms": latency_ms,
                "status": 500,
                "error_type": type(e).__name__,
            },
        )
        # Detail genérico — NÃO inclui str(e). Razão: categoria C das
        # decisões de telemetria (27/05/2026) — "nunca pro cliente":
        # token plaintext, Authorization header, stack traces. str(e)
        # de exceptions do agente (langgraph, anthropic SDK, sqlite)
        # rotineiramente vaza nomes de tabela, paths, prompts, ou
        # excerpts de SQL — equivalente a meio-stack-trace.
        #
        # O cliente recebe o request_id via header X-Request-ID
        # (middleware request_id_middleware). Suporte usa esse id pra
        # achar o log estruturado, que tem error_type + exc_info completo.
        # Assim o operador tem visibilidade e o cliente não vê nada útil
        # pra reconnaissance.
        raise HTTPException(status_code=500, detail="Internal error")
    finally:
        # Reset do cost accumulator — mesma defesa do request_id_var
        # (Sessão D-1): sem reset, valor vaza pra fora do scope dentro
        # da mesma task asyncio. Não vaza entre tasks (copy-on-write).
        reset_accumulator(acc_token)
