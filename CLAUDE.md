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

## Coletores de Assembleias estaduais (novo estado)

Um `scripts/coletar_estadual_<uf>.py` por UF fora do SAPL, com um job próprio na matriz `estaduais` de `.github/workflows/atualizar.yml` (um job lento não segura os outros). Use `estaduais_comum.py` (`sessao()`, `salvar`, `ler`, `avisar`, `ligar_nomes`) e grave em `dados/estaduais/<UF>/`. O que importa para o tempo de execução:

- **Nunca refaça tudo todo dia.** O CI começa de um checkout limpo e só o que está commitado em `dados/estaduais/` vale como cache. Antes de escrever o coletor, meça uma coleta do zero e uma com cache (`time` em Python, contra a API real) e anote o resultado no `CHANGELOG.md`.
- **Anos encerrados** (`comum.ano_encerrado`: `ano < hoje.year - 1` com arquivo existente) não são baixados de novo. Dado mensal (verba, remuneração, diárias): só os meses que faltam no arquivo e os `comum.meses_recentes(hoje, MESES_RECENTES)` são relidos; o resto vem do arquivo anterior (guarde `mes` em cada item).
- **Proposições: leitura incremental.** Procure na API uma ordenação ou filtro por data de alteração (ex.: MG tem `ord=3`, por `dataUltimaAcao`; RN lista da mais nova para a mais antiga). Leia só até a data da coleta anterior (com 1 dia de folga) e junte com `materias_<ano>.json`. Sem isso, guarde no arquivo anual `vistas` ({chave: dia em que o detalhe foi lido}, inclusive do que não é de deputado, como na BA) e releia o ano corrente de forma escalonada (`zlib.crc32(chave) % N`), nunca tudo no mesmo dia.
- **Releitura completa de segurança** a cada `RENOVAR_COMPLETA_DIAS` (14): guarde `completaEm` no arquivo e faça a completa também quando faltar o arquivo de algum ano. O incremental não vê o que mudou sem alterar o campo de ordenação (ex.: arquivamentos no RN); isso entra na completa.
- **Respeite o ritmo da fonte.** Pausa e conexões simultâneas pedidas pela API (`CONEXOES_POR_HOST` e `PAUSA`); não paralelize além disso, o bloqueio costuma ser sem aviso.
- **Prazo.** O job tem `ESTADUAIS_PRAZO_MIN` (25 min): o coletor guarda o que já leu e termina. Grave o arquivo ao fim de cada etapa (ano, deputado), para que um prazo esgotado não perca o que já foi lido, e faça cada etapa falhar com `comum.avisar` sem derrubar as outras.
- **Teste offline** em `tests/test_coletar_estadual_<uf>.py`, incluindo o caminho incremental (lê só o novo, junta com o guardado, completa velha lê tudo) e uma amostra real em `tests/fixtures/contratos/` (`CONTRATOS` no coletor). Todo `monkeypatch` precisa cobrir a função que o código realmente chama (na BA, `baixar_ckan` e não `baixar`), senão o teste vai à internet.
