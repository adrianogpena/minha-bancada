# PA (ALEPA) - pesquisa de endpoints equivalentes ao coletor do PR

Hoje coleta (scripts/coletar_estadual_pa.py, dados/estaduais/PA/): deputados, presenca, diarias (2023-2026), verbas indenizatorias (2023-2026, dashboard57), total mensal da verba de gabinete (sigep frame_verbagabinete), ligacoes.
Docstring do coletor diz "projetos e votacoes: sem fonte". Isso esta desatualizado: existem (abaixo). Amostras em scratchpad/pesquisa/pa/.

Hosts: alepa.pa.gov.br (ASP.NET MVC + DevExpress, sem login/captcha), alepa.quartertec.com.br (dashboards DevExpress), sigep.alepa.pa.gov.br/transp (PHP), bancodeleis.alepa.pa.gov.br (PHP + API JSON), downloads.alepa.pa.gov.br (PDFs). Todos responderam 200 a curl sem User-Agent especial.
Nenhum host novo estava em ENDPOINTS.md exceto alepa.pa.gov.br, sigep, quartertec: bancodeleis.* e downloads.* sao novos (registrar).

## Resumo

| Item PR | Status PA |
|---|---|
| deputados | JA TEM |
| presenca em plenario | JA TEM |
| diarias | JA TEM |
| verba indenizatoria (ressarcimento) | JA TEM (dashboard57). Regras/PDF: NAO PUBLICA (pagina so embute o dashboard) |
| remuneracao por deputado | ENCONTRADO (sigep, 2 passos por nome) - esforco medio |
| gabinete (servidores lotados) | ENCONTRADO (sigep frame_relacaopessoal, teto 103 linhas por consulta) - medio |
| votacao nominal por deputado | ENCONTRADO (HTML por votacao, 2015+) - medio |
| proposicoes (autoria por nome) | ENCONTRADO (callback DevExpress; paginacao nao reproduzida, usar janela de datas) - alto |
| normas legais (leis/decretos/resolucoes) | ENCONTRADO (API JSON, SEM autoria) - baixo |
| pautas (links) | ENCONTRADO (callback, mes a mes) - baixo |
| atas (links PDF) | ENCONTRADO (callback, mes a mes) - baixo |
| contratos do orgao | ENCONTRADO (dashboard52, JSON) - baixo |
| atas de registro de preco / licitacoes | ENCONTRADO (dashboard59, JSON) - baixo |

## Votacao nominal por deputado - ENCONTRADO
- Lista: POST https://alepa.pa.gov.br/Legislativo/CallbackPanelVotacoesNominais
  form: `__DXCallbackName=cbpPautas`, `__DXCallbackArgument=c0:`, `ano=2026`, `mes=<1-12>` (mes OBRIGATORIO; sem mes = HTTP 500). Antes, um GET em /Legislativo/VotacoesNominais para pegar o cookie ASP.NET_SessionId.
- Resposta: HTML com cartoes `<a class='pauta-item-title' href='/Legislativo/DetalhesVotacaoNominal?IdProposicao=16339&IdVotacao=8869'>27/10/2026 - PROJETO DE LEI COMPLEMENTAR N 10/2026 - 1 TURNO</a>`. Uma linha por (proposicao, turno); sem paginacao (8 itens no mes testado). Mes sem votacao: 0 itens.
- Cobertura: testado 2015, 2019, 2023, 2024, 2025, 2026 (todos retornam itens). Leitura incremental: reler so os 2 ultimos meses; meses encerrados ficam em cache.
- Detalhe: GET /Legislativo/DetalhesVotacaoNominal?IdProposicao=16339&IdVotacao=8869 (os parametros type=DOC/PDF devolvem o MESMO HTML, nao ha arquivo).
  HTML com sessao, numero da sessao, projeto, data, autor (ex. MINISTERIO PUBLICO DO ESTADO), turno, resultado (APROVADA) e listas por voto: blocos `SIM`, `NAO`, `ABSTENCAO`, `NAO VOTARAM`, cada um com `Nome  Partido` por deputado e `Quantidade: N`. Exemplo: `SIM  ANDREIA XARAO MDB | ANGELO FERRARI FE UNIAO PP | ... Quantidade: 25 ... NAO VOTARAM ADRIANO COELHO MDB ... Quantidade: 16`.
