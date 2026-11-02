# SP (Alesp) — pesquisa de endpoints equivalentes ao coletor do PR

Descoberta principal: a API do portal (`https://legis-api-portal-prd.al.sp.gov.br`, já usada para foto e presença) tem Swagger público em `/v3/api-docs` (cópia em pesquisa/api.json). Sem login nem captcha nos GET testados. Os dados abertos XML (`https://www.al.sp.gov.br/repositorioDados/...`) são o catálogo em `/dados-abertos/grupo/{1,2,21,41,81}`.

Já coleta (coletar_estadual_sp.py): deputados (deputados.xml + foto API), proposições PL/PLC/PR/PDL/PEC/PCONST com autoria (proposituras.zip + documento_autor.zip), verba de gabinete (despesas_gabinetes_<ano>.xml), remuneração (folha HTML), presença em plenário (lista-presenca-parlamentar). Arquivos em dados/estaduais/SP: deputados, ligacoes, materias_2023..2026, presenca, remuneracao_2025/2026, verbas_2023..2026.

## 1. Normas legais com autoria — ENCONTRADO (esforço médio)
- Lista de normas: `GET https://www.al.sp.gov.br/repositorioDados/legislacao/legislacao_normas.zip` (10 MB zip, 118 MB XML, atualizado diariamente; HTTP 200, Last-Modified 2026-10-31). Tipos: `legislacao_tipo_normas.xml` (Lei=9, LC=2, EC=55, Decreto=3, Decreto Legislativo=28, Resolução da Alesp=19, Ato da Mesa=21 ...).
- Campos: `IdNorma, Data, Numero, IdTipo, Ementa, IdTema, Situacao, Promulg, DataDO, URLFicha (http://www.al.sp.gov.br/norma/<IdNorma>)`. NÃO traz autoria nem deputado.
- Autoria vem pela ligação PL -> norma, na API: `GET /processo/detalhes/todos/{sigla}/{ano}/{numero}` (ex.: `/processo/detalhes/todos/PL/2025/1373`) retorna `transformadoNorma:true, urlNorma:"/norma/212095", descricaoNorma:"Lei nº 18.386, de 23/12/2025", autores:[{id,matricula,nome}]` (autor pode ser "Governador", sem matrícula; deputado vem com `matricula`, que liga ao id do deputado).
- Descobrir quais PL viraram lei: `GET /processo?listaIdTipoProcesso=1&transformadoNorma=true&ano=2025&page=0&size=200` (169 resultados em 2025, 22 em 2026; o item da listagem não traz `urlNorma`, só o detalhe traz; flag `transformadoNorma` vem null na listagem mas o filtro funciona). Outros tipos: PLC=2, PDL=4, PR=3, PEC=5.
- Volume: ~170 PL/ano, 1 chamada de detalhe cada. Incremental: `dtInicio/dtFim` no /processo (ou só anos novos + releitura de pendentes).
- Riscos: autoria "Governador" não é deputado; norma sem PL (decretos do Executivo) não tem autor; o XML de normas é enorme (118 MB), preferir só a API ou filtrar IdTipo em streaming.

## 2. Votação nominal por deputado no plenário — NÃO PUBLICA
- `GET /votacao/{ano}` (ex.: /votacao/2026, 9 KB) e `GET /sessoes-plenarias/{id}/votacoes` retornam só a deliberação: `idSessao, dataSessao, descricao, idProposicao, numeroProposicao, resultadoVotacao, urlArquivoPrincipal` (PDF do ementário). Sem voto por deputado. (Portal confirma: nominal só em PDF.)
- Alternativa parcial (voto em comissão, por deputado, em parecer): `GET /processo/votacaoComissao/{idProcesso}?size=N` retorna `votos:[{siglaColegiado, parlamentar (nome), txVoto:"Favorável ao voto do relator"}]` (só nome); em XML: `repositorioDados/processo_legislativo/comissoes_permanentes_votacoes.xml` com `IdDeputado, IdDocumento, IdReuniao, IdPauta, IdComissao, TipoVoto (F...), Voto` (liga por IdDeputado). Já listado como "fora do contrato" no docstring; é voto em parecer, não votação de plenário. Esforço baixo-médio se quiser incluir como "voto em comissão".

## 3. Diárias — NÃO PUBLICA (nada localizado)
- Busca no portal (administração, deputado/contas, dados abertos, grupos 1/2/21/41/81) não mostra diárias de deputados. Sem endpoint.

## 4. Gabinete (servidores lotados) — ENCONTRADO, com ressalva (esforço médio)
- `GET https://www.al.sp.gov.br/repositorioDados/administracao/funcionarios_lotacoes.xml` (16,5 MB) e `funcionarios_cargos.xml` (13,6 MB). `uas.xml` (97 KB, atualizado diariamente) mapeia unidades.
- Campos lotação: `IdUA, NomeUA ("Gabinete do Deputado FULANO"), NomeFuncionario, DataInicio, DataFim`. Cargos: `NomeFuncionario, NomeCargo (AUXILIAR PARLAMENTAR, ASSESSOR ESPECIAL I...), NomeRegime, DataInicio, DataFim`. Liga ao deputado só pelo texto "Gabinete do Deputado <nome>" (30 mil linhas), ligar via identidades.ligar_nomes (estratégia nova em ESTRATEGIAS); funcionário só por nome (sem id; homônimos).
- RESSALVA: Last-Modified 2023-05-12 e a maior DataInicio é 2023-07: arquivo parado, sem lotações recentes. Útil só como histórico até meados de 2023. Para dados atuais não há equivalente (a folha de pagamento de servidores não foi localizada).
- Risco: dados pessoais de servidores (nome); o PR faz o mesmo, mas confirme a política antes.

