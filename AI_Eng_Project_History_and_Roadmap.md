# AI Engineering Journey — Documento de Contexto

Última atualização: 21 de maio de 2026
Propósito: dar ao Claude contexto completo para continuar as sessões sem perder história. Ler antes de responder.

> **Mudança estrutural (13 de maio de 2026):** o roadmap foi reorganizado por **capítulos** e **sessões**, não mais por semanas e dias. Não há prazo para concluir capítulos. A disciplina é fazer um pouco todo dia; quando houver tempo, fazer mais. Ver Seção 4 para a nova filosofia de sessão.
>
> **Pivot prático (15 de maio de 2026, mentoria com Emanuel):** o foco sai do aprofundamento teórico (eval frameworks, prompt engineering como tópico isolado, mini-capstone "acadêmico") e vai para **construção de produto** dentro de framing de plataforma enterprise. O Cap 2 fecha após RAG de produção. Cap 3 ganha três camadas (Dev / Governance / UI) e o princípio "users where they are". Teoria entra on-demand. Ver Seção 20 para o registro completo.
>
> **Cadência e foco de projeto (21 de maio de 2026):** o deck do Emanuel passa de cadência semanal (sexta) para **entrega ao fechar cada capítulo**. Além disso, **um projeto por capítulo** — Cap 3 inteiro dentro do `sql-agent`, troca de projeto só ao virar de capítulo. Ver Seção 20 para o registro completo.

---

## 1. Quem sou

**Nome:** Misael (Luan Misael Gomes de Moura)
**Email:** luanmisaelmoura@gmail.com
**Trabalho atual:** Senior Data Scientist no Nubank (~4-5 anos no total, 2-3 como Senior DS)
**Localização:** São Paulo (quer voltar pra Fortaleza no longo prazo)
**Coach:** Emanuel Fontelles (Lenotis) — recebe uma apresentação a cada capítulo concluído
**Mentor de IA:** Claude (este projeto) — define tarefas das sessões, ensina conceitos, explica código

### Direção (sem data fixa)

- **Próximo papel:** AI Engineer remoto — em empresa internacional, com compensação compatível
- **Arco longo (~12-18 meses depois):** crescer para AI Solutions Architect — quem desenha sistemas de IA end-to-end pra problemas de negócio

### Por que essa transição

- Nubank retornando ao escritório (2 dias/semana a partir de julho/2026, subindo pra 3)
- Crescimento de carreira limitado dentro do Nubank
- Skills muito acopladas a ferramentas internas do Nubank
- Quer trabalho 100% remoto, de Fortaleza

### Objetivo financeiro
- Atual: ~R$20k/mês base, ~R$25k efetivo com bônus
- Meta: manter compensação similar via empresas remotas internacionais (USD/EUR)

---

## 2. Filosofia da jornada (atualizada em 15 de maio de 2026)

Cinco princípios guiam tudo:

1. **Disciplina > prazo.** Não há meta de chegar em X até Y. Há meta de fazer um pouco todo dia, sem falhar mais que o mínimo possível. A consistência é o ativo.
2. **Profundidade > variedade.** Entender um vector DB a fundo > conhecer cinco superficialmente. Aplicado em todo capítulo.
3. **Construção em camadas.** Cada projeto principal (`sql-agent`, `pdf-chat`, eventualmente Clayton) cresce em camadas em vez de ser substituído por outro. Aprender sobre o mesmo projeto várias vezes, com lentes diferentes, é o exercício.
4. **Direção > detalhe; teoria on-demand.** *(Emanuel, 15/05/2026)* "Melhor saber o caminho do A ao B do que o detalhe de cada parada." A analogia é de música: aprende a tocar a música primeiro; teoria musical entra quando a música pede. Aplicado: o tópico só é aprofundado quando um projeto exige; senão, fica na lista de "sei onde encontrar".
5. **Ciclo de entrega curto: semanas, não meses.** *(Emanuel, 15/05/2026)* Projetos de IA precisam entregar valor em semanas para justificar o investimento — referência prática: 80% do valor de negócio em 6 semanas. Os capstones são reframed como entregas de 4–6 semanas, não como projetos de "trimestre".

---

## 3. Background técnico

### Skills fortes (já tem)
- Python diário (pandas, numpy, sklearn, lgbm)
- Modelos de ML (LGBM, RNNs, CNNs)
- Deep learning, alguma teoria de transformer/LLM
- Pipelines Kubeflow customizados
- Scala (ETL no Nubank)
- Git básico (+ uso ativo de Claude Code)
- SQL/SQLite

### Gap (o que estamos construindo)
- LLM APIs (nunca tinha chamado uma antes da jornada)
- Construir interfaces para não-técnicos
- Deploy de apps na internet
- LangChain, LangGraph, MCP
- Agentes, tool_use, RAG
- Arquitetura de dados para sistemas de IA (Seção 13)

---

## 4. Como as sessões funcionam

### Unidade de trabalho: a sessão

- **Duração:** ~30-45 min. Sessão curta o suficiente pra caber em qualquer dia.
- **Frequência:** pelo menos uma por dia. Múltiplas por dia quando o tempo permitir.
- **Horário:** flexível. Manhã antes do Nubank, almoço, noite — qualquer um.
- **Capítulo:** bloco temático com vários tópicos. Termina quando os tópicos foram dominados, não numa data.

