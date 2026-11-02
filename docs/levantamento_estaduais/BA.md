# BA (ALBA) - pesquisa de endpoints equivalentes ao coletor do PR

Amostras em `.../scratchpad/pesquisa/ba/` (e arquivos soltos na pasta pesquisa). Todos os testes: GET, sem captcha/login, exceto onde indicado. Páginas do site em `www.al.ba.gov.br` respondem em cp1252/utf-8 misto (usar `decodificar`).

## Resumo
| Item PR | Status BA |
|---|---|
| deputados | JÁ TEM |
| proposições | JÁ TEM |
| normas legais com autoria | NÃO PUBLICA (só atos administrativos da Mesa, PDF, sem autoria) |
| votação nominal | BLOQUEADO (NoPaper/Cloudflare 403) |
| presença em plenário | ENCONTRADO (por sessão e deputado, só até 18/06/2025) |
| diárias | ENCONTRADO, mas só servidores (nenhum deputado) |
| remuneração | NÃO PUBLICA por deputado (subsídio único em PDF: R$ 34.774,64) |
| gabinete | NÃO PUBLICA (só tabela salarial SP em PDF) |
| pautas e atas | ENCONTRADO parcial (PDF do texto da sessão até 06/2025; ordem do dia até 17/06/2025) |
| contratos | ENCONTRADO (HTML paginado, 2023 a hoje) |
| atas de registro de preço | PARCIAL (licitações com objeto "REGISTRO DE PREÇOS"; sem ata nem CNPJ) |
| regras/PDF do ressarcimento | ENCONTRADO (8 PDFs de normas da verba indenizatória) |
| verba indenizatória, emendas | JÁ TEM |

## JÁ TEM (coletor atual)
Deputados (HTML), verba indenizatória (Excel anual), proposições (lista por tipo + detalhe), emendas parlamentares (CKAN, despesas e pagamentos). Arquivos em `dados/estaduais/BA/`: deputados, emendas_*, ligacoes, materias_2023-2025, pagamentos_2026, verbas_2023-2026.

## Presença em plenário - ENCONTRADO (esforço baixo/médio)
- Lista de sessões: `GET https://www.al.ba.gov.br/atividade-legislativa/sessoes-plenarias?dataInicio=2023-01-01&dataFim=2025-12-31&page=<0..>`; HTML, 20 por página fixo (`size` ignorado), ~25 páginas para 2023-2025, ordem decrescente; paginação por links `?...&page=N&size=20`. Filtros: `dataInicio`, `dataFim` (ISO), `numero`, `tipo`.
- Cada linha: nº da sessão, tipo (Ordinária/Extraordinária/...), data, link do PDF do texto (`/fserver/:imagensAlbanet:PDFsSessao:splena_18062025_52a_Ord%20.pdf`), vídeos por orador, e link `/atividade-legislativa/frequencia-sessao/<idSessao>` (ex.: 6420 = 52ª ordinária de 18/06/2025).
- `GET /atividade-legislativa/frequencia-sessao/6420`: HTML com cabeçalho "52ª Sessão Ordinária - 18/06/2025 às 14:07" e tabela DEPUTADO | PRESENÇA (Sim/Não), 63 linhas, nome parlamentar (sem id; ligar via `identidades.ligar_nomes`). Exemplo: `Adolfo Menezes | Não`, `Alan Sanches | Sim`.
- Cobertura: sessões de 2021 até 18/06/2025. A página avisa que após 01/08/2025 o conteúdo migrou ao NoPaper (403). Ou seja, não há presença de 07/2025 em diante (2025 parcial, 2026 inexistente).
- Incremental: filtro `dataInicio`; sessão com id já lido não é relida. Volume: ~500 sessões x 1 GET (pausa 1 s) na primeira carga.
- Riscos: dado congelado em 06/2025; id da frequência não é sequencial garantido (id 4000 deu 302), usar só os ids dos links.

