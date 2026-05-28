"""
Structured logging — JSON em stdout, request_id por scope, hashing de
campos categoria B.

Decisões travadas (sessão 27/05/2026, ver project_sql_agent_2026_05_27
na memória):
  1. stdlib `logging` + JsonFormatter custom (zero dep, didático).
  2. Categoria B (PII risk):
     - question: q_hash em INFO; texto em DEBUG.
     - sql_generated: sql_hash + sql_len em INFO; SQL em DEBUG.
     - answer: só answer_len + output_tokens em INFO; texto em DEBUG.
       (Sem hash em INFO — answer é o maior vetor de PII e hash
       raramente é útil pra debug, já temos request_id pra correlacionar.)
  3. Sampling: 100% (volume baixo do agente; revisitar em Cap 4+).
  4. Destino: stdout (12-factor, container-friendly).
  5. Log injection: defesa via json.dumps (escapa \\n e aspas).
     Teste unitário em test_structured_logging.py prova a property.

request_id:
  Gerado server-side em todo request HTTP (UUID4). ContextVar propaga
  pro logger sem precisar passar como arg — qualquer log do scope do
  request herda o id automaticamente. Cliente NÃO pode setar o id
  (vetor de log forge: cliente poderia mandar id de outra request
  pra poluir/sabotar auditoria).
"""
import contextvars
import hashlib
import json
import logging
import sys
from typing import Any


# ContextVar é a versão thread-safe (e async-task-safe) de TLS. Cada
# request roda no seu próprio "logical scope" — uma task asyncio. Setar
# a var no início da task faz todos os logs daquela task verem o valor.
# Tasks rodando em paralelo veem o valor DELAS — não vaza entre requests.
# Default "-" indica "fora de scope de request" (logs de startup, eval CLI).
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


# Campos que todo LogRecord tem (criados pelo logging.Logger).
# Excluímos do JSON output porque são ou redundantes (`msg` vira `event`)
# ou ruído pra agregador (filename/lineno/funcName poluem em produção,
# úteis só em dev). Mantemos via campos explícitos quem importa.
_LOGRECORD_BUILTINS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime", "taskName",
})


class JsonFormatter(logging.Formatter):
    """
    Renderiza LogRecord como JSON em uma linha. Campos extras passados
    via `logger.info("event", extra={"k": "v"})` viram chaves no JSON.

    Por que escrever na mão e não usar python-json-logger?
      Didático: ver o LogRecord por dentro força entender o modelo do
      stdlib (handlers, formatters, propagação). Em ~30 linhas você tem
      tudo que importa: timestamp ISO, level, event, request_id, extras.

    Por que json.dumps com ensure_ascii=False?
      Pra acento aparecer literal no log (português legível).
      Continua escapando \\n e aspas — que é o que importa pra defesa
      contra log injection (categoria 5 das decisões).

    Por que default=str?
      Fallback pra objetos não-JSON (datetime, UUID, etc.) — evita
      crash em runtime quando alguém passa algo inesperado em extra=.

    Por que serializar exc_info num campo "exc_info"?
      log.exception()/log.error(exc_info=True) anexam o traceback em
      record.exc_info. A Formatter base concatena isso como texto multi-
      linha DEPOIS da mensagem; aqui, num JSON de uma linha, isso quebraria
      o formato. Então renderizamos o traceback via formatException() e o
      colocamos numa string única (o json.dumps escapa os \\n internos),
      preservando o stack completo pro operador SEM virar várias linhas de
      log nem reabrir o vetor de log injection.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "event": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        # Extras: tudo que não é built-in do LogRecord (inclui o que
        # foi passado via `extra=` no logger.info call).
        for key, value in record.__dict__.items():
            if key in _LOGRECORD_BUILTINS or key.startswith("_"):
                continue
            payload[key] = value
        # Traceback: só presente quando log.exception() / exc_info=True.
        # formatException() devolve a string multi-linha do stack; vira
        # um campo único (json.dumps escapa os \n), então uma entrada de
        # erro continua sendo UMA linha de log com o stack completo dentro.
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configura o root logger pra cuspir JSON em stdout.

    Idempotente: chamadas múltiplas (testes, reload de dev) não
    duplicam handlers — limpa os existentes antes.
    """
    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)


def hash_text(text: str, length: int = 12) -> str:
    """
    Fingerprint estável de texto pra logging categoria B.

    SHA-256 truncado em N chars. Não é password — é fingerprint pra
    correlação ("essa pergunta apareceu antes? esse SQL é repetido?").
    Colisão impossível no volume do agente (12 chars hex = 48 bits).
    Sem salt: queremos que o mesmo texto sempre dê o mesmo hash, pra
    contagem/dedup; salt quebraria isso e não adiciona segurança aqui
    (não é credential).
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]
