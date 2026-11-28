# Levantamento: vereadores em exercício em dados abertos de Tribunais de Contas (2ª rodada)

Data dos testes: 2026-11-28. Somente leitura (web e curl, amostras pequenas). "NÃO VERIFICADO" = não consegui abrir ou não achei documentação; não significa que a fonte não existe. Falhas de conexão (HTTP 000, ECONNREFUSED, timeout) em vários hosts `.tc.br`/`.gov.br` podem ser bloqueio de rede deste ambiente (AM, PB, RN respondiam normalmente): vale repetir os NÃO VERIFICADOS de uma rede brasileira.

Objetivo: fonte oficial com vereadores em exercício (inclui suplentes que assumiram) por município, com nome, partido e posse/afastamento. Hoje o site só tem os eleitos de 2024 do TSE.

## Resultado em uma tabela

| Situação | Quantos | Quais |
|---|---|---|
| Tem lista de vereadores (nome, cargo, datas) | 2 UFs | PE, PB |
| Verificado, sem lista de vereadores | 15 UFs + TCM-SP + TCM-GO | AM, CE, DF, ES, GO, MA, PI, PR, RJ, RN, RS, SC, SE, SP, TO; TCM-SP; TCM-GO |
| NÃO VERIFICADO (sem acesso a partir deste ambiente; repetido na 4ª rodada) | 10 UFs + 4 TCMs | AC, AL, AP, BA, MG, MS, MT, PA, RO, RR; TCM-BA, TCM-PA, TCM-Rio, TCM-CE |

Repetição de 2026-11-28 (3ª rodada, mesma rede): PI, PR e TO passaram a verificados sem lista; os demais seguem sem conexão (timeout, ECONNREFUSED, 403 de WAF/Cloudflare), então não foi implementado coletor novo. Repetir de rede brasileira; PE e PB continuam as únicas fontes com lista.

Nenhuma fonte nacional publica vereador em exercício. Nenhum dos dois tribunais com lista traz partido: o partido vem do TSE.

## UF com lista de vereadores

### PE: TCE-PE, API Dados Abertos (Sagres Pessoal), `ListaServidores` (verificado na 1ª rodada, mantido)
- URL: `https://sistemas.tce.pe.gov.br/DadosAbertos/ListaServidores!json?NomeCargo=VEREADOR` (também `!xml`, `!html`). Sem chave nem cadastro. HTTP 200, 4,9 MB, 8.859 linhas (limite de 100.000 por chamada).
- Campos: UnidadeJurisdicionadaTCE, NomeUJ (ex.: "Câmara Municipal de Afogados da Ingazeira"), HashCPFPessoa, CPFServidor mascarado (`***.212.314-**`), NomeServidor, Matricula, NomeCargo, NomeTipoVinculo (`Eletivo`), DataAdmissao, DataIngresso, DataAfastamento, TipoAtoPessoalIngresso/Afastamento, AnoRemessa, MesRemessa. Sem partido.
- Amostra: `Abreu e Lima | MARIA SALOME DE ARAUJO | VEREADOR | Eletivo | 2017-01-01 | 2020-12-31`; `Afogados da Ingazeira | JOSE RAIMUNDO LIMA SANTOS | VEREADOR | Eletivo | 2021-01-01 | 2024-12-31`.
- Cobertura: 189 UJ distintas. Traz mandatos de vários períodos com ingresso e afastamento, então dá para ver quem assumiu no meio do mandato. Cargo sujo (125 grafias distintas): precisa normalizar. O filtro `NomeCargo=VEREADOR` é "contém". Mandato em curso: `DataAfastamento` ausente; 1.892 linhas com ingresso em 2025 (ingresso fora de 01/01/2025 sugere suplente; validar contra o TSE).
- Atualização mensal (remessa 2026/10 nas amostras). Esforço baixo. Risco: cargo sujo; ligação por nome e CPF mascarado (6 dígitos centrais).

### PB: TCE-PB, arquivos de servidores no bucket público (novo nesta rodada)
- Portal: `https://dados-abertos.tce.pb.gov.br/` (HTTP 200, SPA React; `dados.tce.pb.gov.br` redireciona para ele). Não há API REST: o JS do portal (`/assets/index-Cq25HyE6.js`, HTTP 200, 488 KB) aponta para um bucket S3/MinIO público `https://download.tce.pb.gov.br/dados-abertos/`, listável sem chave: `?list-type=2&delimiter=/&prefix=<prefixo>/` (HTTP 200). Raiz: `dados-consolidados/` (despesas, licitacoes, receitas, servidores), `dados-por-municipio/`, `portais-auditoria/`, `portal-upas/`.
- Conjuntos: `dados-consolidados/servidores/servidores-AAAA.zip` (2013 a 2026, 59 a 112 MB cada) e `dados-por-municipio/<código 3 dígitos>/servidores/servidores-AAAA.zip` (223 prefixos de município).
- Formato: ZIP com um CSV (`;`, UTF-8 com BOM). Campos: nome_municipio, codigo_unidade_gestora, descricao_unidade_gestora (ex.: "Câmara Municipal de Água Branca"), cpf_cnpj, nome_servidor, tipo_cargo (`Eletivos`), descricao_cargo (`00000001 - VEREADOR`, `00000002 - VEREADOR PRESIDENTE`), valor_vantagem, data_admissao (DD/MM/AAAA), matricula, ano_mes. Sem partido, sem data de afastamento.
- Teste: `dados-por-municipio/001/servidores/servidores-2026.zip`, HTTP 200, 237.978 B (acima das 20 linhas pedidas; é o menor arquivo útil), CSV de 1,78 MB com 8.667 linhas, das quais 90 de VEREADOR = 9 matrículas x 10 meses (202601 a 202610), todas `Eletivos`. Exemplo (nome e CPF omitidos): `Água Branca; 101001; Câmara Municipal de Água Branca; ...; Eletivos; 00000001 - VEREADOR; 6.000; 01/01/2025; 000000000000056; 202601`.
- Cobertura: 223 municípios (prefixos do bucket; não confirmei Câmara em todo ano). Atualização mensal. Sem chave.
- Esforço baixo a médio (um ZIP por município/ano ou o consolidado de ~84 MB em 2026). Risco: é folha mensal, então suplente que assume é inferido pela primeira e última aparição em `ano_mes`; `data_admissao` da amostra é 01/01/2025 para todos; o CPF vem completo (dado pessoal, não guardar); sem partido.