### Como nomear o trabalho

Em vez de "Semana X, Dia Y", usamos **"Capítulo X · Sessão Y"** quando importa referenciar uma sessão específica (ex: nas notas, no report do Emanuel). A maior parte das sessões não precisa de nome — só o conteúdo importa.

### Regras que Claude sempre segue
- Explicar todo código que escreve — Misael não quer copiar/colar sem entender
- Uma pergunta de cada vez
- Corrigir erros de gramática em inglês naturalmente antes de responder
- Manter respostas claras e simples
- Quando Misael estiver travado, sugerir Claude Code no terminal
- **Sessões devem ser curtas e densas.** Se o material pede mais que ~45 min, dividir em duas sessões em vez de esticar uma

### Rituais que sobreviveram (versão enxuta)

- **Pre-question (antes de conceito novo):** Misael prevê como funciona, mesmo errado. O ato de gerar a hipótese cria âncora pra resposta correta.
- **Self-explanation (depois de Claude explicar):** Misael re-explica em suas palavras OU prediz o que muda se a linha X for modificada.
- **Mental prediction antes de rodar código:** "o que você acha que vai acontecer?"
- **Exercício no fim:** 1 a 3 exercícios, conforme tempo disponível na sessão. Os três níveis (fácil/médio/difícil) viram um menu, não obrigação.
  - Quando a sessão é longa e couber, o exercício *difícil* combina o conceito atual com um anterior (interleaving)

### Spacing & retrieval (em sessões, não semanas)

- **Não revisitar** um conceito na sessão imediatamente seguinte. O esquecimento é o que cria a memória ao recuperar.
- **Revisitar** ao abrir o próximo capítulo (~10-20 sessões depois) — recreate from memory primeiro, só consultar nota depois.
- **Revisitar novamente** uns dois capítulos à frente.
- **Sinal de revisão:** se o retrieval falhar, é onde a próxima semana deve investir.

### Correção de exercícios

Quando Misael erra num exercício, Claude pede pra ele refazer com pista mínima — não dá a solução direta.

---

## 5. Reporting — apresentação por capítulo para Emanuel

**Cadência (atualizada 21/05/2026):** o deck é entregue **quando um capítulo é concluído**, não mais toda sexta. Sem pressão de calendário — o gatilho é "Capítulo X fechado", não "é sexta". Quando o capítulo fechar, em qualquer dia da semana, o deck é montado em seguida.

**Formato:** slide deck (HTML ou .pptx). 5–10 slides, ~10-12 min de walkthrough. Sem cumprimento, sem terceira pessoa.

**Esqueleto recomendado:**
1. *Capa* — qual capítulo está sendo fechado e o tema central
2. *Progresso do capítulo* — bullets cobrindo os tópicos, links pra PRs/deploys
3. *Aprendizado principal* — um conceito que aterrissou no capítulo, com snippet/diagrama
4. *O que ficou shaky* — itens da auto-avaliação ("know cold / know shakily / forgot")
5. *Decisões e tradeoffs* — material pra futuros ADRs
6. *Métricas* (quando aplicável) — eval scores, latência, custo
7. *Próximo passo* — qual capítulo abre em seguida e por onde começa
8. *(Opcional)* — demo

A apresentação cobre **o capítulo inteiro**, não uma janela de tempo. Se o capítulo levou duas semanas ou seis, a entrega é a mesma.

**Backfill:** não é preciso refazer apresentações retroativas.

---

## 6. LinkedIn

- Frequência: 1 post por semana, sexta-feira (cadência própria, agora desacoplada do deck do Emanuel)
- Conteúdo: o conceito ou projeto principal da semana
- O post reusa material do slide "Aprendizado principal" — não é trabalho paralelo
- Sem framing de transição de carreira, sem mencionar Nubank, sem números de "semana X" — tom educativo, neutro

### Backfill em aberto
Capítulo 1 (Fundamentos) foi inteiro coberto sem posts. Candidatos fortes a posts retroativos:
- **RAG** (alto volume de busca, pdf-chat deployado)
- **tool_use / ReAct** (conceito menos conhecido, ângulo educativo bom)
- **LangChain** (quando usar framework vs raw API)

Um post de backfill por semana, intercalado com post da semana atual. Consistência > velocidade.

---

## 7. Setup & ambiente

- **Hardware:** Mac Mini M4 (16GB RAM, 256GB)
- **Editor:** Cursor
- **Python:** 3.11 via Homebrew
- **Virtual envs:** cada projeto tem seu próprio `py311env`, ativado com `source py311env/bin/activate`. Dentro do venv, usar `python` (não `python3.11`).
- **Claude Code:** instalado globalmente via npm, usado diariamente
- **GitHub:** luanmoura-aimanager
- **API key Anthropic:** em `~/.zshrc` como `ANTHROPIC_API_KEY`

### Pasta de trabalho
Todos os projetos e deliverables vivem em **`~/ai-projects/`**. Repos:
- `sql-agent/`
- `pdf-chat/`
- `langgraph-studio/`
- `mcp-studio/`
- Deliverables (decks, ADRs externos): mesmo nível.

