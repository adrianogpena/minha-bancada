# CE (Alece): pesquisa de endpoints equivalentes ao coletor do PR

Todos testados em 2026-10-31 com curl (UA Mozilla), 2 s de pausa. Sem captcha/login em nenhum. Amostras em `.../scratchpad/pesquisa/ce/`.
Base: transparencia = https://transparencia.al.ce.gov.br ; site = https://www.al.ce.gov.br

## Já coleta (coletar_estadual_ce.py)
deputados, proposições (numero.php: PL, PLC, PEC, PDL, PR), votação nominal (XLSX), diárias, remuneração, verba (VDP CSV).
Não coleta e o docstring diz "presença não existe".

## Itens

### Deputados / Proposições / Votação / Diárias / Remuneração / Verba: JÁ TEM
Proposições: faltam duas tabelas que o numero.php oferece e `TABELAS` não lê: `projeto_indi` (indicações) e `projeto_mens` (mensagens do Executivo). Links: http://www2.al.ce.gov.br/legislativo/proposicoes/numero.php?nome=31_legislatura&tabela=projeto_indi&opcao=T (idem `projeto_mens`). Esforço baixo (incluir em TABELAS). Legislaturas anteriores: `nome=30_legislatura` etc.

### Normas legais (leis/decretos/resoluções com autoria): ENCONTRADO parcial
- Resoluções e PDL com autoria: já vêm de numero.php (PR, PDL, PLC). A coluna "situação" indica se virou lei, mas não há número da lei publicada.
- https://www.al.ce.gov.br/legislativo/leis-e-normativos-internos : lista (número/ano, tipo, ementa, data, links Visualizar/Download) só de atos administrativos internos (Ato Deliberativo, Ato Normativo, Resolução administrativa). Sem autoria de deputado. Valor baixo para o site.
- Leis estaduais promulgadas: não há lista própria na Alece (https://www2.al.ce.gov.br/legislativo/sinopse_legislativa/index_sinopse.html e "Mapa de Leis Históricas" são páginas antigas; não testei profundidade). Esforço alto, ganho incerto. Status: NÃO PUBLICA lista estruturada com autoria.

### Votação nominal: JÁ TEM (XLSX por matéria, ~60 linhas na página).

### Presença em plenário: ENCONTRADO (proxy), sem lista oficial de presença
- Oradores do dia: https://www.al.ce.gov.br/legislativo/oradores (HTML) e CSV https://www.al.ce.gov.br/legislativo/oradoresCsv (200, text/csv, ~1 KB, só o dia atual). Histórico: https://www.al.ce.gov.br/legislativo/oradores-historico?ano=2025&texto= (HTML, anos 2025 e 2026; lista por data: expediente, ordem de oradores, "cedido para").
- Formato: `29.10.2026 PRIMEIRO EXPEDIENTE 90min (10min cada) 1º FERNANDO SANTANA cedido para RENATO ROSENO ...` ; liga ao deputado só por nome (usar `identidades.ligar_nomes`).
- Dá: pronunciamentos/cessões de tempo, não presença. Quem votou (XLSX) já indica presença na votação (quem ficou em branco pode ser ausente). Esforço médio. Risco: texto livre.
- Atas com lista de presentes: ver Atas (vazio).

### Diárias: JÁ TEM.

### Gabinete (servidores lotados no gabinete): ENCONTRADO
- https://transparencia.al.ce.gov.br/gestao-de-pessoas/pessoal?mes=10&ano=2026&page=N (HTML, 34 linhas/página, 172 páginas/mês). Cada linha tem botão com `data-bs-remuneracao="<base64>"`; decodificado (latin-1), campos separados por `_`: matrícula, nome, LOTAÇÃO, situação, cargo, nível, ..., ano, mês, ..., categoria, data de admissão.
- Exemplo decodificado: `023094_ABIGAIL SILVA DO NASCIMENTO FONSECA_GABINETE DEPUTADA DRA SILVANA_EM EXERCICIO_ASS GAB PARLAMENTAR_ASP03_...`. A lotação "GABINETE DEPUTADO(A) <nome>" liga o assessor ao deputado (por nome).
- O CSV (`/gestao-de-pessoas/pessoal/csv?mes=&ano=`, cp1252, `;`, 6.537 linhas, categoria "ASSESSOR PARLAMENTAR" 1.217) NÃO traz a lotação: só cargo "ASS GAB PARLAMENTAR" e remuneração. Já é o CSV que o coletor usa para a remuneração.
- Filtros do formulário (GET): `mes, ano, categoria, situacao, cargofuncao, nome`. `categoria=SERVIDORES ATIVOS - FUNÇÃO DE NATUREZA COMISSIONADA - ASSESSOR PARLAMENTAR` reduz a ~36 páginas (não testei a resposta com essa categoria; `cargofuncao` exige código tipo `CP16_ASS COM INQUERITO ADM`, valor com o texto sozinho retornou 0). `nome=ABIGAIL` funciona (2 resultados).
- Incremental: só o mês corrente (e os que faltam). Esforço médio. Risco: base64 não documentada, 36 a 172 requisições/mês, nome do deputado no texto da lotação (variações).

### Pautas e atas (links): ENCONTRADO parcial / atas BLOQUEADO (vazio)
- Pauta do dia (Ordem do Dia): https://www.al.ce.gov.br/legislativo/ordem-do-dia/avulso-de-projeto (HTML com texto da pauta e PDF `/legislativo/tramit/tramit2026/up_*.pdf`), CSV `/avulso-de-projeto-csv`, PDF `-pdf`, histórico `-historico`. Só a pauta da próxima sessão; histórico paginado via HTML.
- Expediente (leituras de projetos com autoria "Autoria do Deputado X", entrada de proposição): https://www.al.ce.gov.br/legislativo/expediente , CSV `/legislativo/expedientecsv`, histórico `/legislativo/expediente-historico`. Útil: data de leitura de cada proposição e autoria.
- Atas: https://www.al.ce.gov.br/atas/legislaturas/16?ano=2026&categoria=<1..4,5,6> (GET; ids de categoria: 4 especial, 3 extra especial, 2 extraordinária, 1 ordinária provável, etc.). Testei 2023, 2024, 2025 com categoria 1, 5, 6 e 2026 com texto: sempre "Nenhum dado localizado". Status: NÃO PUBLICA (hoje vazio). Com categoria em texto devolve HTTP 500.
- Consulta antiga www2: https://www2.al.ce.gov.br/pdr/consultas.php?pg=publico (menu: apanhamento taquigráfico, deliberação plenário, avulso de requerimento, oradores, relatório de requerimentos), sem dados abertos na amostra ("Aguardando pauta").
- Esforço baixo para pauta atual + expediente; atas inviáveis.

### Contratos e atas de registro de preço do órgão: ENCONTRADO (API JSON + CSV)
- API JSON oficial, sem chave: https://transparencia.al.ce.gov.br/api/contratos (Swagger: https://transparencia.al.ce.gov.br/docs?api-docs.json). 20 por página, `?page=N` (total 1.790, 90 páginas). Filtros: numero_contrato, ano_contrato, doe_contrato, especie_contrato, objeto_contrato, cpfcnpj_contrato, fiscalgestor_contrato, contratado_contrato, iniciovigencia_contrato, fimvigencia_contrato, valorvencedor_contrato, inicio_contrato.
- Campos: id_contrato, numero, ano, especie (CONTRATO, ATA DE REGISTRO DE PREÇOS, CONTRATO DE FORNECIMENTO), objeto, cpfcnpj (só dígitos), fiscalgestor, contratado, iniciovigencia/fimvigencia (dd/mm/aaaa), valorvencedor ("8.400,00"), lotes[] (idlotes, numerolote, descricao, valor), aditivos[].
- Exemplo: `{"id_contrato":"1215","numero_contrato":"51","ano_contrato":"2026","especie_contrato":"CONTRATO","cpfcnpj_contrato":"07209299000138","contratado_contrato":"EDITORA VERDES MARES LTDA","iniciovigencia_contrato":"26/10/2026","valorvencedor_contrato":"8.400,00",...}`
- CSV completo de uma vez (873 KB, 2.098 linhas, UTF-8 BOM, `;`, campos multilinha por lote/aditivo): https://transparencia.al.ce.gov.br/licitacoes-e-contratos/contratos/csv . Traz ainda "Nº VDOC", "ÓRGÃO SOLICITANTE", tipo e preço do aditivo. Espécies: 1.218 atas de registro de preço, 741 contratos, 138 fornecimento. Anos 2021 a 2026.
- Outros endpoints da mesma API: /api/licitacoes (77 em 2026; filtros numero_edital, ano_edital, modalidade_edital, situacao_edital...), /api/empenhos, /api/pagamentos, /api/termos-credenciamento. Não ligam a deputado (dados do órgão).
- Incremental: ordenação por mais recente na página 1 (id_contrato crescente); ler até achar id já guardado; releitura completa a cada 14 dias (aditivos mudam).
- Esforço baixo. Risco: valores em string BR (`valor_br`), documentos já só dígitos (validar com `fornecedores.documento`), nova entrada no ENDPOINTS.md (`/api/contratos` mesmo host já listado; o CSV também).

### Regras/PDF do ressarcimento (verba): ENCONTRADO
- https://transparencia.al.ce.gov.br/despesas/verba-desempenho-parlamentar (HTML estático) lista os normativos da VDP com status: Resolução 287/1992 (revogada), Ato Normativo 225/2003 (revogado), 231/2005 (revogado), Ato Deliberativo 929 de 14/03/2023 (vigente), Resolução 762 de 21/12/2023, Ato Normativo 343/2024.
- PDFs: https://transparencia.al.ce.gov.br/userfiles/files/vdp/2023-ato-deliberativo-n-929_1775043845.pdf , `.../vdp/resolucao-762-23-publicacao_1775043845.pdf` , `.../vdp/ato-normativo-343-24_1775043845.pdf` (sufixo numérico muda a cada publicação; ler os links da página). Texto também em https://www.al.ce.gov.br/legislativo/leis-e-normativos-internos/1755/visualizar.
- Esforço baixo (um scrape de links). Risco: nome de arquivo com carimbo.

## Resumo de esforço
Baixo: contratos/atas de registro (API ou CSV), regras da VDP, indicações e mensagens (`projeto_indi`, `projeto_mens`), pauta/expediente atual.
Médio: gabinete (HTML paginado + base64), oradores histórico.
NÃO PUBLICA: atas (vazio), presença oficial, leis promulgadas com autoria.
