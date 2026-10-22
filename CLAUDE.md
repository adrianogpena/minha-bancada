# Minha Bancada

Site estático (GitHub Pages) com os políticos do Brasil. Scripts Python coletam dados (TSE, Câmara, Senado) e geram `site/dados/`; o front é HTML/JS puro em `site/`. Visão geral e fluxo de dados: `README.md`.

## Comandos

```bash
pip install -r requirements-dev.txt   # já roda sozinho no início das sessões na nuvem
python -m pytest -q                   # testes Python, offline, poucos segundos
node --test tests/js/app.test.js      # testes de site/assets/app.js
node --test tests/e2e/fumaca.test.js  # fumaça no navegador (Playwright + Chromium) sobre dados mínimos gerados
python scripts/gerar.py               # gera site/dados/ a partir de dados/
python -m http.server 8000 -d site    # servir o site local
```

Não há build nem linter de código. O CI (`.github/workflows/testes.yml`) roda os testes acima (o de navegador num job próprio) e o `actionlint` nos workflows.

## Estrutura

- `scripts/coletar*.py`: um coletor por fonte; `gerar*.py` montam os JSON do site; `historico.py`, `feeds.py`, `resumo_email.py` rodam após a coleta diária.
- `dados/`: cache bruto e histórico versionado (~270 MB). Evite `grep`/`find` amplos aqui; busque em `scripts/`, `tests/` e `site/*.html|assets`.
- `tests/fixtures/contratos/`: respostas reais reduzidas das APIs; os testes rodam os coletores contra elas.
- `site/dados/`, `dados/deputados/` etc. são gerados e ficam no `.gitignore`.

## Convenções

- Texto, comentários, commits e mensagens em português.
- Endpoint novo: registrar em `ENDPOINTS.md` e o conjunto no `CHANGELOG.md`. Ideias pendentes: `FUTURAS_IMPLEMENTACOES.md`.
- Testes nunca acessam a internet; simule a resposta no formato real da API. Se mudar um coletor por causa de mudança na API, regrave amostras com `python scripts/contrato_apis.py --gravar <nome>`.
- Commits de dados diários (`Dados atualizados em ...`, `Histórico diário ...`) vêm do Actions; não edite `dados/` à mão.
- Não crie PR sem pedido; desenvolva na branch designada da sessão.