---

## 8. Como Misael aprende

- Aprende fazendo — nada de tutorial ou curso, vai direto pro build
- Quer tudo explicado durante a construção — nunca só copia/cola
- Aprende rápido, animado com o material
- Comunicação direta, sem preâmbulo
- Usa Claude Code ativamente pra resolver bloqueios sozinho
- Retenção por exercício ativo (analogia: aprende sintetizador lendo o manual *enquanto* mexe no instrumento)
- Predição mental antes de rodar código ajuda na retenção

### Princípios de retenção aplicados
- **Retrieval ativo > revisão passiva.** Recriar de memória antes de consultar nota.
- **Spacing > imediato.** Não revisar logo após aprender.
- **Geração > recepção.** Prever como algo funciona antes de ouvir a explicação.
- **Auto-explicação > acknowledgment.** Re-explicar verifica entendimento; concordar não.
- **Metacognição > grinding.** Rastrear o que se sabe cold / shakily / forgot guia onde investir.

---

## 9. Estado atual

**Capítulo 3 — Production grade & integração enterprise** · em andamento. Cap 2 concluído em 17/05/2026.

### Coberto no Capítulo 3 (até agora)
- **API design — FastAPI:**
  - Interface FastAPI criada e documentada (PR #18, 18/05/2026)
  - Agente real wired no endpoint `/query` (PR #19, 19/05/2026)
  - `GET /health` (liveness) + error boundary com `HTTPException(500)` em `/query` (PR #20, mergeado em 21/05/2026)
- **Governança — auth:**
  - Bearer token auth via `Depends(verify_token)`, token esperado lido de `API_TOKEN` env var no startup (fail-fast). Testes manuais A/B/C confirmaram 200/401/422 (PR #21, 22/05/2026)
  - Fix do 422 → 401 quando header `Authorization` ausente: `Header(None)` + check explícito. Smoke test com TestClient nos 4 casos (sem header / scheme errado / token errado / token certo) → 401/401/401/200 (PR #22, 23/05/2026)
- **Security mini-opener — DoS / token abuse (23/05/2026):** abertura do tema de rate limit. Vetores estudados: burst, slowloris, token brute force, token stuffing. Decisão de arquitetura: limit por IP *antes* do auth (`60/min, 500/hora`) + limit por token *depois* do auth (`30/min, 200/hora`), via `slowapi` com storage in-memory.
- **Governança — rate limit IP (Sessão A do split):**
  - `SlowAPIMiddleware` com `default_limits=["60/minute", "500/hour"]`, `headers_enabled=True`, key por IP. `/health` exemptado. Smoke test (TestClient, 4 casos) — incluindo burst com token inválido devolvendo 429 (prova que limit aplica antes do auth → brute force barrado). PR #23 (23/05/2026).
  - **Aprendizado-chave (não-óbvio):** `@limiter.limit` decorator NÃO roda antes do `Depends(verify_token)`. FastAPI resolve TODOS os Depends antes de chamar a função, e o decorator embrulha a função — então decorator roda *depois* do auth. Pra rate limit defender contra brute force, **tem que ser middleware** (que roda fora do ciclo de Depends). O smoke test pegou esse erro de modelo mental.
- **Side-mission técnica:** keyring do macOS travando `pip install` / `import` resolvido com `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring` + venv recriado. Documentado em memória.
- **Governança — rate limit por token (Sessão B do split):**
  - `@token_limiter.limit("30/minute;200/hour")` em `/query` com `key_func=get_token_key` extraindo o Bearer token do header `Authorization`. Roda depois do `Depends(verify_token)` — só tokens válidos consomem quota. PR #25 (25/05/2026).
  - **Aprendizado-chave (não-óbvio):** usar o mesmo `Limiter` para o decorator e o middleware desliga o IP layer para a rota — `SlowAPIMiddleware._should_exempt()` pula rotas que estão em `limiter._route_limits`. Solução: segundo `Limiter` separado (`token_limiter`) para o decorator, mantendo `/query` fora do `limiter._route_limits` e preservando o IP check. Documentado no PR #25.
  - 4 testes cobrindo: token isolado (30 reqs → 200, 31º → 429 + `retry-after`), quotas separadas por token, e coexistência dos dois layers (IP counter e token counter independentes).
- **Side-mission fechada — X-Forwarded-For trust model (27/05/2026):**
  - `get_client_ip` custom substituindo `get_remote_address`: respeita XFF apenas quando `request.client.host` está em `TRUSTED_PROXIES` (env var, lista de IPs separados por vírgula). Vazio = comportamento antigo (peer IP). Não usa `slowapi.util.get_ipaddr` porque ele lê XFF sem trust check (qualquer cliente burlaria a quota variando o header).
  - 4 testes: XFF ignorado sem `TRUSTED_PROXIES`; XFF respeitado quando peer trusted; leftmost IP da cadeia (`"client, proxy1, proxy2"`); fallback ao peer em header malformado. TODO(deploy) do XFF removido de `main.py`.
- **Governança — structured logging (parte 1, 27/05/2026):**
  - Design travado em 5 decisões: stdlib `logging` + `JsonFormatter` custom; categoria B (PII) com hash em INFO e texto em DEBUG (por campo: `question` hash, `sql_generated` hash+len, `answer` só `len`); sampling 100%; destino stdout (12-factor); defesa de log injection via `json.dumps`. Razões em `logging_config.py`.
  - Implementado: `logging_config.py` (JsonFormatter, `hash_text`, `setup_logging`, `request_id_var` ContextVar); middleware `@app.middleware("http")` no `main.py` gerando UUID4 por request, propagando via ContextVar e expondo no header `X-Request-ID`; log estruturado em `/query` com `q_hash`, `answer_len`, `history_len`, `latency_ms`, `status` em INFO + `question_text`/`answer_text` em DEBUG.
  - 11 testes (`test_structured_logging.py`): hash determinístico, JSON válido, **log injection** (`\n` + JSON forjado vira uma única linha), request_id UUID4 e propagação ContextVar → header, categoria B (INFO sem `question_text`, DEBUG com).
  - **Decisão tática:** `X-Request-ID` é sempre gerado server-side; cliente não pode setar (vetor de log forge). Comentado em `main.py`.
  - **Aprendizado-chave (não-óbvio):** `ContextVar` em FastAPI requer `reset(token)` no `finally` do middleware mesmo em async — sem isso o valor "vaza" pra fora do scope dentro da mesma task asyncio (entre tasks não vaza por causa do copy-on-write, mas dentro vaza). Sem `reset`, logs pós-request vêem o id da última request.
- **Pendente parte 2 (próxima sessão):** cost attribution — callback do `ChatAnthropic` capturando `input_tokens`/`output_tokens` do `response_metadata['usage']`, exposto em USD por chamada no log; também tem TODO(security) no `query_failed` (vaza `str(e)` no detail da response — categoria C).
- **Próximo (depois de cost attribution):** Deployment — Docker, CI/CD, secrets. Encerra a camada de governança.

### Coberto no Capítulo 2
- MCP — protocolo, servidor, integração no `sql-agent` (sqlite-mcp-server)
- Evaluation — eval harness, regex methods, llm_judge, calibração 30-case, Cohen's κ, ADR-003 (router scope reframe)
- Data Lake × Warehouse × Lakehouse — opener de RAG de produção (17/05/2026, know cold)
- RAG de produção — chunking strategy (overlap, unidade de medida), hybrid search (BM25 + vetorial, RRF), reranking (cross-encoder vs bi-encoder) ✅ (17/05/2026)
- ELT × ETL + dbt mental model — diferença de onde transforma, `ref()`, ambientes, governança ✅ (17/05/2026)

### Saiu do Cap 2 (decisão de 15/05/2026, mentoria)
- **Prompt engineering como tópico isolado** → vira *on-demand*. Entra quando um projeto pedir (few-shot, CoT, structured outputs aprendidos contra um caso real).
- **Mini-capstone "acadêmico" do Cap 2** (eval antes/depois) → suprimido. O lugar natural pra mostrar pensamento de sistemas agora é **dentro do primeiro projeto do Cap 3**, com integração real, não num exercício isolado.

### Conceito mais recente que ainda está shaky
- **Critério não-observável em LLM-as-judge** — quando o critério pede o que o juiz não pode ver. Apareceu no caso `revenue_per_category`. Vale uma revisita on-demand quando voltar a mexer em eval.

### Side missions pendentes
- ADR para fechar Layer 4 do sql-agent: read-only SQLite connection × `sqlglot` parser para stacked queries
- Backfill LinkedIn dos tópicos do Capítulo 1
- Adicionar header `WWW-Authenticate: Bearer` nas respostas 401 do `/query` (RFC 7235) — vale quando aparecer cliente automatizado consumindo a API
- Migrar storage do rate limit (slowapi) de in-memory → Redis quando entrar em deployment multi-instância (cai naturalmente no tópico de Deployment do Cap 3)

---

## 10. Capítulo 1 — Fundamentos *(concluído)*

**Pergunta-guia:** como o LLM pode raciocinar sobre dados e ferramentas externas?

### Tópicos cobertos
- **RAG do zero** — pypdf, ChromaDB, Claude API → `pdf-chat`
- **Native tool_use** — schema injection, ReAct loop manual → primeira versão do `sql-agent`
- **LangChain** — `@tool` decorator, `create_react_agent`, memória de conversa
- **LangGraph** — StateGraph, nodes, edges, router pattern

### Mini-capstone
Pequeno agente from scratch combinando LangGraph (W4) + @tool (W3) + native tool_use (W2) + ChromaDB (W1). Realizado.

---

## 11. Capítulo 2 — Pensamento de sistemas *(concluído)*

**Pergunta-guia:** como passar de "isso funciona" para "isso é mensurável e robusto"?

### Tópicos
- **MCP** — protocolo, servidores, integrações reais ✅
  - Reservar tempo pra *desenhar* um servidor MCP, não só consumir (lente de arquiteto: granularidade, versionamento, auth model)
- **Evaluation** — LLM-as-judge, datasets, regressão ✅
- **RAG de produção** — chunking strategy, hybrid search, reranking ✅ *(concluído 17/05/2026)*
  - **[Data Architecture +]** opener: Data Lake × Warehouse × Lakehouse ✅ *(concluído 17/05/2026)*
  - **[Data Architecture +]** Event-driven ingestion para LLM systems — conceitos Kafka aplicados a knowledge base *(realocado para Cap 3 quando fizer sentido no contexto de um projeto real)*

### Itens removidos do Cap 2 (mentoria 15/05/2026)
- ~~Prompt engineering como tópico dedicado~~ → vira material *on-demand* dentro de projetos do Cap 3 (few-shot, CoT, structured outputs aplicados quando o caso real pedir)
- ~~Mini-capstone do capítulo~~ → o teste real de "pensamento de sistemas" passa a ser o **primeiro projeto integrado do Cap 3**, não um exercício acadêmico em cima de `pdf-chat`/`sql-agent`
- ~~[Data Architecture +] Schema-on-read × schema-on-write~~ no opener de Prompt engineering → realocar pra Cap 3 (API design) quando fizer sentido

---

## 12. Capítulo 3 — Production grade & integração enterprise

**Veículo único:** `sql-agent`. Toda a vertical do Cap 3 (API, governança, deployment, observabilidade, camada de interface) acontece dentro desse repo. Nada de pular para outros projetos no meio do capítulo — regra estabelecida em 21/05/2026.

**Pergunta-guia:** como esse agente sobrevive ao contato com produção **e chega no fluxo de trabalho do usuário sem que ele tenha que sair pra usar**?

### Framing da mentoria (Emanuel, 15/05/2026)

A plataforma de IA enterprise tem **três camadas**, e todo agente de produção precisa lidar com as três:

1. **Camada de desenvolvimento** — onde o agente é construído e roda. *(Databricks, LangGraph, Python, FastAPI.)*
2. **Camada de governança** — o que torna o serviço utilizável por outros: API management, autenticação, telemetria, rate limiting, cost attribution. *(Sem essa camada, o agente é um script; com ela, é um serviço.)*
3. **Camada de interface com o usuário** — onde o agente *chega* no fluxo de trabalho da pessoa: Slack, Teams, Outlook, Jira. **Não é uma UI nova; é integração no que o usuário já usa.**

**MCP é a espinha de padronização** entre as camadas: o serviço fica disponível em qualquer lugar (Slack bot, agente em Outlook, REPL interno) porque foi exposto como MCP server e cada surface consome o mesmo contrato.

### Princípios operacionais do Cap 3

- **Users where they are.** *(Emanuel)* "O maior problema desse tipo de produto é o cara ter que sair do fluxo dele de trabalho e acessar outra plataforma." Implicação: o primeiro projeto do Cap 3 não pode ser um Streamlit standalone — tem que entrar num surface existente (Slack/Teams/Outlook ou similar). Onde exatamente, decide quando chegar lá.
- **Entrega em semanas, não meses.** O capstone do Cap 3 é um sprint de **4–6 semanas** que entrega 80% do valor. Não é um projeto de "trimestre".
- **Theory on-demand.** Conceitos teóricos (prompt engineering avançado, tradeoffs de chunking, etc) entram quando o projeto pede, não como tópico isolado.

### Thread de segurança (mantida — atravessa todo o capítulo)
Ao iniciar cada tópico, ~30 min de "Security mini-opener":
- Prompt injection — direto e indireto, padrões de defesa
- Data exfiltration — dados sensíveis vazando via prompts, logs, tool outputs
- Tool permission model — least privilege para agentes, classes perigosas, human-in-the-loop
- Auditability — o que logar, o que nunca logar, tornar o agente explicável post hoc

### Tópicos

- **API design (camada de desenvolvimento)** — FastAPI, streaming, async, versioning. Expor o `sql-agent` como API real, não só como script Streamlit.
  - **[Data Architecture +]** Multi-source ingestion design — pipeline pequeno (REST + S3 + DB) alimentando LLM (hands-on)
  - **[Data Architecture +]** ELT × ETL + dbt mental model
  - **[Data Architecture +]** Schema-on-read × schema-on-write (realocado do Cap 2)
- **Camada de governança** — API gateway básico, auth (token/OAuth), rate limiting, cost attribution por chamada, telemetria estruturada. Aqui é onde o agente "vira serviço".
- **Deployment** — Docker, CI/CD, env config, secrets
- **Observabilidade** — tracing, cost tracking, latência, LangSmith
  - **[Clayton callback]** usar Clayton como caso de referência pra observabilidade
- **Camada de interface (users where they are)** — pelo menos uma integração real numa surface existente. Candidatos: Slack bot, Teams agent, agente em Outlook via Microsoft 365, comando em Jira. Princípio: o usuário não abre URL nova.

### Capstone I (reframed — sprint de 4–6 semanas)

Um agente útil, deployado, **acessado por um usuário real dentro do fluxo dele** (Slack/Teams/Outlook), com:
- API exposta com auth e rate limit
- Telemetria mínima (cost, latência, taxa de erro)
- Pelo menos uma defesa de segurança implementada (não só listada)
- Eval leve antes/depois pra mostrar que mudou pra melhor

Deliverable principal: o agente em uso, não um relatório sobre o agente.

---

## 13. Capítulo 4 — Padrões avançados

### Tópicos
- **Quando *não* fine-tunar** — o mercado se moveu pra prompting + RAG + long context. ~1 sessão em LoRA pra não ser caixa preta; resto em DSPy, prompt optimization, context engineering. Decisão de arquiteto: "fine-tune ou não, e por quê"
- **Multi-agent** — supervisor, worker, handoffs, shared memory
  - **[Clayton callback]** Clayton já roda um router que escolhe skill sets por incidente — afiar esse padrão
- **Custo & latência** — caching, model routing, prompt compression
- **Capstone II** — portfolio-ready, multi-agent, produção

---

## 14. Capítulo 5 — Data platform para IA

**Objetivo:** converter credencial de DE existente (Scala ETL, Databricks, S3) em *fluência arquitetural*.

### Tópicos
- **Stack moderno** — dbt em profundidade, orquestração (Dagster ou Airflow — escolher um), data contracts
  - Deliverable: pipeline dbt preparando dados para LLM agent
- **Vector infrastructure em escala** — pgvector × managed (Pinecone/Weaviate), hybrid search, embedding lifecycle
  - Deliverable: ADR comparando três vector DBs para hipotético caso de 10M docs
- **Event-driven & streaming para IA** — Kafka/CDC, RAG com atualização contínua
  - Deliverable: design (sem implementar Kafka) de como manter knowledge base de 10k docs fresca sob updates diários
- **Feature stores & embedding stores** — Feast, offline/online consistency, *quando* (e quando não) usar
  - Deliverable: decisão escrita sobre se Clayton se beneficiaria de feature store

---

## 15. Capítulo 6 — Cloud AI & integração enterprise

**Princípio:** profundidade em UM cloud (recomendado AWS — Nubank é AWS-heavy, reusa contexto).

### Tópicos
- **AWS Bedrock end-to-end** — Knowledge Bases, Agents, Guardrails. Managed × self-hosted LangGraph
  - Deliverable: reimplementar versão do `sql-agent` no Bedrock + ADR "Bedrock × LangGraph custom: quando cada"
- **Identidade & segurança enterprise** — IAM, VPC endpoints, SSO, OAuth, secrets
  - Deliverable: design doc de acesso endurecido para agente interno hipotético
- **API gateway, service mesh, multi-tenancy** — um agente, 5 tenants, rate limiting, cost attribution, isolation
  - Deliverable: diagrama multi-tenant + análise de tradeoffs
- **Cost & FinOps para IA** — caching tiers, model routing, reserved capacity
  - Deliverable: modelo de custo (planilha) pra workload realista (1M chamadas/mês, mixed traffic)

---

## 16. Capítulo 7 — Skills de arquiteto

**Objetivo:** praticar os *artefatos* que arquitetos produzem.

### Tópicos
- **AI governance, red teaming, compliance** — LGPD/GDPR pra sistemas IA, prompt injection em escala
  - Deliverable: red team em Clayton + relatório de findings
- **Reference architectures & ADRs** — C4 diagrams, decision records, tradeoff docs
  - Deliverable: 3 ADRs retroativos pras decisões já feitas (Clayton, sql-agent, pdf-chat)
- **System design pra IA** — estilo entrevista de arquiteto. "Desenhe sistema de suporte AI pra 1M users/mês"
  - Deliverable: 2 writeups em formato architect-interview
- **Capstone Solutions Architect** — brief de negócio (fictício ou real da rede), reference architecture completa (ADR, C4, capacity/cost), POC do caminho crítico
  - Deliverable: *o* artefato de portfólio para roles arquitetura

---

## 17. Projetos

> **Regra de projeto por capítulo (21/05/2026):** um projeto por capítulo, para evitar context-switch. Cap 3 = `sql-agent` exclusivamente. Cap 4 em diante: decidir qual projeto será o novo veículo ao abrir o capítulo (candidatos: greenfield, `pdf-chat` revisitado, ou `Clayton` como caso de produção).

### `pdf-chat`
- Upload de PDF + chat via RAG
- Streamlit, Anthropic API, pypdf, ChromaDB
- https://github.com/luanmoura-aimanager/pdf-chat
- **Status:** Deployado. Em standby durante o Cap 3.

### `sql-agent` *(veículo único do Cap 3)*
- Perguntas em linguagem natural sobre DB SQLite
- Streamlit, Anthropic API (raw tool_use), LangChain, LangGraph, MCP, eval harness, FastAPI
- https://github.com/luanmoura-aimanager/sql-agent
- https://sql-agent-2026-brazil.streamlit.app
- **Status:** Eval honesto em 8/8 após ADR-003 (router scope reframe). Calibração humana 28/30 (κ=0.526). FastAPI wired com health endpoint + error handling (PR pendente). Próximos gaps no Cap 3: governança (auth/rate limit), camada de interface (Slack/Teams/Outlook), observabilidade. Side mission: ADR de Layer 4 (stacked queries).

### `langgraph-studio`
- Sandbox de aprendizado pra LangGraph antes de integrar nos projetos reais
- https://github.com/luanmoura-aimanager/langgraph-studio
- **Status:** ativo (revisitado quando precisa testar isolado)

### `mcp-studio`
- Sandbox de aprendizado pra MCP
- **Status:** usado para o servidor que rodou no `sql-agent`

### `Clayton` *(produção, Nubank)*
- Agente autônomo de resposta a incidentes de ML — Slack bot → LangGraph → integra Databricks, Jira, GitHub
- Vencedor de hackathon interno
- Será revisitado nos Capítulos 3, 4, 7 como caso de produção

---

## 18. Conceitos consolidados

Lista do que já está sólido (pode ser revisitado em retrieval):

- **RAG:** chunk → embed → ChromaDB → recuperar → mandar pro Claude
- **tool_use:** o LLM pede via `tool_call`, código executa, resultado volta. O LLM nunca toca o dado direto.
- **ReAct loop:** while → pensa → chama tool → recebe → pensa de novo → termina
- **@tool decorator (LangChain):** a docstring vira a description que o LLM lê
- **create_react_agent:** substitui o while loop manual
- **Memória de conversa:** `chat_history` injetado a cada `invoke`
- **Virtual envs:** isola dependências, `py311env` por projeto
- **Git:** branch → code → PR → merge
- **Claude Code:** AI pair programmer no terminal — lê, escreve, git, debuga
- **Streamlit session_state:** persiste entre reruns
- **Deploy Streamlit Cloud:** conecta GitHub repo, adiciona secret, ganha URL pública
- **requirements.txt:** sempre `>=` pra evitar conflito no deploy
- **StateGraph (LangGraph):** builder do grafo, recebe tipo do State
- **State (TypedDict):** dicionário compartilhado, merge automático
- **Nodes:** funções puras que recebem State e retornam só os campos que mudaram
- **Edges:** definem ordem; `conditional_edges` permitem roteamento
- **AIMessage / SystemMessage / HumanMessage:** sempre passar lista, não string
- **LLM output sanitization:** `.strip().upper()` + `in` checks, não `==`
- **MCP:** protocolo cliente/servidor para tools, stdio + JSON-RPC. Guard mora no servidor, sobrevive a troca de framework do agente.
- **Eval como disciplina:** casos + critérios + execução repetível. Regex pra determinístico, LLM-as-judge pra flexível-mas-calibrado.
- **LLM-as-judge com chain-of-thought:** força `reasoning` antes de `passed`; prefill `{` + strip de markdown fence
- **Cohen's κ:** mede concordância acima do acaso. Tem paradoxo: com distribuição muito desigual, κ pode cair mesmo com mais acordo observado.
- **Defesa em camadas:** router → interface limitada → guard no servidor → DB read-only (Layer 4 ainda em aberto no sql-agent)

---

## 19. Data architecture — contexto

### Por que entrou no roadmap
Sinal de mercado (abril/2026): vagas de AI Engineer buscam quem também tem skill de DE/arquitetura de dados. Misael tem prática (Scala ETL no Nubank, Databricks, S3) mas falta vocabulário e experiência de design.

### Resultado do diagnóstico (2 de abril de 2026)
| Conceito | Status |
|---|---|
| Batch × streaming ingestion | ✅ |
| Data partitioning | ✅ |
| Data Lake × Warehouse | 🟡 (direção certa, sharpen) |
| ETL × ELT | 🟡 (conhece ETL, nunca viu ELT) |
| Design de pipeline LLM | 🟡 (faltou ângulo RAG) |
| Schema-on-read × schema-on-write | ❌ |
| Event-driven architecture | ❌ |
| Multi-source pipeline design | ❌ |

### Onde os 5 conceitos novos entram
- **Data Lake × Warehouse × Lakehouse** → opener de RAG de produção (Cap 2)
- **Schema-on-read × schema-on-write** → realocado pra Cap 3 (API design), depois que prompt engineering saiu do Cap 2 em 15/05/2026
- **ELT × ETL + dbt mental model** → opener de API design (Cap 3)
- **Multi-source ingestion pipeline** → hands-on em API design (Cap 3)
- **Event-driven ingestion para LLM systems** → hands-on em RAG de produção (Cap 2)

---

## 20. Histórico de mudanças metodológicas

### 22 de abril de 2026 — extensão da jornada
Original: 16 semanas → AI Engineer. Estendida pra ~28 semanas incluindo trilha de Solutions Architect (Phases 5-7 originais → Capítulos 5-7 atuais).

Três ajustes retroativos:
1. **Cap 2 (MCP)** ganhou tempo dedicado a *desenhar* um servidor MCP, não só consumir.
2. **Cap 3** ganhou Security mini-openers a cada tópico.
3. **Cap 4** reframed: de "Fine-tuning" para "Quando *não* fine-tunar".

### 25 de abril de 2026 — refinamento da metodologia
Após revisão da literatura (deliberate practice, spacing, interleaving), aplicamos:
1. Mecanismo de retrieval espaçado (Monday opener, antes — agora reframed como retrieval ao abrir o próximo capítulo).
2. Interleaving — o exercício *difícil*, quando feito, combina conceito atual com anterior.
3. Self-explanation depois de explicação do Claude.
4. Pre-questioning antes de conceito novo.
5. Metacognição — inventário "know cold / know shakily / forgot".

### 11 de maio de 2026 — mudança no reporting
Emanuel trocou daily WhatsApp report ("Report — Semana X, Dia Y") por **uma apresentação semanal** entregue na sexta. Formato em Seção 5.

### 13 de maio de 2026 — capítulos e sessões
- **Saiu:** "Semana X, Dia Y", prazos por data ("by July 2026"), cronograma fixo
- **Entrou:** "Capítulo X · Sessão Y" como unidade flexível, sessões de 30-45 min, múltiplas por dia OK, disciplina diária no lugar de meta temporal
- **Razão:** as sessões estavam ficando longas e maçantes; a meta temporal pressionava sem agregar
- **O que NÃO mudou (em 15/05):** o currículo (Capítulos 1-7), a cadência do report pro Emanuel *(mudada depois em 21/05)*, o post semanal no LinkedIn, os rituais de aprendizado, os projetos

### 21 de maio de 2026 — cadência por capítulo + um projeto por capítulo
- **Saiu:**
  - Deck semanal de sexta pro Emanuel
  - Liberdade de pular entre projetos (`sql-agent`, `pdf-chat`, etc.) dentro do mesmo capítulo
- **Entrou:**
  - **Deck por capítulo:** o gatilho passa de "é sexta" para "Capítulo X foi fechado". Ver Seção 5.
  - **Um projeto por capítulo:** Cap 3 inteiro dentro do `sql-agent`. Trocar de projeto só ao virar capítulo. Cap 4+: decidir o novo veículo ao abrir o capítulo. Ver Seção 17.
- **Razão:** cadência semanal pressionava entrega artificial mesmo sem o capítulo ter fechado; o valor real do deck é sintetizar um bloco temático completo. Pular entre projetos no mesmo capítulo dispersa progresso e cria context-switch desnecessário — profundidade > variedade (Princípio 2).
- **O que NÃO mudou:** o currículo (Capítulos 1-7), os rituais de aprendizado, o post semanal no LinkedIn, a thread de segurança no Cap 3.

### 15 de maio de 2026 — pivot prático (mentoria com Emanuel)
- **Saiu:**
  - Aprofundamento teórico em eval frameworks como tópico isolado (já tinha se prolongado)
  - Prompt engineering como tópico dedicado no Cap 2
  - Mini-capstone "acadêmico" do Cap 2 (eval antes/depois em `pdf-chat`/`sql-agent`)
- **Entrou:**
  - **Direção > detalhe; teoria on-demand** como 4º princípio (Seção 2). Analogia do Emanuel: aprende a tocar primeiro, teoria musical depois.
  - **Ciclo de entrega curto: semanas, não meses** como 5º princípio. Capstones reframed como sprints de 4–6 semanas, mirando 80% do valor.
  - **Cap 3 reframed** com três camadas de plataforma enterprise (Dev / Governance / UI), MCP como spine de padronização, e princípio "users where they are" (integração em Slack/Teams/Outlook em vez de UI standalone).
- **Razão:** a curva de retorno do aprofundamento teórico estava caindo; o gap real é construir produto que entra no fluxo do usuário e sobrevive a uma camada de governança. Mercado de AI Engineer remunera quem entrega isso, não quem domina a teoria de eval.
- **O que NÃO mudou:** o currículo (Capítulos 1-7) na ordem geral, a cadência do report pro Emanuel, os rituais de aprendizado, a thread de segurança no Cap 3, os Data Architecture +, os capítulos 4-7.
- **Decidir quando chegar lá:** qual surface concreta hospeda o primeiro projeto do Cap 3 (Slack? Teams? Outlook? Jira?).

---

## 21. Pacing — duas opções (sem prazo agora)

A opção B continua sendo o padrão, mas sem data.

### Opção A — Contínuo
Estudar Capítulos 5-7 enquanto já estiver no role de AI Engineer.
**Risco:** pouco tempo de amadurecimento no role antes de pular pra Architect.

### Opção B — Estagiado *(padrão)*
- Conseguir o role de AI Engineer
- Primeiros meses no novo role: Capítulo 5 (data platform) *enquanto já usa no trabalho*
- Meses seguintes: Capítulos 6-7 (cloud enterprise + architect skills), agora com contexto real pra calibrar
- **Vantagem:** architect é role melhor aprendido dentro de organização. Metade do trabalho é navegação política, stakeholder management, restrições reais.

---

## 22. Como Claude deve ler este documento

- Sempre antes da primeira resposta da sessão
- Quando Misael disser "vamos começar" ou "here we go": perguntar se está no Mac Mini pronto pra começar
- Em sessão: seguir os rituais da Seção 4 conforme o tipo de tarefa (revisão / conceito novo / projeto)
- **Não tentar fazer cabê numa sessão mais do que cabe.** Se vai estourar 45 min, propor dividir
- Sempre que possível, conectar conceito novo a experiência prévia de DS de Misael (AUC/KS como analogia a métricas abertas/fechadas, etc) — é uma ponte de aprendizado consistente e eficaz
- **Aplicar os princípios 4 e 5 (Seção 2) ativamente:** se um tópico teórico aparece sem projeto concreto puxando, parar e perguntar "isso entra agora ou fica on-demand?". Se um capstone começa a passar de 6 semanas, o problema é escopo — propor cortar.
- **Pensar todo projeto do Cap 3+ em três camadas:** dev / governance / UI. Sempre perguntar "em que surface o usuário consome?" antes de aceitar UI standalone.