## Tabela por UF e TCM

| UF / tribunal | Fonte e URL | Formato | O que traz | Cobertura | Esforço | Risco | Status |
|---|---|---|---|---|---|---|---|
| PE | TCE-PE `ListaServidores` (ver acima) | JSON/XML | nome, cargo, ingresso, afastamento; sem partido | PE | baixo | cargo sujo | VERIFICADO, com lista |
| PB | TCE-PB bucket `download.tce.pb.gov.br/dados-abertos/` (ver acima) | ZIP/CSV | nome, cargo, admissão, folha mensal; sem partido | 223 municípios | baixo/médio | CPF completo, inferência por mês | VERIFICADO, com lista |
| AM | TCE-AM `https://econtasapi.tce.am.gov.br/v3/api-docs` (HTTP 200, 42 KB, OpenAPI) | JSON | pagamentos, empenhos, contratos etc.; `lotaciograma` é do próprio TCE; `/unidades` HTTP 200 com 468 unidades, 0 Câmaras | AM | n/a | n/a | VERIFICADO, sem lista |
| CE | TCE-CE API SIM `https://api-dados-abertos.tce.ce.gov.br/sim/` (OpenAPI `openapi_prod.yaml`, 200, 436 KB) | JSON | `/agentes_publicos_municipais`: município, órgão, `cpf_servidor` completo, `codigo_vinculo`, nomeação. SEM nome, partido, cargo, datas | 185 municípios, inclui Fortaleza (057) | médio | sem nome; ligar só por CPF, que o TSE não publica aberto | VERIFICADO, sem lista. Endpoint `agentes_publicos_folha`: NÃO VERIFICADO (HTTP 000) |
| MA | TCE-MA `https://tce-api.apps.tcema.tc.br/v3/api-docs` (200, 121 KB, 307 caminhos) | JSON | `/sincfolha/{ano}/servidor`, `cargofuncao`, `matriculaservidor`, `movimentacaoservidor`, `remuneracao`: CPF mascarado, código de cargo, movimentação; SEM nome, partido. Cargo "VEREADOR" existe em `cargofuncao` | MA, estado e municípios | alto | sem nome; Bearer declarado mas os GET responderam 200 sem token (pode mudar) | VERIFICADO, sem lista |
| ES | TCE-ES `https://www.tcees.tc.br/portal-da-transparencia/dados-abertos/` e CKAN `https://dados.es.gov.br/` (`package_search` "vereador" e "agentes politicos" = 0) | CKAN | só gestão do próprio TCE e finanças municipais. API CidadES é de remessa por jurisdicionado, não aberta | ES | alto | alto | VERIFICADO, sem lista. Painel de Controle `paineldecontrole.tcees.tc.br`: NÃO VERIFICADO (SPA sem endpoint achado) |
| GO (TCM-GO) | `https://www.tcmgo.tc.br/site/transparencia/subsidio-dos-agentes-politicos/`; XLSX `.../Subsidios-Legislatura-2025-2028.xlsx` (HEAD 200, 33.394 B) | XLSX | município, cargo (Vereador etc.), subsídio, lei, processo. SEM nome, partido | municípios de GO | baixo (só subsídio) | não resolve pessoas | VERIFICADO, sem lista |
| GO (TCE-GO) | busca web sem portal de dados abertos de municípios (TCE-GO não audita municípios) | n/a | n/a | n/a | n/a | n/a | NÃO VERIFICADO |
| DF (TCDF) | `https://unidades.tc.df.gov.br/distribuicao-de-processos/dados-abertos/` (200): APIs de distribuição de processos | JSON | processos do próprio TCDF | DF | n/a | DF não tem Câmara Municipal | VERIFICADO, sem lista |
| RJ (TCE-RJ) | `https://dados.tcerj.tc.br/api/v1/` (OpenAPI 200, 100 KB, sem chave), rota `/situacao_funcional?ano=2025&municipio=Niteroi` (200) | JSON/CSV | AGREGADO: unidade gestora, mês, quantidade e remuneração de "Agente Político" (ex.: `CAMARA NITEROI`, 23). SEM nome, partido | municípios do RJ | baixo (só contagem) | n/a | VERIFICADO, sem lista. Serve para conferir o número de vereadores por Câmara/mês |
| RJ (TCM-Rio) | `https://www.tcmrio.tc.br/` (200); Power BI e Portal da Transparência não abertos | n/a | n/a | só a capital | n/a | n/a | NÃO VERIFICADO (Power BI renderiza em JS) |
| RN | `https://apidadosabertos.tce.rn.gov.br/swagger/docs/v1` (200, 11 KB) | CSV/JSON/HTML | jurisdicionados, balanço, licitações, empenhos, contratos; nenhuma rota de pessoal | RN | n/a | n/a | VERIFICADO, sem lista |
| RS | TCE-RS CKAN (1ª rodada): `package_search` "vereador" e "agente" = 0 | CKAN | sem lista | RS | n/a | n/a | VERIFICADO, sem lista |
| SC | `https://www.tcesc.tc.br/apis-dados-abertos`: só `municipios.php` (200, 17.462 B) e `unidades-gestoras.php` (200, 435.044 B), cadastro. e-Sfinge de acesso restrito | JSON | código e nome de município/unidade | 295 municípios | n/a | curl direto recebe 403 (Akamai); só funcionou por navegador real | VERIFICADO, sem lista |
| SE | `https://www.tce.se.gov.br/visualizadorRelatorios/swagger/docs/v1` (200, 1.517 B): Contratos, Despesas, Receitas | JSON | nenhum endpoint de pessoal | SE | n/a | n/a | VERIFICADO, sem lista |
| SP (TCE) | `https://transparencia.tce.sp.gov.br/conjunto-de-dados` (200) e `/apis` (200) | CSV/SQL, JSON | despesas, receitas, RCL, dívida ativa, licitações; nada de pessoal. "Mapa das Câmaras" (`camarasmunicipais`) redirecionou para aviso de painéis indisponíveis em 2026-11-28 | 644 municípios | n/a | n/a | VERIFICADO, sem lista |
| SP (TCM-SP) | `https://iris.tcm.sp.gov.br/dadosAbertos.html` (200) | CSV zip, API | receita, dotação, empenho da capital; sem pessoal | só a capital | n/a | n/a | VERIFICADO, sem lista |
| AC | `www.tceac.tc.br` citado em notícia; curl HTTP 000 (timeout 22 s) | n/a | pista: sistema e-TCE e SICAP, sem endpoint público documentado | n/a | n/a | n/a | NÃO VERIFICADO (sem conexão, sem documentação) |
| AL | `www.tceal.tc.br` (só PDFs em buscas); curl e WebFetch: conexão recusada | n/a | n/a | n/a | n/a | n/a | NÃO VERIFICADO (conexão recusada) |
| AP | `https://www.tce.ap.gov.br/portal-da-transparencia` (da busca); ECONNREFUSED | n/a | n/a | n/a | n/a | n/a | NÃO VERIFICADO (conexão recusada) |
| BA (TCE) | nenhum portal achado em 3 buscas | n/a | n/a | n/a | n/a | n/a | NÃO VERIFICADO (sem documentação) |
| BA (TCM) | `e.tcm.ba.gov.br` e `tcm.ba.gov.br`: conexão recusada/timeout. Via SEI-BA (`ba.gov.br/sei/bfp-financas-publicas`) só gasto com pessoal agregado, planilhas não abertas | n/a | n/a | n/a | n/a | n/a | NÃO VERIFICADO (conexão recusada) |
| MG | `https://dadosabertos.tce.mg.gov.br/` e CAPMG `https://capmg.tce.mg.gov.br/`, links do site oficial (200); ambos sem conexão (curl 000, ECONNREFUSED, ERR_CONNECTION_TIMED_OUT) | n/a | notícia do tribunal cita consulta de folha de agentes públicos dos municípios | n/a | n/a | n/a | NÃO VERIFICADO (rede; candidata prioritária para repetir de IP brasileiro: MG tem 853 municípios) |
| MS | `tce.ms.gov.br`: curl 000; só resoluções do e-Sfinge | n/a | n/a | n/a | n/a | n/a | NÃO VERIFICADO (sem conexão) |
| MT | `www.tce.mt.gov.br`: curl 000; só documentos do APLIC | n/a | n/a | n/a | n/a | n/a | NÃO VERIFICADO (sem conexão) |
| PA (TCE) | `www.tcepa.tc.br`: curl com 0 B; resolução (DOE 2026-06-03) sobre remessa de folha, não publicação | n/a | n/a | n/a | n/a | n/a | NÃO VERIFICADO (sem conexão) |
| PA (TCM) | `https://www.tcmpa.tc.br/` HTTP 403 (Cloudflare) | n/a | n/a | n/a | n/a | n/a | NÃO VERIFICADO (bloqueio) |
| PR | `https://pit.tce.pr.gov.br/Dados/DadosConsulta/Consulta` (200, exige login/SPA); link antigo `www1.tce.pr.gov.br/...dados-abertos...` 404; regras de uso em PDF (200) exigem aceite | n/a | SIAP-Folha recebe folha municipal, publicação aberta não confirmada | n/a | n/a | n/a | NÃO VERIFICADO (portal exige aceite/JS) |
| PI | `https://www.tcepi.tc.br/portaldacidadania/dados-abertos` (200, SPA que exige JavaScript) | n/a | n/a | n/a | n/a | n/a | NÃO VERIFICADO (JS; repetir com navegador) |
| RO | `https://www.tcero.tc.br` HTTP 403 | n/a | n/a | n/a | n/a | n/a | NÃO VERIFICADO (bloqueio 403) |
| RR | `https://www.tcerr.tc.br/`: timeout 30 s no curl e no navegador do Kedalion | n/a | n/a | n/a | n/a | n/a | NÃO VERIFICADO (timeout) |
| TO | `https://www.tceto.tc.br/` (200); `transparencia.tceto.tc.br` (200) só do próprio tribunal; SICAP-AP é de remessa; módulo externo `app.tceto.tc.br/sicap/externo/` exige login | n/a | n/a | n/a | n/a | n/a | NÃO VERIFICADO (sem portal de dados abertos achado; módulo externo com login) |
| TCM-CE | `dataportals.org` lista `https://api.tcm.ce.gov.br/`; host não resolve (DNS) | n/a | n/a | n/a | n/a | n/a | NÃO VERIFICADO (DNS; existência atual não confirmada) |

