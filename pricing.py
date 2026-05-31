"""
Pricing table loader pra cálculo de cost_usd.

Decisão travada (Sessão D-3, 31/05/2026): formato JSON nested separando
metadata (`version`) de dados (`models`). Razões:
  - Crescimento sem poluir: quando entrar sonnet/opus/etc., `models`
    cresce mas `version` fica isolado.
  - JSON Schema friendly — estrutura clara pra futuras validações.
  - Per-MTok (não per-token) bate com como Anthropic publica preços
    ($0.80 / MTok input pro haiku 4.5). Mais legível pra editar à mão
    quando preço muda.

Formato:
  {
    "version": "2026-05-31",
    "models": {
      "claude-haiku-4-5-20251001": {
        "input_per_mtok": 0.80,
        "output_per_mtok": 4.00
      }
    }
  }

Cálculo de cost (decimal exato, não float):
  cost_usd = (input_tokens / 1_000_000) * input_per_mtok
           + (output_tokens / 1_000_000) * output_per_mtok

Decimal porque dinheiro NUNCA em float (mesma razão do schema NUMERIC).
"""
import json
from decimal import Decimal
from pathlib import Path
from typing import TypedDict


class ModelPricing(TypedDict):
    input_per_mtok: float
    output_per_mtok: float


class PricingTable(TypedDict):
    version: str
    models: dict[str, ModelPricing]


# Carregado uma vez no import. Pricing muda raramente (release de modelo);
# recarregar por request é desperdício. Em prod, pra hot-reload, dá pra
# adicionar um endpoint /admin/reload-pricing — fora de escopo aqui.
_PRICING_PATH = Path(__file__).parent / "pricing.json"


def _load() -> PricingTable:
    with open(_PRICING_PATH, encoding="utf-8") as f:
        data: PricingTable = json.load(f)
    # Validação mínima — falha fast se o JSON estiver malformado.
    # Em prod com mais modelos vale considerar jsonschema/pydantic.
    if "version" not in data or "models" not in data:
        raise ValueError(
            f"pricing.json inválido: precisa de 'version' e 'models' "
            f"(achei: {list(data.keys())})"
        )
    if not data["models"]:
        raise ValueError("pricing.json sem nenhum modelo definido")
    for model_name, prices in data["models"].items():
        for key in ("input_per_mtok", "output_per_mtok"):
            if key not in prices:
                raise ValueError(
                    f"pricing.json modelo {model_name!r}: falta '{key}'"
                )
            if prices[key] < 0:
                raise ValueError(
                    f"pricing.json modelo {model_name!r}: {key} negativo"
                )
    return data


_TABLE: PricingTable = _load()

# Constantes Decimal construídas UMA vez no import. Antes eram recriadas
# a cada calculate_cost_usd (Decimal(str(float)) + Decimal("1000000") +
# Decimal("0.00000001")); como os valores são estáticos, pré-converter
# evita reconstruir os mesmos objetos a cada request no hot path.
_MTOK = Decimal("1000000")
# Schema é NUMERIC(12, 8) — 8 casas decimais. Quantum fixo pro quantize.
_QUANTUM = Decimal("0.00000001")
# Preços por modelo já como Decimal exato (str() no float evita contaminar
# com imprecisão do float ao virar Decimal). Chave = model_name.
_DECIMAL_PRICES: dict[str, tuple[Decimal, Decimal]] = {
    name: (
        Decimal(str(prices["input_per_mtok"])),
        Decimal(str(prices["output_per_mtok"])),
    )
    for name, prices in _TABLE["models"].items()
}


def get_version() -> str:
    """Versão da tabela pra registrar em cada cost_event (auditabilidade)."""
    return _TABLE["version"]


def calculate_cost_usd(
    model_name: str, input_tokens: int, output_tokens: int
) -> Decimal:
    """Calcula cost em USD via Decimal exato.

    Levanta KeyError se modelo não estiver na tabela — sinal claro de
    que pricing.json precisa ser atualizado antes de processar requests
    com esse modelo.
    """
    if model_name not in _DECIMAL_PRICES:
        raise KeyError(
            f"Modelo {model_name!r} não está em pricing.json — "
            f"atualize pricing.json antes de processar requests."
        )
    input_price, output_price = _DECIMAL_PRICES[model_name]
    cost = (Decimal(input_tokens) / _MTOK) * input_price
    cost += (Decimal(output_tokens) / _MTOK) * output_price
    # Quantize pra não passar precisão maior que NUMERIC(12, 8) pro DB
    # (que truncaria silenciosamente).
    return cost.quantize(_QUANTUM)