## Atas / textos das sessões - ENCONTRADO parcial (baixo)
- Mesmo endpoint de sessões acima; coluna "Textos" = PDF (taquigrafia) por sessão (`pdftotext` mostra "SESSÕES DO PLENÁRIO ... comparecimento dos deputados: ..."). Serve como link de ata; não traz votos nominais (0 ocorrências de "votação" no exemplo).
- Ordem do dia: `GET /atividade-legislativa-nova/ordem-do-dia?dataInicio=&dataFim=&numero=&palavra=` lista (tipo, data, link detalhe); detalhe `/atividade-legislativa-nova/ordem-do-dia/<n>/<dd-mm-aaaa>/<Tipo>` traz tabela proposição (PL./25776/2025), tipo, autor, ementa, links Texto/Emenda/Parecer. Último dia: 17/06/2025.
- Pauta: `/atividade-legislativa-nova/pauta` e `/pauta-historico` e `/parecer` (páginas HTML; pauta vigente vazia, conteúdo atual no NoPaper). Pauta de comissões: `/comissoes/resumo-pauta`, composição `/comissoes/composicao/<id>` (não testado a fundo).
- Relatórios estatísticos anuais da taquigrafia (agregado, sem por-deputado): `https://www.al.ba.gov.br/transparencia/relat-atividades-legislativas` -> `/fserver/:imagensAlbanet:upload:Sessoes_Plenarias_2026.pdf` (1,7 MB, até 30/04/2026), `..._2025`, `Detaq_2024`, `..._2023` etc.

## Contratos - ENCONTRADO (esforço baixo)
- `GET https://www.al.ba.gov.br/transparencia/contratos-convenios?dataInicio=2023-01-01&dataFim=2026-12-31&page=0&size=200` -> HTML; `size=200` funcionou e devolveu 182 linhas (2023 até 01/11/2026) numa página só. Demais filtros: `modalidade`, `empresa`, `situacao` (Ativo, Encerrado, Estornado, Suspenso...).
- Linha: nº/ano (037/2026), data, empresa (razão social, sem CNPJ), modalidade (Pregão Eletrônico, Dispensa, "Adesão a Registro de Preço - ..."), situação, valor (R$ 37.859,49), aditivos, anexo (link, geralmente "--"). Link do detalhe `/transparencia/contratos-convenios/detalhar/110100012600000433` (id do contrato; HTML com objeto e vigência `01/11/2026 à 31/10/2027`).
- Excel oficial: form GET para `https://apiportalscd.al.ba.gov.br/scd/contratos-convenios/portal/excel` -> de fora do navegador ficou pendurado (timeout 90 s); não usar. HTML basta.
- Outros: `/transparencia/contratos-convenios/fiscais-contratos` (fiscais), `/pagamento-cronologico` (por exercício 2018-2026 e unidade orçamentária 1101/1201, form + Excel/PDF), `/transparencia/credor-empenho-despesa` e `/transparencia/contrato-sintetico` (despesa por credor, exercício 2018-2026, não explorados a fundo).
- Risco: fornecedor só por nome (usar `fornecedores.nome_chave`); sem CNPJ na lista. Verificar no detalhe se há CNPJ (o exemplo não tem). Contrato é do órgão, não do deputado.
- Incremental: `dataInicio` = último dia lido; ou reler tudo (1 GET).

## Atas de registro de preço / licitações - PARCIAL (baixo)
- `GET https://licita.alba.ba.gov.br/licitacoes-externo` (HTML 354 KB, dados num array JS inline: nº, objeto, modalidade, data, valor, situação, link `/licitacao/<id>/ver-edital`). Registros desde 20/12/2022; 29 com "REGISTRO DE PREÇOS" no objeto (Pregão Eletrônico/Registro de Preço). Atas em si não listadas; edital em `.../licitacao/<id>/ver-edital`. Contratos com modalidade "Adesão a Registro de Preço" no portal de contratos acima cobrem o lado contratado.
- Risco: parse do array JS; sem CNPJ.

## Diárias - ENCONTRADO, mas sem deputados (esforço baixo, valor baixo)
- `GET https://portalrh.alba.ba.gov.br/transparencia-troca/0` com cabeçalho `X-Requested-With: XMLHttpRequest` e parâmetros DataTables serverSide (`draw=1&start=0&length=1000&order[0][column]=0&order[0][dir]=asc&search[value]=&search[regex]=false&columns[i][data]=<nome|cadastro|simbolo|cargo_funcao|lotacao|roteiro|dt_partida|dt_retorno|qtd_diarias|valor_diaria|valor_total|id>&columns[i][searchable]=true&columns[i][orderable]=true` + `year=2025&month=06`). Sem os `columns[...]` dá HTTP 500 (mês com dados) ou lista vazia.
- Resposta JSON: `{"recordsTotal":6,"data":[{"id":"1009","nome":"FERNANDA WATT DE ALENCAR GUEDES","cadastro":"924037","simbolo":"FC07","lotacao":"DIR DA ESCOLA DO LEGISLATIVO","cargo_funcao":"DIRETOR","roteiro":"Salvador - BA // Natal - RN // Salvador - BA","dt_partida":"04/06/2025","dt_retorno":"06/06/2025","qtd_diarias":"2","valor_diaria":"R$ 1.620,00","valor_total":"R$ 3.240,00"}]}`.
- Cobertura: 2019 até 05/2026 (junho a outubro/2026 vazios hoje). Varri 2025-01 a 2026-10 (22 GETs): 261 linhas, nenhum deputado (cargos de servidores: assessor técnico, diretor...; lotação sem "GAB"). Aba militar: `transparencia-troca/1` (500 sem params). Detalhe: `/transparencia/diarias-pagas/<id>/get-data` (500 nos testes).
- Conclusão: não há diária de deputado; só serve como dado do órgão. Tabela de valores: `https://portalrh.alba.ba.gov.br/pdf/transparencia/ALBA_Tabela_Valores_Diarias.pdf`.