- Liga ao deputado SO POR NOME (sem id) -> identidades.ligar_nomes com UF=PA (nomes de urna, igual aos de deputados.json; partido vem como federacao "FE UNIAO PP").
- Volume: ~8 a 10 votacoes por mes, 1 GET de ~95 KB por votacao. 2026 inteiro ~60-100 GET.
- Esforco: medio (parse HTML, mapear blocos de voto). Risco: HTML sem estrutura semantica (texto corrido); sessao pode ter voto simbolico (so lista nominal publicada aqui).

## Proposicoes - ENCONTRADO (paginacao NAO reproduzida)
- Pagina: https://alepa.pa.gov.br/Legislativo/Proposicoes. Filtro: POST /Legislativo/CallbackPanelProposicoes
  form: `__DXCallbackName=cbpProposicoes`, `__DXCallbackArgument=c0:`, `model[Ano]=2026` (aceita tambem model[Numero], model[IdTipoProposicao], model[IdTipoAutor], model[IdAutor], model[Texto], model[DataInicio]=2026-10-20T03:00:00.000Z, model[DataFim]=...). Cookie de sessao do GET da pagina.
- Resposta: HTML com `<h3>DEP. TORRINHO TORRES</h3><span>INDICACAO N 96/2026, DE 28/10/2026</span><p>ementa</p>` e link `/Legislativo/DetalhesProposicao?IdProposicao=16407&tipo=...`. PDF do texto: https://downloads.alepa.pa.gov.br/Projeto/16407.PDF. Autor so pelo nome ("DEP. X"), pode ser orgao (MINISTERIO PUBLICO etc.).
- Limite: so 10 itens por chamada. pageCount informado no HTML (2026: 196 paginas, ~1960 itens; 2023: 361 paginas). Tentei 9 formas do pager (`PN1`, `PAGERONCLICK|3;PN1;`, com DXMVCCallbackState, model, cookie): devolve sempre a pagina 0. PageSize/PageIndex no model tambem ignorados.
- Alternativa que FUNCIONA: particionar por filtros ate <=10 itens: Ano+Numero (1 item por tipo+numero), ou janela DataInicio/DataFim por dia (+ IdTipoProposicao se o dia passar de 10). Ex.: janela 20-22/10/2026 devolveu 4 paginas (~40 itens). Filtro por data permite leitura incremental.
- Volume: ~2000 proposicoes/ano; por dia + tipo ~300-600 requisicoes na carga inicial de um ano, depois so os dias novos. Respeitar pausa de 1 s.
- Esforco: alto (paginacao nao resolvida; descobrir o state do pager com o navegador/DevTools talvez resolva e derrube o custo para ~200 req/ano). Risco: DevExpress muda o protocolo; nome do autor sem id.

## Normas legais - ENCONTRADO (sem autoria)
- API JSON: GET https://bancodeleis.alepa.pa.gov.br/api/leis.php?ano=2026&tipo=3&numero=&q= (documentacao em /api.php; pagina https://alepa.pa.gov.br/Home/Page/BancodeLeis embute o mesmo PHP).
- Tipos: 3 Lei Ordinaria, 4 Lei Complementar, 2 Decreto Estadual, 1 Decreto Legislativo, 10 Resolucoes, 11 Emendas Constitucionais Estaduais, 12 Emendas Constitucionais Federais.
- Resposta: `{"status":true,"total":50,"resultados":[{"id":32532,"numero":"11666","ano":"2026","tipo":"Lei Ordinária","ementa":"...","arquivo":"lei_...pdf","link_pdf":"https://bancodeleis.alepa.pa.gov.br/arquivos/lei_....pdf"}]}`.
- Limite duro de 50 por chamada, sem pagina. 2026: tipo=3 e tipo=2 batem 50 (truncados); tipo=1 tem 38, tipo=4 tem 7. Particionar com `numero=` parcial (ex. 116, 115...) ate vir <50. Base total ~30 mil normas (desde 1900s); coletar so ano atual e anteriores recentes.
- NAO traz autoria nem data (so ano); sem ligacao a deputado -> serve como catalogo de leis, nao como "leis de autoria do deputado". Cruzar com proposicoes (mesmo numero/ano) exigiria casar manualmente.
- Esforco: baixo. Risco: a API diz "evite chamadas repetitivas"; sem filtro de data (relera o ano corrente).

