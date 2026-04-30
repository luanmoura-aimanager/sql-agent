# ADR-001: Adopt MCP for SQL tool exposure in sql-agent

## Status
Accepted (2026-04-29)

## Contexto
No estado anterior tínhamos um app com agente que acessa um banco de dados com tools hardcoded no código do próprio app, tornando limitado o acesso ao banco por outros agentes externos ou outras aplicações — cada um teria que reimplementar seu próprio set de tools para acessar o mesmo recurso.

## Decisão
Criar um servidor MCP standalone que expõe as tools necessárias para responder perguntas sobre o banco (`get_schema` e `run_query`), consumido pelo sql-agent via transporte stdio.

## Alternativas consideradas
- **Manter as tools diretamente no `app.py` (status quo):** descartado — tools ficam acopladas ao app, sem reuso.
- **MCP via stdio (escolhido):** mais simples e direto para esse caso, e abre acesso a outros agentes e apps que queiram se conectar ao mesmo banco.
- **Outras alternativas (REST, gRPC, MCP via HTTP/SSE):** existem e seriam relevantes em cenários multi-máquina ou multi-tenant, mas precisam ser estudadas mais a fundo antes de adoção.

## Consequências

**Positivas:**
- Outros agentes (ex: Claude Desktop, Clayton) podem consumir o mesmo servidor MCP sem nenhuma mudança no servidor.
- Schema discovery dinâmica: o agente descobre o banco em runtime via `get_schema`, em vez de receber o schema mastigado no system prompt.
- Trust boundary explícita: o guard de segurança vive no servidor, na fronteira correta, e não espalhado em cada cliente.

**Negativas:**
- O agente precisa de duas chamadas MCP por pergunta SQL (uma para o schema, outra para a query) — latência maior que import direto.
- Sistema agora tem dois processos (app + servidor MCP); debug fica mais espalhado.
- Deploy precisa garantir que o servidor MCP esteja no path e seja executável (cenário visto no Dia 4 — pasta `mcp/` que não tinha sido versionada inicialmente).

## Limitações conhecidas
- O guard SELECT-only é heurístico de string e vulnerável a stacked queries (`SELECT ...; DROP ...`) e comentários SQL. Em produção, a melhor solução é ter medidas de segurança diretamente no banco — por exemplo, conexão SQLite read-only ou parser SQL real (sqlglot).
