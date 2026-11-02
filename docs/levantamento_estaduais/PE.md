# PE (ALEPE) - pesquisa de endpoints

Amostras em `.../scratchpad/pesquisa/pe/`. Testado em 2026-10-31, sem login nem captcha em nenhum item abaixo.

Já coleta (`coletar_estadual_pe.py`): deputados (lista da legislatura + `parlamentares`), verba indenizatória (JSON do portal, por deputado/mês/nota), proposições (projetos, indicações, requerimentos, XML por ano).

## Resumo
| Item | Status |
|---|---|
| Deputados, proposições, verba | JÁ TEM |
| Gabinete (servidores lotados) | ENCONTRADO (liga por nome do deputado no texto da lotação) |
| Contratos do órgão | ENCONTRADO (JSON) |
| Atas de registro de preço | ENCONTRADO parcial (licitações JSON; tela própria sem endpoint confirmado) |
| Presença em plenário | ENCONTRADO (HTML por reunião, por nome) |
| Atas (links/texto) e expedientes | ENCONTRADO (HTML, listagem paginada) |
| Pautas | NÃO PUBLICA como pauta; o "expediente" do dia (pareceres e proposições lidas) é o mais próximo |
| Normas legais com autoria | ENCONTRADO (legis.alepe.pe.gov.br, HTML/ASP.NET) |
| Votação nominal por deputado | NÃO PUBLICA (atas só dizem "aprovado"; sem "nominal") |
| Diárias | NÃO PUBLICA (`/financas/diarias` cai na SPA vazia; nenhum endpoint de diárias no bundle JS) |
| Remuneração por deputado | NÃO PUBLICA por pessoa (`/remuneracao/` só por cargo; a tela "Remuneração e Ajuda de Custo dos Deputados" existe na SPA, endpoint não identificado) |
| Regras/PDF do ressarcimento | NÃO verificado (sem PDF achado no bundle); `verbaindenizatoria-rubricas.php` já dá as rubricas |

## Gabinete - ENCONTRADO, esforço baixo
- `GET https://dadosabertos.alepe.pe.gov.br/api/v1/servidores/?formato=json` (também `?ano=AAAA`, `?vinculo=a-disposicao|efetivo-cedido`, `&formato=csv`). 200, 617 KB, 1977 servidores; 1281 com lotação `GAB.DEP. <NOME>` (49 gabinetes distintos). Ano 2024 também responde (627 KB): histórico por ano.
- Campos: `NOME`, `CODIGO_LOTACAO`, `NOME_LOTACAO`, `CARGO_EFETIVO`, `CARGO_NIVEL`, `VINCULO`, `DATA_ADMISSAO.date`.
  ```
  {"NOME":"ABRAAO SANTOS SILVA","CODIGO_LOTACAO":"256","NOME_LOTACAO":"GAB.DEP. WANDERSON FLORENCIO","CARGO_EFETIVO":"Assessor Especial","VINCULO":"Comissionado","DATA_ADMISSAO":{"date":"2026-05-05 ..."}}
  ```
- Liga ao deputado só pelo nome dentro de `NOME_LOTACAO` (sem id): usar `identidades.ligar_nomes` com entrada em `ESTRATEGIAS` (tira o prefixo "GAB.DEP."; nomes parlamentares podem vir abreviados). Há também lotações de liderança ("Oposição / Vice-Líder / ...") que não são gabinete.
- Sem salário por servidor. `GET /api/v1/remuneracao/` (7 KB) é tabela por cargo (`cargo, remuneracao, tipoCargo, mesCompetencia, anoCompetencia`), serve para estimar. `GET /api/v1/lotacoes/` só dá totais; `/cargos/?vinculo=comissionado|efetivo` lista cargos.
- Sem filtro de data de leitura; arquivo pequeno, baixar inteiro por ano é barato. Risco: sem id de servidor (homônimos), usar id = hash de nome|lotação|admissão (id estável sem posição).

## Contratos e atas de registro de preço - ENCONTRADO, esforço baixo
- `GET https://dadosabertos.alepe.pe.gov.br/api/v1/contratos/?formato=json`: 200, 322 KB, 652 contratos, anos 2013-2026.
  ```
  {"modalidade":"Pregão Eletrônico","contratada":"A S DE LIMA COMERCIO LTDA.","cpfCnpj":"22553731000105.00","objeto":"5.000 OUTROS","valor":"143360.00","numeroLicitacao":"18.00","ano":"2026.00","vigenciaInicio":{"date":"2026-08-19 ..."},"vigenciaFim":{...},"numeroContrato":"22553731000105.00","anoLicitacao":"2026.00"}
  ```
  Números vêm como string com ".00"; `numeroContrato` repete o CNPJ (campo defeituoso), `cpfCnpj` perde o zero à esquerda (restaurar e validar via `fornecedores.documento`). `objeto` às vezes só "5.000 OUTROS". Id estável: `ctr_` sobre `cpfCnpj|numeroLicitacao|anoLicitacao|vigenciaInicio` (sem número de contrato confiável).
- `GET /api/v1/licitacoes/?formato=json`: 200, 258 KB (processo, modalidade, objeto, situação, total adjudicado). Complementa com o objeto real. Também `https://www.alepe.pe.gov.br/licitacoes/list.php?v=2&` (JSON `{"data":[...]}`, campos `NUMEROPROCESSO, ANOPROCESSO, NOMEMODALIDADE, OBJETOCONFORMEEDITAL, SITUACAOLICITACAO, QTD_EMPRESAS, TOTAL_ADJUDICADO`) e `licitacoes/list.php?ID=<n>` (detalhe).
- Outras URLs do portal vistas no bundle: `https://www.alepe.pe.gov.br/contratos/list.php?pagina=` e `?ID=`, `contratos/aditivos/list.php?anocontrato=`. `contratos/export.php` retorna HTTP 500 (CSV quebrado hoje).
- Atas de registro de preço: tela `/financas/atas-registro-preco` na SPA; o endpoint não apareceu como string no bundle (provavelmente `licitacoes/list.php` com filtro de modalidade). Não confirmado: precisa abrir a tela no navegador e ver a rede. Esforço médio.
- Sem filtro de data; baixar inteiro (poucos KB) todo dia é aceitável.