## 3ª rodada (2026-11-28): resultado dos alvos de maior porte

Testes com curl (--max-time 15 a 30), WebFetch e navegador do Kedalion.

| UF | Resultado | Detalhe |
|---|---|---|
| PI | VERIFICADO, sem lista | OpenAPI `https://www.tcepi.tc.br/portaldacidadania/assets/dados-abertos/docs.json` (servidor `https://sistemas.tce.pi.gov.br`, 53 rotas, aberta por curl, HTTP 200). `/api/portaldacidadania/servidores/{idUG}/{exercicio}/lista` só responde para Prefeituras (Câmaras voltam `[]`); nas 5 prefeituras testadas o vínculo Eletivo é só prefeito, vice e conselheiros tutelares, filtro `cargo=VEREADOR` dá 0. Campos: cargo, cpf mascarado, lotacao, nome, vinculo (sem datas). `/api/portaldacidadania/prefeituras` (224) e `/muralic/api/ugs` (999 UGs, com "CAMARA DE ...") só cadastro. Não varri as 224 prefeituras |
| SC | VERIFICADO, sem lista (mantido) | `apis-dados-abertos` só tem `municipios.php` e `unidades-gestoras.php`; e-Sfinge Captura traz leiautes de remessa; portal de transparência é do próprio TCE; curl segue 403 (Akamai), só o navegador abre |
| PR | VERIFICADO, sem lista | PIT `https://pit.tce.pr.gov.br/Dados/DadosConsulta/Consulta` e `/Consolidado` (HTTP 200, sem login; `<ano>_PIT_TodosArquivos.zip`, 1,0 a 1,4 GB): 9 temas por município (Combustivel, Contrato, Convenio, Despesa, Diarias, Licitacao, Obra, Receita, Relacionamentos), nenhum de pessoal. SIAP-Folha só tem manuais de remessa. Zips não baixados inteiros |
| TO | VERIFICADO, sem lista | Portal do Cidadão `https://portaldocidadao.tceto.tc.br/` (HTTP 200): `getUnidades` e `getDadosAbertos` listam planilhas só contábeis (Credor, Empenho, Pagamento, balancetes); 139 municípios com código IBGE e CNPJ da Câmara. `/portaiscamaras/index` só aponta para os portais de cada Câmara. Credor/Empenho/Pagamento da Câmara poderiam trazer subsídio por pessoa: não verificado |
| MG | NÃO VERIFICADO (sem acesso) | `dadosabertos.tce.mg.gov.br`, `capmg.tce.mg.gov.br` e `fiscalizandocomtce.tce.mg.gov.br` resolvem, mas o TCP expira (curl 28; Kedalion ERR_CONNECTION_TIMED_OUT); o site `www.tce.mg.gov.br` (200) linka para eles |
| MT, MS, BA | NÃO VERIFICADO (sem acesso) | `www.tce.mt.gov.br`, `www.tce.ms.gov.br`, `www.tcm.ba.gov.br`, `www.tce.ba.gov.br`: timeout/ECONNREFUSED. Sem confirmação própria; relatos de terceiros apontam MT só com agregado no Radar e APLIC com senha, MS e-Sfinge só de remessa, TCM-BA com reCAPTCHA por consulta |
| PA | NÃO VERIFICADO (bloqueio) | `www.tcepa.tc.br`: "Request Rejected" (WAF); `www.tcmpa.tc.br`: Cloudflare 403. Painel "vínculos de servidores" do TCM-PA é Power BI (relato de terceiros, não confirmado) |
| AC, AL, AP, RR | NÃO VERIFICADO (sem acesso) | curl 000, ECONNREFUSED ou ERR_CONNECTION_TIMED_OUT; 4 buscas não acharam portal de pessoal municipal |
| RO | NÃO VERIFICADO (bloqueio) | `www.tcero.tc.br` HTTP 403 (curl, WebFetch e navegador). A IN 52/2017 manda as Câmaras publicarem a remuneração em portal próprio, não o TCE |

