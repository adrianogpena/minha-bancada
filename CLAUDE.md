# Minha Bancada

Site estático (GitHub Pages) com os políticos do Brasil. Scripts Python coletam dados (TSE, Câmara, Senado, Assembleias) e geram `site/dados/`; o front é HTML/JS puro em `site/`. Visão geral e fluxo: `README.md`.

## Comandos

```bash
pip install -r requirements-dev.txt   # roda sozinho no início das sessões na nuvem
python -m pytest -q                   # Python, offline, poucos segundos
node --test tests/js/app.test.js      # módulos de site/assets/js
node --test tests/e2e/fumaca.test.js  # fumaça no navegador (Playwright + Chromium) sobre dados mínimos (tests/e2e/preparar_site.py)
python scripts/gerar.py               # gera site/dados/ a partir de dados/
python -m http.server 8000 -d site    # servir local
```

Sem build nem linter. CI (`.github/workflows/testes.yml`): pytest + teste JS, fumaça no navegador (job próprio) e `actionlint` nos workflows. Os testes não rodam na master, só em branch/PR.

## Estrutura

- `scripts/coletar*.py`: um coletor por fonte. `gerar*.py`, `identidades.py`, `mandatos.py`, `candidaturas.py`, `fornecedores.py`, `cadastro_proposicoes.py` montam os JSON do site, todos chamados por `gerar.py`, sem internet. `historico.py`, `feeds.py`, `resumo_email.py` rodam após a coleta diária.
- `dados/`: cache bruto e histórico versionado (~270 MB). Não use `grep`/`find` amplos aqui; busque em `scripts/`, `tests/`, `site/*.html` e `site/assets`.
- `site/dados/` e `dados/deputados/` etc. são gerados e estão no `.gitignore`. Núcleo normalizado em `site/dados/nucleo/` (pessoas, partidos, ligacoes, mandatos, fornecedores, candidaturas/, disputas/).
- `tests/fixtures/contratos/`: respostas reais reduzidas das APIs; os testes rodam os coletores contra elas.

## Convenções

- Texto, comentários, commits e mensagens em português.
- Endpoint novo: registrar em `ENDPOINTS.md` e o conjunto no `CHANGELOG.md` (`tests/test_endpoints_doc.py` exige todo host externo consultado em `ENDPOINTS.md`). Ideias pendentes: `FUTURAS_IMPLEMENTACOES.md`.
- Testes nunca acessam a internet; simule a resposta no formato real da API. Mudou um coletor por mudança na API: regrave amostras com `python scripts/contrato_apis.py --gravar <nome>`.
- Commits de dados diários (`Dados atualizados em ...`, `Histórico diário ...`) vêm do Actions; não edite `dados/` à mão.
- Não crie PR sem pedido; desenvolva na branch designada da sessão.

## Dados sem duplicação

Valem para todo código novo e para qualquer arquivo que você tocar. Onde o código atual ainda foge da regra, não amplie o desvio e, se o ajuste couber na tarefa, corrija.

1. **Um lugar só.** Cada dado vive em um arquivo; os demais apontam por id (como `proposicoes_cadastro/<ano>.json` com `proposicoes/<idDeputado>.json`, e `nucleo/`). Não copie tipo, ementa, nome ou valor para dentro de outro registro.
2. **Id estável e rastreável.** Todo id novo guarda o id original da fonte no registro e é derivado de hash de `fonte + id original` (sha1 hex truncado, com prefixo do tipo: `pes_`, `man_`, `for_`, `fed_`). Reprocessar nunca gera id diferente: nada de contador, posição na lista, data da coleta ou ordem de arquivo. Atenção: `pes_` hoje usa `nome|nascimento` como âncora e, para quem só tem id de uma fonte, o id da fonte; se a ligação com o TSE aparecer depois, o id muda. Não repita esse padrão em id novo.
3. **Ligação por nome numa tabela só.** Toda ligação fonte -> pessoa registra método (`cpf`, `nome+nascimento`, `sequencial`, `nome+cargo+uf`, `nome+uf`, `urna+cargo+uf`; em registros de Assembleia também `nome`, `palavras`, `extremos`, `nome+partido`, `similaridade`, `urna+tse`; `manual`) e confiança (alta/média/baixa) em `site/dados/nucleo/ligacoes.json`, gerado por `identidades.py` (`ligacao[fonte] = [método, confiança]`; ambíguos em `ambiguos`, sem par em `semLigacao`). Nome em registro de Assembleia (autor, favorecido, gabinete, voto) -> deputado: `identidades.ligar_nomes(nomes, deputados, UF)`; a regra de cada UF fica em `identidades.ESTRATEGIAS`, o coletor só chama (`ligar = partial(identidades.ligar_nomes, uf=UF)`). A coleta grava `dados/estaduais/<UF>/ligacoes.json` e `gerar.py` junta em `nucleo/ligacoes.json` (`registros`). Correção manual: `scripts/ligacoes_manuais.json`. Comparar nomes de deputado com TSE: `identidades.eleito_do_tse`. Regra dura: **proibido ligar fonte a pessoa fora de `identidades.py`.** Coletor não compara nomes por conta própria: grava o nome e o id da fonte como vieram e chama `identidades.ligar_nomes`. UF com regra própria de nome (título, apelido, partido no nome) ganha entrada em `ESTRATEGIAS`, não função no coletor. Não crie outra função de ligação nem outra tabela. Nome ambíguo não liga. `manual` só por correção explícita num arquivo versionado, nunca no código do coletor.
4. **Normalizar na entrada**, no coletor ou no primeiro passo de `gerar*`, nunca no front:
   - CNPJ/CPF só dígitos, com zero à esquerda restaurado e dígito verificador conferido; inválido, zerado ou mascarado vale como ausente (`fornecedores.documento`). Reuse, não reimplemente.
   - Nome de fornecedor padronizado por `fornecedores.nome_chave` (sem acento, caixa, pontuação nem forma jurídica); `estaduais_comum.sem_acento`/`nome_limpo` para nomes de pessoa.
   - Datas em ISO `AAAA-MM-DD` (`estaduais_comum.data_br_iso`); valores em número (`valor_br`), mês como inteiro.
   - Categoria de despesa: lista fixa única em `scripts/categorias.py` (`CATEGORIAS`, regras em `REGRAS`, `categoria_id`, `agrupar`), para Câmara, Senado e Assembleias. O coletor grava o rótulo da fonte como veio (`categoria`/`tipo`); o `gerar*` agrupa por id e guarda os rótulos originais em `originais`. Rótulo sem regra vira `outros` e `gerar.py` avisa (`categorias.DESCONHECIDAS`): acrescente a palavra em `REGRAS` e um caso em `tests/test_categorias.py`. Não crie lista de categorias por UF nem reagrupe no front.