## Presença em plenário - ENCONTRADO, esforço médio
- Listagem: `GET https://www.alepe.pe.gov.br/reunioes/?pagina=N` (HTML, ~33 páginas; filtro por data pelo campo `field-filter-data`, parâmetro não confirmado). Cada linha: data, nº de ordem, tipo (ORDINÁRIA, EXTRAORDINÁRIA, SOLENE) e links `/expediente/?docid=`, `/atas/?docid=`, `/frequencia/?docid=`.
- Frequência: `GET https://www.alepe.pe.gov.br/frequencia/?docid=2980` (HTML, ~1,5 KB, charset ISO-8859-1). Blocos: "Deputados Faltosos (Total n)", "em Missão Autorizada", "Licenciados", "Presentes", cada um com nome e partido:
  ```
  82ª REUNIÃO ORDINÁRIA ... REALIZADA quarta-feira, 28/10/2026 | Faltosos Total 0 | Missão Autorizada: Abimael Santos PL, ... Total 27 | Licenciados: Rosa Amorim PT | Presentes: Adalto Santos PP, ...
  ```
- Liga só por nome+partido (`nome+partido`), sem id. Leitura incremental: listagem é da mais nova para a mais antiga; ler páginas até a data da coleta anterior. Volume: ~80 reuniões/ano, uma requisição por reunião.
- Risco: "Missão Autorizada" é ausência justificada (separar de falta); encoding ISO-8859-1.

## Atas e expedientes (links) - ENCONTRADO, esforço baixo
- `https://www.alepe.pe.gov.br/atas/?docid=N` (HTML com texto integral; botão "Exportar em PDF"); `https://www.alepe.pe.gov.br/expediente/?docid=N` (pareceres e proposições lidas na reunião, com página do Diário Oficial). Ambos saem da listagem `/reunioes/`. Texto da ata lista os deputados presentes por nome (confere com a frequência) e não traz votos nominais.
- Pauta propriamente dita (ordem do dia antecipada): não há página; o expediente é publicado depois da reunião.

## Normas legais com autoria - ENCONTRADO, esforço médio-alto
- `https://legis.alepe.pe.gov.br/lista.aspx?tiponorma=<n>` (HTML ASP.NET, 825 KB, sem login): 1 Leis Ordinárias, 2 Complementares, 4 Resoluções da Alepe, 5 Decretos Legislativos, 6 Decretos do Executivo, 13 Emendas Constitucionais, 11 Decretos-Lei, 7/15/8 atos administrativos. Ano via `ctl00$conteudo$ddlAno` (postback com `__VIEWSTATE`/`__EVENTVALIDATION`, padrão WebForms; GET sem ano traz o ano corrente, 189 itens em Leis Ordinárias 2026).
- Detalhe: `texto.aspx?id=<id>` (texto, traz "AUTORIA DO DEPUTADO ANTÔNIO MORAES - PSD") e `dadosReferenciais.aspx?id=<id>` (Data, Ementa, Proposição "PROJETO DE LEI ORDINÁRIA 4236/2026", Publicação no DOE). Há `arquivoTexto.aspx?tiponorma=&numero=&ano=&complemento=0`.
- Liga ao deputado por nome+partido no texto de autoria (nem todas as normas são de deputado: autoria do Executivo/Mesa/TJ). Liga também à proposição pelo número (PL nnnn/AAAA) que o coletor já tem. Uma requisição por norma (~190 leis/ano) mais a listagem; exige ritmo lento. Risco: HTML frágil, postback para anos antigos.

## Votação nominal - NÃO PUBLICA
Nenhuma página `/votacao`, nenhum endpoint no bundle da transparência, nenhum "nominal" na ata testada (só "submetidas à discussão e à votação, aprovadas"). O sistema legislativo interno (legis) só serve normas. Não há fonte aberta.

## Diárias - NÃO PUBLICA
Bundle da transparência (menus `/financas/*`, `/pessoal/*`) não tem rota de diárias; `/financas/diarias` devolve a casca da SPA. Verba indenizatória (já coletada) é o único gasto por deputado.

## Remuneração por deputado - NÃO PUBLICA por pessoa
Rota SPA `/financas/remuneracao-ajuda-deputados` existe ("Remuneração e Ajuda de Custo dos Deputados"), mas o endpoint de dados não aparece no bundle como URL; provavelmente tabela fixa (subsídio igual para todos). Conferir abrindo a tela no navegador. Fora isso, `api/v1/remuneracao/` só por cargo.

## Observações
- `https://dadosabertos.alepe.pe.gov.br/` lista 7 APIs: parlamentares, cargos, lotacoes, servidores, remuneracao, licitacoes, contratos (proposições à parte). Todas aceitam `?formato=json|csv`.
- Registrar em `ENDPOINTS.md`: `api/v1/servidores`, `api/v1/contratos`, `api/v1/licitacoes`, `www.alepe.pe.gov.br/reunioes|frequencia|atas|expediente`, `legis.alepe.pe.gov.br`.
- Ordem sugerida: gabinete (servidores) e contratos (baixo), depois presença/atas, depois normas.