Conclusão: nenhum coletor novo nesta rodada; `scripts/coletar_vereadores.py` segue com PE e PB. Os timeouts em hosts `.gov.br`/`.tc.br` (github.com e archive.org abrem) indicam bloqueio de rede deste ambiente: repetir MG, MT, MS, BA, PA, AC, AL, AP, RO e RR de rede brasileira antes de descartar.

## 4ª rodada (2026-11-28, rede de Portugal): sem acesso brasileiro

Nenhuma fonte nova de TCE passou a verificada. `curl` com 12 s: MG (`dadosabertos.tce.mg.gov.br`, `capmg.tce.mg.gov.br`), MT, MS, TCM-BA, TCE-BA, AC, AL e AP deram HTTP 000 (timeout ou conexão recusada); o navegador do Kedalion também expirou em MG (ERR_CONNECTION_TIMED_OUT); `ipinfo.io` indicou país PT. RO: 403 (373 B). RR: timeout. TCM-PA: 403 (Cloudflare). TCE-PA `https://www.tcepa.tc.br/`: HTTP 200 (44 KB), mas é só a página de desafio de bot do F5 (`/TSPD/?type=25`, exige JavaScript), sem links; não contornei. Continuam NÃO VERIFICADOS: MG, MT, MS, BA (TCE e TCM), PA (TCE e TCM), AC, AL, AP, RO, RR; repetir de IP brasileiro (ou do navegador do usuário na rede dele). Querido Diário (frente C) não foi levantado: o SAPL cobriu a necessidade por ora.