## Pautas do plenario (links) - ENCONTRADO
- POST https://alepa.pa.gov.br/Legislativo/CallbackPanelPautas, form `__DXCallbackName=cbpPautas`, `__DXCallbackArgument=c0:`, `ano=2026`, `mes=10` (cookie do GET /Legislativo/Pautas).
- Resposta HTML: `<a class='pauta-item-title' href='/Legislativo/DetalhesPauta?Id=1255'>27/10/2026 - PAUTA DA 29 SESSAO ORDINARIA, DO 2 PERIODO, DO(A) 4 ANO LEGISLATIVO DA 61 LEGISLATURA</a>`. Funciona em 2019 e 2026 (4 a 8 itens por mes). Detalhe da pauta e HTML (GET /Legislativo/DetalhesPauta?Id=N), nao PDF; para o site basta o link.
- Esforco: baixo. Sem ligacao com deputado (pauta e da sessao).

## Atas das sessoes (links PDF) - ENCONTRADO
- POST https://alepa.pa.gov.br/Legislativo/CallbackPanelAtas, form `__DXCallbackName=cbpAtas`, `__DXCallbackArgument=c0:`, `ano`, `mes` (cookie do GET /Legislativo/Atas).
- Resposta: `<a class='pauta-item-title' target='_blank' href='https://downloads.alepa.pa.gov.br/Ata/3278.PDF'>30/09/2025 - ATA DA 29 SESSAO ORDINARIA ...</a>`. PDF 117 KB (Content-Type application/pdf). 2026/6: 20 atas; 2026/9: 6; 2026/10: "Nenhuma ata" (publicacao com atraso). Mes vazio = reler nos meses recentes.
- Esforco: baixo.

## Contratos do orgao - ENCONTRADO
- Pagina https://alepa.pa.gov.br/Transparencia/Page/Contratos embute o dashboard52. API: GET https://alepa.quartertec.com.br/api/dashboard/data?dashboardId=dashboard52&itemId=gridDashboardItem1&parameters=[]&query={}  (mesma API/decodificacao DTO do dashboard57 que o coletor ja usa; `parameters=[]` basta, sem CPF_Deputados). Definicao do painel: GET /api/dashboard/dashboards/dashboard52 (JSON).
- 135 contratos de todos os anos numa unica chamada (45 KB). Campos: DataItem0 objeto resumido, DataItem1 data de inicio, DataItem2 situacao ("Em andamento"), DataItem8 numero do contrato ("011/2026"), DataItem3 licitacao+modalidade ("008/2026 Pregao"), DataItem4 razao social do contratado, DataItem7 fiscal/gestor (nome de pessoa), medidas = valor por periodo. O painel tem ainda ApFisEmpresa.CNPJ (nao exibido na grade; pedir via query) e gridDashboardItem(s) de documentos (IdApFisContratoAnexo) - URL de download dos anexos nao descoberta.
- Esforco: baixo (reusa consulta_dashboard/linhas_dashboard com outros itemId). Risco: ordem de colunas por codigo DataItemN muda se o painel for editado.

## Atas de registro de preco / licitacoes - ENCONTRADO
- Dashboard59: GET https://alepa.quartertec.com.br/api/dashboard/data?dashboardId=dashboard59&itemId=gridDashboardItem2&parameters=[]&query={} (129 linhas, 45 KB). Campos: ano (DataItem6), numero (DataItem2), modalidade (DataItem0, ex. Pregao), objeto (DataItem1, texto "DISPOE SOBRE REGISTRO DE PRECOS PARA ..."), data do edital (DataItem9), situacao do certame (DataItem10: Suspenso, Contrato Assinado), valor estimado (DataItem11), vencedor/empresa (DataItem7). Documentos (editais, atas) em gridDashboardItem3 (nome do arquivo + IdApFisContratoAnexo), URL de download nao descoberta.
- Nao ha lista separada de "atas de registro de preco"; ficam como licitacoes (filtrar objeto por "REGISTRO DE PRE").
- Esforco: baixo.