## Remuneração - NÃO PUBLICA por deputado
- `https://portalrh.alba.ba.gov.br/pdf/transparencia/ALBA_ECV_Deputados.pdf`: "Subsídio dos Deputados Estaduais, Lei nº 14.532, de 16/01/2023: 34.774,64" (valor único; pode virar constante com link para a fonte). Sem folha por deputado; "Validar Contracheque" exige documento.
- Servidores (JSON, sem login): `GET https://portalrh.alba.ba.gov.br/transparencia/0` (efetivos, 336 linhas) e `/transparencia/1` (função comissionada, 235), campos `cadastro, name, lotacao, cargoFuncao, dataNomeacao, dataDemissao, simbolo, mediaHotasSemanal`; sem salário (só símbolo; tabela por símbolo em PDF). `/transparencia/2..6` dá 500.

## Gabinete - NÃO PUBLICA
- Lotações em `/transparencia/0` e `/1` não incluem gabinete de deputado (nenhum "GAB"/nome de deputado; só Presidência, Diretoria Parlamentar, Liderança da Maioria...). Secretário Parlamentar: só `https://portalrh.alba.ba.gov.br/pdf/transparencia/ALBA_ECV_SP.pdf` (tabela salarial SP-13 a SP-17B, Resolução 1.287/2001), sem nomes. Estagiários: `/transparencia/estagiarios` (não explorado; sem deputado).

## Votação nominal - BLOQUEADO
- NoPaper (`albalegis.nopapercloud.com.br/spl/...`, `alba.nopapercloud.app`) retorna 403 Cloudflare (confirmado agora com curl). Nenhum espelho no site da ALBA nem no CKAN `dados.ba.gov.br` (busca por assembleia/alba/deputado/legislativ: 0 conjuntos). PDFs de sessão não trazem voto nominal.

## Normas legais - NÃO PUBLICA como no PR
- `GET /transparencia/legislacao-transp?exercicio=2025&palavra=` (HTML, 20 por página): só atos administrativos da Mesa/Presidência (ex.: "2025 - RESOLUÇÃO DA MESA DIRETORA Nº 148/2025", "ATO DA PRESIDÊNCIA Nº 6740/2025") com PDF; sem autoria de deputado. Leis estaduais e decretos legislativos: aparecem como proposição no coletor atual (situação/ementa); o número da lei sai do detalhe da proposição, a verificar no coletor.

## Ressarcimento (verba): regras/PDF - ENCONTRADO (baixo)
- `GET https://www.al.ba.gov.br/transparencia/verbas-regula?exercicio=<ano>` lista 8 normas: Resolução 1.316/2003, Ato da Presidência 21.527/2003, Resolução 1.391/2006, Ato da Mesa 08/2012 (011/2014), 17/2016, 18/2017, 25/2020, Resolução 2.110/2023 (saldo da verba dentro do ano fiscal). PDFs em `/fserver/:imagensAlbanet:upload:01-resolucao_mesa-1316_2003.pdf` ... `08-resolucao_presidencia_2110-2023.pdf`. Basta um dicionário de links como fonte de regras.
- Verba (já coletada): `https://www.al.ba.gov.br/transparencia/verbas-idenizatorias-excel?ano=2026`.

## Prioridade sugerida
1. Presença por sessão (valor alto, 2021 até 06/2025; avisar que 07/2025 em diante é NoPaper).
2. Contratos do órgão (1 GET, `size=200`).
3. Links de regras da verba e textos de sessão (PDF) como fonte.
4. Licitações/registro de preço (array JS inline), opcional.
Não vale coletar: diárias (sem deputado), remuneração/gabinete (não publicados), votação (bloqueada).

## ENDPOINTS.md (se implementar)
Hosts novos: `portalrh.alba.ba.gov.br` (só se coletar servidores/diárias), `licita.alba.ba.gov.br`, `apiportalscd.al.ba.gov.br` (não usar). `www.al.ba.gov.br` já está.