## SAPL das Câmaras: todas as UFs medidas (2026-11-28)

Medido do zero, em rede de Portugal, uma UF por vez (Câmaras com SAPL / com vereadores / mandatos / erros / tempo): SP 80/66/770/2/137 s; PE 54/44/597/0/87 s; BA 52/35/473/0/64 s; MT 51/41/481/1/96 s; PB 47/39/464/0/69 s; RS 56/41/460/2/228 s; RN 52/40/463/1/73 s; PI 45/35/348/1/99 s; RO 39/35/389/0/46 s; RJ 37/30/428/0/44 s; CE 34/17/316/0/36 s; TO 34/28/280/0/67 s; GO 30/19/238/1/68 s; SC 26/18/191/0/145 s; AM 25/14/185/0/44 s; ES 24/19/194/1/49 s; PA 18/10/137/0/28 s; MA 13/9/112/0/25 s; AC 14/4/55/0/19 s; MS 12/9/115/0/22 s; AP 10/3/38/0/26 s; AL 7/6/78/0/32 s; RR 5/5/74/0/15 s; SE 3/2/28/0/15 s; MG 205/162/1.773/2/452 s; PR 163/141/1.493/1/252 s. Total das 26 UFs: cerca de 37 min do zero (2.238 s somados); com tudo em cache, 2 s. Nenhuma UF passou de 8 min; a maior, MG, cabe em um passo de 25 min.

Erros (12 Câmaras): 9 de DNS/conexão (Barra de São Francisco/ES, Cristianópolis/GO, Bonfinópolis de Minas e Patrocínio/MG, União/PI, Ivatuba/PR, Jardim do Seridó/RN, Nova Prata/RS, Leme/SP), 1 de certificado SSL (Taguaí/SP) e 2 de HTTP 404 na API (Serra Nova Dourada/MT, Rio Grande/RS: instância sem `/api/parlamentares/`). Nenhuma foi por legislatura sem 2025-2028; as Câmaras sem vereadores (instância vazia ou sem a legislatura) não contam como erro.

Coleta diária: `UFS_PADRAO` passou a ter as 26 UFs, em um passo só do job `vereadores`. Como o passo tem prazo de 25 min e a primeira rodada do zero leva cerca de 37, as últimas UFs da lista (as menores) completam na rodada seguinte: o que foi lido fica guardado. Depois disso cada Câmara é relida a cada 7 dias, escalonada, e a rodada com cache é de poucos minutos.

Divergências contra os eleitos do TSE 2024 (MG e PR, ainda por medir nas outras UFs): o filtro `?legislatura=` de algumas instâncias devolve mandatos de outras legislaturas (Ponte Nova/MG: 7 mandatos de 2009-2012), e o coletor descarta mandato com fim antes de 2025-01-01 ou início depois do fim da legislatura (MG: 1.780 -> 1.773 mandatos). Instâncias parciais: Chácara e Grão Mogol/MG com 1 mandato, Rio Azul e Terra Roxa/PR com 3, contra 9 eleitos no TSE. Sem duplicata exata: Muriaé/MG tem o mesmo parlamentar em 2 afastamentos distintos; Cascavel/PR registra suplentes como titular com ingresso posterior. Titulares com ingresso até 2025-01-31 diferentes dos eleitos: MG 10 de 161 Câmaras, PR 30 de 141 (ex.: Bicas/MG e Almirante Tamandaré/PR têm titular na posse que o TSE não lista como eleito). Onde a contagem fecha, cerca de 97% dos nomes batem.

Frente dos TCEs: repetição não feita (rede de Portugal, `ipinfo.io` = PT); continuam sem verificação os mesmos TCEs da 4ª rodada. Querido Diário não levantado.

### Divergências contra o TSE 2024, 24 UFs

Medido sobre as Câmaras com itens e sem erro, contra os eleitos de VEREADOR 2024 do mesmo código TSE (nome civil ou urna; sem acento, caixa e apelido entre parênteses). MG e PR entram para comparação. Colunas: SAPL = Câmaras com SAPL; itens = com mandatos; sem cód. = sem código TSE; parc. = mandatos < cadeiras; dup. = duplicata exata (mesmo nome, parlamentar, ingresso e afastamento); homôn. = nomes com 2 parlamentares distintos; fora TSE = titulares com ingresso até 2025-01-31 sem eleito de mesmo nome (Câmaras afetadas); fecha = Câmaras com titulares na posse = cadeiras (% de nomes que batem); afast. = itens com afastamento; supl. = suplentes (titular falso ou ingresso após 2025-01-31).