## Gabinete (servidores lotados) - ENCONTRADO
- Hoje so coleta o total mensal da verba de gabinete. Lista nominal: POST https://sigep.alepa.pa.gov.br/transp/frame_relacaopessoal.php, form `b_lotacao=GAB. DEP. GUSTAVO SEFER` (tambem b_nome, b_cargo). GET sem filtro ja traz a tabela.
- Colunas: Matricula, Nome, Admissao, Exoneracao, Carga horaria, Cargo/Funcao ("FUNCAO PUB. APOIO LEGISLATIVO FPAL-04"), Classificacao, Lotacao ("10430 - GAB. DEP. GUSTAVO SEFER"), Situacao (Ativo/Inativo). Inclui exonerados com data.
- LIMITE: a resposta trunca em 103 linhas de dados (com filtro por gabinete, e sem filtro) -> um gabinete com >103 registros (incluindo inativos) perde servidores. Mitigar com b_cargo (um por classificacao/cargo) ou b_nome (letra) e unir. Lotacao traz o id numerico do gabinete (10430) e o nome -> casar com o deputado por nome (ligar_nomes).
- Sem salario por servidor nessa tela (o salario esta em frame_servidores/detalhecc, abaixo).
- Esforco: medio (41 deputados x particoes; ~100-300 requisicoes, foto do dia, sem historico).

## Remuneracao por deputado - ENCONTRADO (2 passos)
- Lista: POST https://sigep.alepa.pa.gov.br/transp/frame_servidores.php form `anoref=2026&mes=9&b_nome=GUSTAVO` (b_nome obrigatorio; sem nome mostra "Preencha o nome"). Linhas: matricula, nome (link), cargo (DEPUTADO ESTADUAL), lotacao (PLENARIO).
- Detalhe: o link `detalhecc.php?mes=<token>&ano=<token>&mat=<token>&tipo=<token>` (tokens base64 gerados por linha; pegar o href da lista na hora, nao montar). Retorna: Tipo de folha, Classificacao DEPUTADOS, Cargo, Lotacao, CPF mascarado (931.***.***-**), Remuneracao R$ 34.774,64, Ferias, Adiantamento de 13, Pecunia, Total Bruto, Descontos R$ 9.725,53, Redutor Constitucional, Total Liquido R$ 25.049,11 (setembro/2026).
- Anos 2023-2026, mes 1-12 e 13o. Liga por nome (nome civil "GUSTAVO BEMERGUY SEFER" difere do de urna -> ligar_nomes ja trata nome civil via TSE).
- Volume: 41 deputados x meses x 2 requisicoes; ~80 req/mes, so 2 meses recentes na incremental. Pausa de 1 s.
- Esforco: medio. Risco: tokens por sessao; busca por substring devolve homonimos (filtrar cargo == DEPUTADO ESTADUAL).
- Complemento sem custo: PDF "Historico de subsidios dos deputados" em https://alepa.pa.gov.br/Transparencia/Page/EstruturaRemuneratoriaDeputados (a pagina responde o proprio PDF; pdftotext funciona): 2022 R$25.322,25; 2023 R$29.469,99/31.238,19; 2024 R$33.006,39; 2025 R$34.774,64, com normas (Decreto Legislativo). So 4 linhas, para tabela de referencia.

## Regras/PDF do ressarcimento (verba) - NAO PUBLICA
- Pagina /Transparencia/Page/VerbaIndenizatoria so embute o dashboard57 (ja coletado); nenhum link de ato/PDF das regras na pagina. Pagina "Dados Abertos" da Transparencia e so o card da API de leis.

## Pendencias de confirmacao
- Paginacao da lista de proposicoes (maior ganho): inspecionar com DevTools a requisicao real do pager de /Legislativo/Proposicoes (provavelmente envia o state do cardView + model como customArgs).
- Anexos de contratos/licitacoes (IdApFisContratoAnexo): achar a URL de download no portal quartertec.
- Registrar em ENDPOINTS.md: bancodeleis.alepa.pa.gov.br, downloads.alepa.pa.gov.br, alepa.pa.gov.br/Legislativo/*.