## Coletores de Assembleias estaduais (novo estado)

Um `scripts/coletar_estadual_<uf>.py` por UF fora do SAPL, com job próprio na matriz `estaduais` de `.github/workflows/atualizar.yml` (job lento não segura os outros). Use `estaduais_comum as comum` (`sessao()`, `salvar`, `ler`, `avisar`) e `identidades.ligar_nomes` para ligar nomes a deputados e grave em `dados/estaduais/<UF>/`. Foco no tempo de execução:

- **Nunca refaça tudo todo dia.** O CI parte de checkout limpo; só o que está commitado em `dados/estaduais/` vale como cache. Antes de escrever o coletor, meça uma coleta do zero e uma com cache (`time` em Python, contra a API real) e anote no `CHANGELOG.md`.
- **Anos encerrados** (`comum.ano_encerrado`: `ano < hoje.year - 1` com arquivo existente) não são baixados de novo. Dado mensal (verba, remuneração, diárias): releia só os meses que faltam no arquivo e `comum.meses_recentes(hoje, MESES_RECENTES)`; o resto vem do arquivo anterior (guarde `mes` em cada item).
- **Proposições, leitura incremental.** Procure na API ordenação ou filtro por data de alteração (MG tem `ord=3`, por `dataUltimaAcao`; RN lista da mais nova para a mais antiga). Leia até a data da coleta anterior (1 dia de folga) e junte com `materias_<ano>.json`. Sem isso, guarde no arquivo anual `vistas` ({chave: dia em que o detalhe foi lido}, inclusive o que não é de deputado, como na BA) e releia o ano corrente escalonado (`zlib.crc32(chave) % N`), nunca tudo no mesmo dia.
- **Releitura completa de segurança** a cada `RENOVAR_COMPLETA_DIAS` (14): guarde `completaEm` no arquivo e faça a completa também quando faltar o arquivo de algum ano. O incremental não vê mudança que não altera o campo de ordenação (ex.: arquivamentos no RN).
- **Ritmo da fonte.** Respeite pausa e conexões simultâneas (`CONEXOES_POR_HOST` e `PAUSA`); não paralelize além, o bloqueio costuma vir sem aviso.
- **Prazo.** O job tem `ESTADUAIS_PRAZO_MIN` (25 min): o coletor guarda o que leu e termina. Grave o arquivo ao fim de cada etapa (ano, deputado) e faça cada etapa falhar com `comum.avisar` sem derrubar as outras.
- **Teste offline** em `tests/test_coletar_estadual_<uf>.py`: caminho incremental (lê só o novo, junta com o guardado, completa velha lê tudo) e amostra real em `tests/fixtures/contratos/` (`CONTRATOS` no coletor). Todo `monkeypatch` deve cobrir a função que o código realmente chama (na BA, `baixar_ckan` e não `baixar`), senão o teste vai à internet.
- Os itens que o coletor grava obedecem à seção "Dados sem duplicação" (documento, nome e data normalizados; ligação de deputado pelo núcleo; categoria só como a fonte publica, o `gerar*` mapeia).