| UF | SAPL | itens | sem cód. | parc. | dup. | homôn. | fora TSE (Câmaras) | fecha (% bate) | afast. | supl. |
|---|---|---|---|---|---|---|---|---|---|---|
| AC | 14 | 4 | 0 | 0 | 0 | 0 | 5 (3) | 3 (90.2%) | 20 | 2 |
| AL | 7 | 6 | 0 | 0 | 0 | 0 | 10 (5) | 3 (87.1%) | 4 | 7 |
| AM | 25 | 14 | 0 | 1 | 0 | 0 | 5 (4) | 9 (96.6%) | 7 | 15 |
| AP | 10 | 3 | 0 | 0 | 0 | 0 | 4 (2) | 3 (88.6%) | 0 | 3 |
| BA | 52 | 35 | 0 | 0 | 0 | 2 | 25 (12) | 27 (95.4%) | 20 | 20 |
| CE | 34 | 17 | 0 | 0 | 0 | 0 | 6 (5) | 13 (98.5%) | 77 | 74 |
| ES | 24 | 19 | 0 | 1 | 0 | 1 | 7 (5) | 16 (97.1%) | 1 | 4 |
| GO | 30 | 19 | 0 | 0 | 0 | 1 | 9 (6) | 13 (98.7%) | 7 | 7 |
| MA | 13 | 9 | 0 | 0 | 0 | 0 | 5 (2) | 8 (95.6%) | 4 | 4 |
| MG | 205 | 162 | 0 | 2 | 0 | 0 | 73 (52) | 153 (95.8%) | 35 | 53 |
| MS | 12 | 9 | 0 | 1 | 0 | 0 | 3 (2) | 7 (98.9%) | 3 | 3 |
| MT | 51 | 41 | 0 | 0 | 0 | 2 | 32 (22) | 27 (94.7%) | 31 | 46 |
| PA | 18 | 10 | 1 | 0 | 0 | 0 | 7 (6) | 7 (94.9%) | 0 | 7 |
| PB | 47 | 39 | 0 | 1 | 0 | 0 | 29 (12) | 32 (97.3%) | 35 | 28 |
| PE | 54 | 44 | 0 | 0 | 0 | 0 | 22 (16) | 41 (96.4%) | 21 | 27 |
| PI | 45 | 35 | 1 | 1 | 0 | 1 | 14 (11) | 24 (98.2%) | 7 | 12 |
| PR | 163 | 141 | 0 | 2 | 0 | 9 | 84 (53) | 111 (95.3%) | 81 | 100 |
| RJ | 37 | 30 | 0 | 0 | 0 | 1 | 17 (10) | 24 (97.4%) | 11 | 39 |
| RN | 52 | 40 | 0 | 0 | 0 | 0 | 25 (15) | 35 (95.4%) | 12 | 18 |
| RO | 39 | 35 | 1 | 0 | 0 | 6 | 30 (16) | 27 (93.3%) | 7 | 10 |
| RR | 5 | 5 | 0 | 0 | 0 | 0 | 5 (4) | 3 (95.3%) | 2 | 7 |
| RS | 56 | 41 | 0 | 1 | 0 | 1 | 41 (23) | 23 (95.8%) | 32 | 51 |
| SC | 26 | 18 | 0 | 0 | 0 | 2 | 14 (9) | 13 (94.2%) | 15 | 19 |
| SE | 3 | 2 | 0 | 0 | 0 | 0 | 0 (0) | 2 (100.0%) | 2 | 2 |
| SP | 80 | 66 | 0 | 1 | 0 | 0 | 31 (23) | 57 (96.6%) | 43 | 57 |
| TO | 34 | 28 | 0 | 0 | 0 | 0 | 10 (8) | 24 (98.3%) | 3 | 4 |
| 24 UFs | 768 | 569 | 3 | 7 | 0 | 17 | 356 (221) | 441 (96.3%) | 364 | 466 |

Os nomes de município sem código TSE são 3: Eldorado do Carajás (PA), Caraúbas do Piauí (PI) e Espigão D'Oeste (RO); entram em `GRAFIAS_MUNICIPIO` (conferir a grafia do TSE). A coluna "fora TSE" conta titulares (MG 73, PR 84), não só Câmaras: os "10 de 161" e "30 de 141" acima eram Câmaras sob outro critério e não são comparáveis.

Conclusões para ligar:

- Instância parcial: só 7 em 24 UFs (Novo Airão 3/9, Marilândia 1/9, Rio Brilhante 5/13, Quixaba 7/9, Curral Novo do Piauí 1/9, Pareci Novo 7/9, Agudos 1/13), todas por mandatos < cadeiras. Tratar como parcial quando itens < cadeiras do TSE; ligar o que existe e não deduzir ausência de vereador.
- Duplicata exata: nenhuma nas 24 UFs. Homônimos (2 parlamentares com o mesmo nome na mesma Câmara): 17 casos em 12 Câmaras; não ligar por nome (já é a regra de ambíguo) e separar por `idParlamentar`.
- Ligação esperada: nas 441 Câmaras em que os titulares na posse igualam as cadeiras, 96,3% dos nomes batem com um eleito. Os 3,7% restantes e os 356 titulares fora do TSE (221 Câmaras) são, em geral, eleitos com nome civil/urna diferente ou titulares que não constam como eleitos (convocados antes da posse); não ligar à força, deixar sem ligação.
- Suplentes (466 itens) e afastamentos (364) são frequentes: afastamento preenchido não invalida o titular; suplente sem eleito de mesmo nome ganha pessoa própria, como no PE/PB.