## 5. Pautas e atas (links) — ENCONTRADO (esforço baixo-médio)
- Plenário: `GET /sessoes-plenarias/consulta?ano=2026&page=0&size=100` (JSON paginado; campos id, tipo, numero, titulo, situacao, dtInicio, flDeliberativa, temPauta/temIntegra; 259 sessões em 2026). Por sessão: `/sessoes-plenarias/{id}/pauta` (vem vazio na sessão testada), `/sessoes-plenarias/{id}/ordem-do-dia`, `/sessoes-plenarias/{id}/integra` (ata: `urlIntegra` https://www.al.sp.gov.br/legis/docs/2026/8/6/310000003899.html e `urlIntegraDO` link do DOE), `/ementa`. Filtros dataInicial/dataFinal permitem incremental.
- Comissões: `GET /colegiado/reunioes?ano=2026&page=0&size=N` (id, dtReuniao, colegiadosRelacionados, `documentosReuniao` com "Pauta de colegiado", txPath/txNomeArq do arquivo; filtros dataInicio/dataFim, pesquisarAtas); `/colegiado/reuniao/{id}/pauta`; `/colegiado/reunioes-atas-transcricoes/{idColegiado}/{idLegislatura}` (atas). XML equivalente: `comissoes_permanentes_reunioes.xml`, `comissoes_permanentes_deliberacoes.xml`, `comissoes_permanentes_presencas.xml` (presença de deputado em comissão por IdDeputado).
- Agenda geral: `repositorioDados/agenda/agenda_eventos.xml` (29 MB, atualizado diariamente; Titulo, Local, Data, HoraIni; sem deputado). Pouco útil.
- Pauta do deputado: não há; pautas ligam a sessão/comissão, não a deputado (exceto presença em comissão).
- URL do documento: montar a partir de `txPath` + `txNomeArq` sob https://www.al.sp.gov.br/legis (conferir ao implementar).

## 6. Contratos e atas de registro de preço do órgão — ENCONTRADO (esforço médio, HTML)
- `GET https://www.al.sp.gov.br/alesp/contratos/` (HTML único de 4 MB, 5.540 contratos, 2012 a 2026; blocos: Contratos Vigentes/Encerrados, Atas para Registro de Preço, Dispensa Art. 24 I e II, Convênios e Outros). Cada item: "Processo Digital N / AAAA", modalidade (Pregão, Inexigibilidade...), objeto, link PDF (`/repositorio/contratos/<arquivo>.pdf`) e link de detalhe.
- Detalhe: `GET /alesp/contratos/detalhe/?detContrato=<hash md5>` (HTML 48 KB): CONTRATANTE, CONTRATADA com CNPJ (ex.: "MADARP NEGÓCIOS E SOLUÇÕES LTDA. - 54.456.948/0001-85"), OBJETO, MODALIDADE, VIGÊNCIA, VALOR TOTAL, No. DO EMPENHO, ASSINATURA, e tabela "Informações Financeiras" (data, empenho, NF, fornecedor, descrição, valor). Dá para ligar a fornecedores por CNPJ (`fornecedores.documento`).
- Lista de licitações abertas: `https://www.al.sp.gov.br/SistemaContratos/exibe-licitacoes-pregao-eletronico` (não testado a fundo).
- Não é a API de processos tipo "Contrato" (`/processo?listaIdTipoProcesso=134`, 2.923 itens): esses são ofícios do TCE sobre contratos do Executivo, não contratos da Alesp. Não usar.
- Incremental: ordem decrescente por processo/ano; 1 detalhe por contrato (só os novos e os vigentes). Pausa entre requisições: 5.540 detalhes na primeira carga é muito; limitar a vigentes + ano corrente e anterior.
- Risco: parse de HTML latin-1 (acentos como entidades HTML), página de 4 MB.

## 7. Regras/PDF do ressarcimento (verba) — ENCONTRADO (esforço baixo)
- A página https://www.al.sp.gov.br/deputado/contas/ cita os textos legais: Ato nº 02/2002 (`/norma?id=234`), Resolução nº 822/2001 (`/norma?id=3908`), Resolução nº 824/2002 (`/norma?id=925`). São páginas HTML de norma (não PDF); só link de fonte. Também há 'Prestação de Contas' no menu do deputado.

## 8. Outros ganhos possíveis (não pedidos)
- Presença em reuniões de comissão por deputado: `comissoes_permanentes_presencas.xml` (IdDeputado).
- Membros de comissões por data: `/colegiado/membros/{idColegiado}/{dtFiltro}`; `comissoes_membros.xml`.
- Biografia: `/biografia/{nuMatricula}`; lideranças: `/lideranca/todas`; mesa: `/ocupacoes-cargos/mesa-diretora`.
- Proposições de requerimento/indicação: `/processo?listaIdTipoProcesso=9` (Indicação)... (volume alto; já decidido não coletar).
- Limite do portal: XML de dados abertos mudam 1x/dia (Last-Modified 06:28), exceto funcionarios_* parados em 2023.

## Resumo por item
| Item | Status |
|---|---|
| deputados, proposições, presença, remuneração, verba | JÁ TEM |
| normas legais com autoria | ENCONTRADO (XML de normas + API detalhes PL) |
| votação nominal plenário | NÃO PUBLICA (só PDF; voto em comissão existe) |
| diárias | NÃO PUBLICA |
| gabinete (servidores) | ENCONTRADO mas parado em 2023 |
| pautas e atas | ENCONTRADO (API sessões e reuniões) |
| contratos e atas de registro de preço | ENCONTRADO (HTML /alesp/contratos/) |
| regras da verba | ENCONTRADO (links de normas) |
