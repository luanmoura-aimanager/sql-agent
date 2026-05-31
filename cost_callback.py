"""
Cost attribution callback — captura input/output tokens de cada chamada
de LLM e acumula via ContextVar pro scope do request.

Decisão travada (Sessão D-3, 31/05/2026): agregação via ContextVar
durante o request, 1 INSERT por request no fim do /query (não 1 por
chamada de LLM). Razões:
  - Schema `cost_events` foi pensado em D-1 como "fact per request" —
    1:1 com X-Request-ID do log.
  - Hoje só 1 modelo. Quando entrar model heterogeneity (router=haiku,
    react=sonnet, p.ex.), volta como side-mission: 1 INSERT por
    (request_id, model_name) pair.
  - Linhas-conta no DB cresce N× menos.

Reusa o padrão de ContextVar que já dominamos com `request_id_var`
(Sessão D-1 — logging_config.py). Copy-on-write por task asyncio:
requests concorrentes não vazam tokens entre si.

Fluxo:
  1. Middleware no request inicializa via `init_accumulator(token_hash)`.
  2. graph.invoke(config={"callbacks": [cost_handler]}) propaga o
     handler pra TODAS as chamadas de LLM (router + react + tool
     loops). langgraph faz a propagação automaticamente.
  3. CostCallbackHandler.on_llm_end lê AIMessage.usage_metadata e
     mutates o dict acumulador.
  4. /query handler chama `read_accumulator()` no fim, calcula
     cost_usd via pricing.calculate_cost_usd, INSERT em cost_events.
  5. Middleware finally faz `reset_accumulator(token)` pra não vazar
     pra fora do scope (mesma defesa do request_id_var).
"""
import contextvars
import logging
from typing import Any, TypedDict

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


log = logging.getLogger("sql_agent.cost")


class CostAccumulator(TypedDict):
    """Estado mutável durante um request. Resetado por middleware."""
    input_tokens: int
    output_tokens: int
    model_name: str | None  # None se nenhuma chamada ainda; preenchido na 1ª.
    token_hash: str         # do Bearer, pra logar/INSERT depois.
    call_count: int         # quantas chamadas de LLM rolaram no scope.


# ContextVar com default None — fora de scope de request (startup, eval
# CLI, sem middleware ativo), o callback vira no-op em vez de crashar.
cost_accumulator_var: contextvars.ContextVar[CostAccumulator | None] = (
    contextvars.ContextVar("cost_accumulator", default=None)
)


def init_accumulator(token_hash: str) -> contextvars.Token:
    """Inicia accumulator zerado. Devolve token pra reset() no finally.

    O middleware do request chama isso no entry; reset no finally.
    """
    fresh: CostAccumulator = {
        "input_tokens": 0,
        "output_tokens": 0,
        "model_name": None,
        "token_hash": token_hash,
        "call_count": 0,
    }
    return cost_accumulator_var.set(fresh)


def reset_accumulator(token: contextvars.Token) -> None:
    """Reset do ContextVar — mesmo padrão de request_id_var.

    Sem reset, o valor vaza pra fora do scope dentro da mesma task
    asyncio (aprendizado da Sessão D-1).
    """
    cost_accumulator_var.reset(token)


def read_accumulator() -> CostAccumulator | None:
    """Lê o estado atual. None se chamado fora de scope de request."""
    return cost_accumulator_var.get()


class CostCallbackHandler(BaseCallbackHandler):
    """Captura tokens de cada chamada de LLM e acumula no ContextVar.

    Singleton — uma instância módulo-level é o suficiente. ContextVar
    garante isolamento entre requests; o handler é stateless (estado
    todo vive no ContextVar do scope da task asyncio).

    Por que BaseCallbackHandler e não AsyncCallbackHandler?
      langgraph propaga callbacks pra sync E async invokes — base
      handler é chamado nos dois casos. Manter sync simplifica.

    Por que NÃO mexer em pricing aqui (só captura tokens)?
      Separação de responsabilidade: callback é "tokens em rede";
      pricing é "tokens × $/MTok". Isso permite trocar tabela de
      pricing sem mexer no callback, e testar cada peça isolada.
    """

    def on_llm_end(  # type: ignore[override]
        self, response: LLMResult, **kwargs: Any
    ) -> None:
        acc = cost_accumulator_var.get()
        if acc is None:
            # Fora de scope de request (ex: eval CLI, startup, teste
            # unitário do callback sem middleware). Vira no-op em vez
            # de crashar — defesa silenciosa, comportamento previsível.
            return

        # response.generations é list[list[Generation]]. Pra ChatModel,
        # cada generation tem `.message` (AIMessage) com `usage_metadata`.
        input_total = 0
        output_total = 0
        for gen_list in response.generations:
            for gen in gen_list:
                msg = getattr(gen, "message", None)
                if msg is None:
                    continue
                usage = getattr(msg, "usage_metadata", None) or {}
                input_total += int(usage.get("input_tokens", 0) or 0)
                output_total += int(usage.get("output_tokens", 0) or 0)

        # llm_output em alguns paths antigos do langchain tem
        # token_usage fora de generations[i].message. Anthropic via
        # langchain-anthropic v1+ já bota tudo em usage_metadata, mas
        # mantemos fallback defensivo pra não perder contagem se a
        # estrutura mudar entre versões.
        if input_total == 0 and output_total == 0:
            llm_output = response.llm_output or {}
            token_usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
            input_total = int(token_usage.get("input_tokens", 0) or token_usage.get("prompt_tokens", 0) or 0)
            output_total = int(token_usage.get("output_tokens", 0) or token_usage.get("completion_tokens", 0) or 0)

        # Model name: extraímos da primeira chamada e mantemos.
        # Quando virar model heterogeneity (side-mission), vira dict
        # de (model_name → totals) e a integração no /query faz N INSERTs.
        if acc["model_name"] is None:
            llm_output = response.llm_output or {}
            acc["model_name"] = (
                llm_output.get("model_name")
                or llm_output.get("model")
                # Última cartada: pega do .response_metadata da AIMessage
                or _extract_model_from_generations(response)
            )

        acc["input_tokens"] += input_total
        acc["output_tokens"] += output_total
        acc["call_count"] += 1

        # Log per-call em DEBUG — útil pra incident response sem inflar
        # INFO. Pattern do query_debug (D-1): texto granular só em DEBUG.
        log.debug(
            "llm_call_handled",
            extra={
                "input_tokens": input_total,
                "output_tokens": output_total,
                "running_total_input": acc["input_tokens"],
                "running_total_output": acc["output_tokens"],
                "call_count": acc["call_count"],
            },
        )


def _extract_model_from_generations(response: LLMResult) -> str | None:
    """Fallback pra achar model_name na response_metadata da AIMessage."""
    for gen_list in response.generations:
        for gen in gen_list:
            msg = getattr(gen, "message", None)
            if msg is None:
                continue
            meta = getattr(msg, "response_metadata", None) or {}
            model = meta.get("model_name") or meta.get("model")
            if model:
                return model
    return None


# Singleton — handler stateless, ContextVar leva o estado por request.
cost_handler = CostCallbackHandler()