## SAPL das Câmaras: coletor feito (MG e PR)

`scripts/coletar_vereadores_sapl.py` (ver CHANGELOG, 2026-11-28). Descoberta pelo Interlegis lê cards até a página sem cards (a página 2 de MG, por exemplo, só tem casas sem SAPL; parar na primeira página sem SAPL perdia 200 Câmaras). Resultado do zero: MG 205 Câmaras com SAPL registrado, 162 com a legislatura 2025-2028 preenchida (1.780 mandatos; as outras 43 têm instância vazia ou sem a legislatura, 2 delas por erro de DNS); PR 163, 141 com vereadores (1.493 mandatos), 1 erro. Mandatos com `titular` falso: 35 em MG. O resto da lista de UFs do Interlegis roda com `python scripts/coletar_vereadores_sapl.py <UF> ...`; todas as UFs entram no job diário (ver a seção seguinte).

## Fontes nacionais

| Fonte | Teste | O que publica sobre vereador em exercício | Status |
|---|---|---|---|
| TSE candidatos 2024 | `https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2024.zip` (HEAD 200, 78.476.194 B, gerado em 2026-11-28); dataset `candidatos-2024` (200) | Eleitos e suplentes da apuração (`DS_SIT_TOT_TURNO`: ELEITO POR QP/MÉDIA, SUPLENTE, NÃO ELEITO), partido, CPF. Amostra de 400 KB de SE: 351 eleito por QP, 106 por média, 1.766 suplentes. Não diz quem assumiu, renunciou ou saiu; se a coluna muda após a posse: NÃO VERIFICADO | Existe, não responde |
| TSE motivo de cassação 2024 | `.../motivo_cassacao/motivo_cassacao_2024.zip` (200, 601.152 B) | Motivo por `SQ_CANDIDATO` (ex.: fraude à cota de gênero); fala de candidatura/diploma, não de afastamento do cargo | Parcial |
| TSE eleições suplementares 2024 | `.../listaelesuplem/lista_eleicoes_suplementares_2024.zip` (200, 164.065 B) | 43 linhas, nas 3 lidas só Prefeito | Não serve |
| TSE prestação de contas 2024 | dataset `prestacao-de-contas-eleitorais-2024` (200) | contas de campanha, não indica exercício; CSV não baixado | Não serve (por descrição) |
| TSE convocação/posse/diplomação de suplente | `package_list` (200, 190 conjuntos) lido inteiro | nenhum conjunto de convocação, posse ou diplomação | Inexistente no catálogo |
| Querido Diário | `https://api.queridodiario.org.br/gazettes` (200), `openapi.json` v0.19.0 (200) | atos em texto livre de diários municipais. Busca "posse suplente vereador" desde 2025-01-01: 10.000 diários (teto do índice); 1º resultado "ATA DE POSSE DO 2º SUPLENTE DE VEREADOR", Rondonópolis-MT, 2025-11-19. Sem lista estruturada; cobertura de municípios NÃO VERIFICADA | Funciona; sinal complementar, esforço médio/alto |
| CGU Portal da Transparência | API `.../api-de-dados/servidores` HTTP 401 (exige chave por e-mail); `/v3/api-docs` 200; `/peps` com dt_inicio/fim_exercicio | escopo federal pelo esquema; vereador não aparece nos endpoints listados. Download PEP: 302 e depois 403 AccessDenied | Não serve; PEP NÃO VERIFICADO (bloqueio) |
| TCU | `https://sites.tcu.gov.br/dados-abertos/` (200): jurisprudência, normativos, inabilitados/contas irregulares | só responsáveis com contas irregulares; não é lista de exercício. Webservices não chamados | Não serve |
| Atricon, Radar da Transparência | `https://radardatransparencia.atricon.org.br/panel.html` HTTP 403 (Cloudflare) | avalia transparência de portais, não pessoas | NÃO VERIFICADO (bloqueio) |
| SICONFI | `https://apidatalake.tesouro.gov.br/ords/siconfi/tt/entes?an_referencia=2024` (200, 866.548 B) | entes e relatórios fiscais; sem pessoas. Excedeu o limite de amostra (866 KB) | Não serve |
| Cidades Transparentes | `cidadestransparentes.org.br` e `.com.br`: HTTP 000; busca não achou iniciativa com esse nome | n/a | NÃO VERIFICADO (URL não localizada) |
| dados.gov.br | `https://dados.gov.br/dados/api/publico/conjuntos-dados?nomeConjuntoDados=vereadores` HTTP 401 | exige cadastro/token; a página HTTP 200 exige JavaScript | NÃO VERIFICADO (exige cadastro) |

## SAPL das Câmaras como alternativa

Fonte da contagem: diretório oficial Interlegis "Casas Legislativas com SAPL", `https://www12.senado.leg.br/interlegis/orgaosatendidos?servico=SAPL&uf=<UF>&tipocasa=CM&p=<n>` (HTTP 200 nas 27 UFs, 443 páginas, 2026-11-28). Método: Câmaras distintas por nome por UF, entre elas as com linha de serviço SAPL (a paginação repete casas: 4.282 cards para 1.911 casas distintas; se esconde casas, os números são piso).

- **1.145 Câmaras Municipais com SAPL registrado** (20,6% dos 5.570 municípios); **747** com instância "Funcionando" na última verificação do Interlegis (13,4%); cerca de **163** com uso registrado em 2025-26 (2,9%). Câmaras com SAPL fora do registro do Interlegis podem faltar (NÃO VERIFICADO).
- Por UF (com SAPL / funcionando): MG 208/147, PR 163/94, SP 81/62, PE 54/33, BA 53/27, MT 51/37, PB 49/31, RS 57/47, RN 46/15, PI 45/27, RO 42/31, RJ 38/24, CE 34/24, TO 34/27, GO 30/25, SC 27/22, AM 26/9, ES 24/21, PA 18/15, MA 14/8, AC 14/3, MS 12/4, AP 10/6, AL 7/4, RR 5/2, SE 3/2 (DF não tem Câmaras Municipais).
- Vereadores cobertos: total real NÃO VERIFICADO. Aproximação de 9 a 13 cadeiras por município: ~10.300 a ~14.900 para as 1.145 Câmaras; ~6.700 a ~9.700 para as 747 funcionando. O exato sai dos eleitos do TSE por município.
- API testada (Natal RN, Rio Branco AC, Boa Vista RR; todas já em `ENDPOINTS.md`): `/api/parlamentares/legislatura/` (200) e `/api/parlamentares/mandato/?legislatura=<id>` (200, Natal: 12.825 B, 32 mandatos para 29 cadeiras, 31 `titular=true`, 1 `titular=false`). Campos do mandato: parlamentar, legislatura, data_inicio_mandato, data_fim_mandato, titular, tipo_afastamento, tipo_causa_fim_mandato, votos_recebidos, coligacao. Exemplo: `{"parlamentar":43,"legislatura":5,"data_inicio_mandato":"2025-01-01","data_fim_mandato":"2028-12-31","titular":true,"tipo_afastamento":null}`.
- Limites: `ativo` não serve (Natal: 85 ativos para 29 cadeiras; `?ativo=true` devolve 500); o suplente aparece com início igual ao da legislatura (não registra a posse real); `tipo_afastamento` nulo em todos; sem endpoint de afastamento (404); sem partido; o id da legislatura atual muda por instância (Rio Branco id 5 = 1977-1982; Boa Vista sem id 5); `page_size` máximo 100.
- No repositório: SAPL já usado só para Assembleias e 4 capitais (Rio Branco, Boa Vista, Natal, João Pessoa); não existe coletor de vereadores por SAPL. Outras plataformas de Câmaras (IPM, Betha, Cidadão/GovBr): NÃO VERIFICADO.

## Recomendação (vereadores cobertos por esforço)

Contagens de vereadores são estimativas (municípios x cadeiras típicas), não verificadas.

1. **PE, `ListaServidores`** (~2 mil vereadores, 185 a 189 municípios; esforço baixo): única fonte com ingresso e afastamento por vereador; JSON sem chave. Partido e confirmação pelo TSE por nome e município.
2. **PB, bucket `download.tce.pb.gov.br`** (~2 mil vereadores, 223 municípios; esforço baixo/médio): folha mensal em CSV; suplente inferido pelas aparições em `ano_mes`. Não guardar o CPF completo.
3. **SAPL das Câmaras fora de PE e PB** (~10 a 15 mil vereadores nas 1.145 Câmaras, ~7 a 10 mil nas 747 funcionando; esforço médio/alto): um coletor, mas a API só distingue titular x suplente, sem posse real, afastamento nem partido, então serve para detectar mudança de titular, com cruzamento pelo TSE. Cobre MG, PR, SP, RS, BA etc.
4. **Repetir de rede brasileira os NÃO VERIFICADOS de maior porte**: MG (CAPMG e dadosabertos, 853 municípios), PR, MT, MS, PA, BA, AC, AL, AP, RO, RR, TO. Os 403/timeouts podem ser bloqueio deste ambiente; a leitura de PI e SC exige navegador real.
5. **Querido Diário** como sinal complementar de posse de suplente (texto livre, esforço médio/alto) e **TCE-RJ `situacao_funcional`** como conferência do número de vereadores por Câmara/mês (baixo esforço).
6. CE e MA publicam agentes políticos municipais por API aberta, mas só com CPF e sem nome: não servem sem fonte de CPF.

## Consultas de busca e observações

- As partes por grupo registraram as consultas feitas (cerca de 60 buscas web, sem URL adivinhada; hosts achados por busca, por links do site oficial ou por redirecionamento). Falhas de busca por limite de taxa foram repetidas com outra formulação.
- Desvios do limite de amostra: o agente das fontes nacionais baixou 866 KB da lista de entes do SICONFI; o do PB baixou um ZIP de 238 KB (o menor disponível) para conferir os campos. Nenhum dado pessoal foi gravado neste relatório nem enviado nas requisições.
- 1ª rodada (resumo): só PE confirmado; RS e SP sem lista; demais NÃO VERIFICADOS por hosts testados por palpite. Os resultados acima substituem esse quadro.
