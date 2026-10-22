# Levantamento de dados que faltam

Estados cujas Assembleias Legislativas ainda não coletamos. Cada tópico guarda o que já foi apurado e o próximo passo, para uma nova sessão continuar sem refazer a pesquisa. Ideias de funcionalidade ficam em `FUTURAS_IMPLEMENTACOES.md`.

**Já coletados** (SAPL, `scripts/coletar_estaduais.py`, dicionário `ASSEMBLEIAS`): AC, AL, AM, PB, PI, RO, TO.
**Faltam:** AP, BA, CE, DF, ES, GO, MA, MG, MS, MT, PA, PE, PR, RJ, RN, RR, RS, SC, SE, SP.

Para cada estado, apurar: lista de deputados, proposições (autoria), votações nominais, presença, cota/verba e remuneração. Antes de escrever coletor, conferir se a Assembleia usa SAPL (`https://sapl.al.<uf>.leg.br/api/parlamentares/legislatura/?page_size=1`); se usar, basta incluir o host em `ASSEMBLEIAS`. Registrar endpoint novo em `ENDPOINTS.md` e o conjunto no `CHANGELOG.md`.

## PR: Paraná (apurado em 2026-10-22)

Portal: `https://transparencia.assembleia.pr.leg.br/` (acessível por `curl` com User-Agent de navegador, sem bloqueio). Não usa SAPL.

### O que existe

| Dado | Onde | Acesso |
|---|---|---|
| Proposições (autoria, tramitação, situação) | API `http://webservices.assembleia.pr.leg.br/api/public`: `GET /proposicao/campos`, `POST /proposicao/filtrar` (filtro `descricaoTipoProposicao`, ex.: `INDICAÇÃO`), `GET /proposicao/{código}` | JSON aberto, documentada em `/servicos/dados-abertos` |
| Normas legais | Mesma API: `GET /norma-legal/campos`, `POST /norma-legal/filtrar`, `GET /norma-legal/{código}` | JSON aberto |
| Verbas de ressarcimento (cota parlamentar), 2020 até hoje | App `https://consultas.assembleia.pr.leg.br/#/ressarcimento`; API `https://consultas.assembleia.pr.leg.br/api/public/ressarcimento/meses/{ano}` e `/ressarcimentos/{ano}/{mês}` | **Exige token reCAPTCHA** (sem token: HTTP 400 `invalid-recaptcha`). Não contornar |
| Presença em plenário | `/plenario/presenca-em-plenario` (filtros ano 2011–2026, mês, data) | A descobrir: endpoint que a página chama |
| Controle de votações | `/plenario/controle-de-votacao` (por sessão ou por projeto de lei; ano 2011–2026) | A descobrir: endpoint que a página chama |
| Atividade por parlamentar | `/plenario/atividade-por-parlamentar` (filtros parlamentar, legislatura, tipo, situação) | A descobrir; talvez saia da API de proposições (autoria) |
| Parlamentares | `/pessoal/parlamentares` | Lista carregada por script (HTML vazio): a descobrir |
| Remuneração de servidores | `/pessoal/remuneracao-dos-servidores` | A descobrir |
| Diárias de viagem | `/receitas-e-despesas/diarias-de-viagem` | PDF (ex.: `storage2.assembleia.pr.leg.br/file/public-media/transparencia/diarias/pdfs/diarias1.pdf`) |
| Passagens aéreas, cartões, despesas | `/receitas-e-despesas/passagens-aereas`, `/cartoes`, `/despesas/consultas` | A descobrir |
| Relatório de atividades parlamentares | `/plenario/relatorio-de-atividades-parlamentares` | A descobrir |

A API de dados abertos tem só as 6 rotas acima: não há rota de deputados, votos ou gastos.

### Próximos passos

1. Abrir cada página da tabela marcada "A descobrir" no Firefox, com o DevTools (aba Rede) aberto, e anotar a URL, o método e os parâmetros que a página chama ao pesquisar (presença, votações, parlamentares, atividade por parlamentar, remuneração). Só com `curl` não aparece: os dados vêm por script.
2. Testar `POST /proposicao/filtrar` com amostra (um ano, um tipo) para ver se traz autor, data, situação e resultado, e se o autor tem identificador que liga ao deputado.
3. Verificar se o autor/parlamentar nos endpoints de presença e votações tem um código comum, para ligar ao deputado estadual (o TSE já traz os eleitos de 2022).
4. Ressarcimento: pedir a exportação pela Lei de Acesso à Informação (e-SIC da ALEP) ou verificar se há CSV/PDF mensal no portal; não automatizar contornando o reCAPTCHA.
5. Se os passos 1 a 3 derem endpoints estáveis: criar `scripts/coletar_pr.py` (cache em `dados/estaduais/PR/`), `contrato_apis.py` com amostras reais em `tests/fixtures/contratos/`, e registrar tudo em `ENDPOINTS.md` e `CHANGELOG.md`. Fonte com link na página do político (regra de fontes do projeto).

## Demais estados (nada apurado)

Para cada um: conferir SAPL (comando acima); se não for, achar o portal de transparência e a API/dados abertos da Assembleia e preencher a tabela como no PR.

### AP: Amapá

Apuração de 2026-10-22: **nada obtido**, site da Assembleia inacessível. Repetir as tentativas abaixo no futuro.

| URL tentada | Ferramenta | Resultado em 2026-10-22 |
|---|---|---|
| `http://www.al.ap.leg.br` | curl | DNS resolve (`132.255.49.19`), timeout de 20 s |
| `http://www.al.ap.leg.br` | WebFetch | `ECONNREFUSED 132.255.49.19:443` |
| `https://www.al.ap.leg.br`, `https://al.ap.leg.br`, `http://al.ap.leg.br` | curl | timeout |
| `https://www.al.ap.leg.br/pagina.php?pg=transparencia` | curl | timeout (URL de transparência chutada) |
| `https://sapl.al.ap.leg.br/api/parlamentares/legislatura/?page_size=1` | curl | host não resolve (não usa SAPL nesse endereço) |
| `https://transparencia.al.ap.leg.br` | curl | host não resolve |
| `https://web.archive.org/web/20241206213457/http://al.ap.leg.br/` | curl | HTTP 403 (existe cópia de 06/12/2024, curl é bloqueado) |
| mesma cópia do Wayback | WebFetch | bloqueado pela ferramenta ("unable to fetch from web.archive.org") |

Próximos passos: repetir as URLs acima; abrir a cópia do Wayback no Firefox (curl e WebFetch não passam); procurar o portal de transparência e dados abertos por busca; os dados dos deputados estaduais (nome, partido, votos) já vêm do TSE.
### BA: Bahia (apurado em 2026-10-22)

Portal da Assembleia: `https://www.al.ba.gov.br/` (acessível por `curl` com User-Agent de navegador). Não usa SAPL (`sapl.al.ba.leg.br` não resolve). O sistema legislativo é o NoPaper (`albalegis.nopapercloud.com.br`), **atrás de Cloudflare: HTTP 403 "Sorry, you have been blocked"**, inclusive a página de dados abertos e a API. Não contornar.

| Dado | Onde | Acesso |
|---|---|---|
| Deputados em exercício (63, nome + partido) | `/deputados/deputados-estaduais`; ficha em `/deputados/deputado-estadual/{id}` (id = 910629 etc.) | HTML estático. Ficha tem nascimento, formação, mandatos, filiações, atividade parlamentar. Também `/deputados/todos-deputados`, `/ex-deputados-estaduais`, `/contatos-deputados` |
| Verba indenizatória (cota) por deputado | `/transparencia/verbas-idenizatorias` (filtro deputado, mês/ano, categoria); detalhe `/transparencia/verbas-idenizatorias/{id}/` | HTML estático: lançamento (nº, mês/ano, deputado, categoria, valor) e detalhe com nota/recibo, CNPJ/CPF, fornecedor, valor, glosa e PDF da NF em `/fserver/...`. Paginação/filtro a descobrir |
| Proposições (autoria, ementa, data, tramitação) | `/atividade-legislativa-nova/proposicoes`; detalhe `/atividade-legislativa-nova/proposicao/REQ-10650-2025` | HTML estático: "Autor: DEPUTADO ...", origem, data de entrada, regime, ementa, tramitação. Lista por ano em `/atividade-legislativa/proposicoes-por-ano` |
| Emendas parlamentares estaduais (por deputado, 2020 até hoje) | CKAN `https://dados.ba.gov.br/` dataset `emendas-parlamentares`, ZIP `.../emendasparlamentares.zip` (2,5 MB) | **CSV aberto**, atualizado diariamente. `VW_PAINEL_EMENDAS_PARLAMENTARES_DESPESAS.csv` tem ano, órgão, ação, `Deputado`, `Nome do Deputado`, valores orçado/empenhado/liquidado/pago; `..._PAGAMENTOS.csv` tem credor, data, valor e objeto; ligação por `num_codigo`. Dataset `transferencias-especiais` análogo. API CKAN `/api/3/action/package_search` responde |
| Presença/frequência | `albalegis.nopapercloud.com.br/spl/sessoes.aspx` | **Bloqueado (Cloudflare 403)** |
| Votações nominais | Sem seção própria; `/transparencia/ativ-legislat`, `/atividade-legislativa-nova/ordem-do-dia`, `/sessoes-plenarias` | A descobrir se trazem voto por deputado (no NoPaper, provavelmente bloqueado) |
| API de dados abertos (comissões, parlamentares, proposições, trâmites, autores) | `albalegis.nopapercloud.com.br/dados-abertos.aspx` (descrita em `/transparencia/avisos2`) | **Bloqueada (Cloudflare 403)** para curl; testar no Firefox e ver se o bloqueio é só do curl |
| Remuneração, diárias, estagiários | `https://portalrh.alba.ba.gov.br/transparencia` (+ `/diarias`, `/estagiarios`) | HTTP 200; conteúdo a descobrir |
| Liderança/blocos | `albalegis.nopapercloud.com.br/spl/liderancas.aspx` | Provavelmente bloqueado |

`https://www.transparencia.ba.gov.br/` é o portal do **Poder Executivo**: não tem dados da Assembleia/deputados. Só serve para emendas (via CKAN acima), pagamentos, despesas e servidores do estado. Links `/EmendasParlamentares/...` e `/ServidorPessoal/RemuneracaoServidores` dão 404 (caminhos citados na home não existem como escritos; usar o CKAN).

Próximos passos:
1. Abrir `albalegis.nopapercloud.com.br/dados-abertos.aspx` no Firefox: se abrir, anotar os endpoints REST (parlamentares, proposições, trâmites, autores) e se o Cloudflare bloqueia também o acesso programático; se bloquear, pedir liberação/exportação à ALBA (e-SIC/e-Ouv) em vez de contornar.
2. Scraping das páginas HTML do `al.ba.gov.br` (deputados, verbas, proposições): conferir `robots.txt`, paginação e parâmetros de filtro da verba indenizatória (aba Rede do Firefox).
3. Emendas: baixar o ZIP do CKAN, ligar `Nome do Deputado` ao deputado do TSE (nomes com espaços extras) e registrar em `ENDPOINTS.md`/`CHANGELOG.md`.
4. Votos e presença: sem fonte aberta confirmada; verificar se `ordem-do-dia`/`sessoes-plenarias` trazem votação nominal.
5. Verificar `portalrh.alba.ba.gov.br` (remuneração por deputado/gabinete).
### CE: Ceará (apurado em 2026-10-22)

Portal: `https://transparencia.al.ce.gov.br/` (dados desde 2021). Acessível por `curl` com User-Agent de navegador, `robots.txt` sem restrição. Não usa SAPL. Site institucional: `https://www.al.ce.gov.br/`.

| Dado | Onde | Acesso |
|---|---|---|
| Deputados (46 em exercício/licenciados + 7 suplentes em exercício; nome, partido, foto) | `https://www.al.ce.gov.br/deputados`; ficha `/deputados/{slug}` (slug = nome minúsculo sem acento, hífens, ex.: `agenor-neto`); foto `https://www.al.ce.gov.br/image/{id}` | HTML estático. Ficha tem comissões, projetos e "Votos" (conteúdo a abrir) |
| Verba de Desempenho Parlamentar (VDP, a cota) por deputado, 2021 até hoje | `/despesas/verba-desempenho-parlamentar?mes=10&ano=2026` (filtro mês, ano, nome; 30 por página, `&page=2`) | **CSV aberto por mês**: `/despesas/verba-desempenho-parlamentar/csv?mes=10&ano=2026`, separador `;`, colunas `DEPUTADO;PERIODO;EMPENHO;DESCRICAO;CNPJ;CREDOR;VALOR` (valor `4.000,00`), nome como `DEP AGENOR NETO`. Testado: outubro/2026 = 354 linhas; mês sem dados volta só o cabeçalho (jul e ago/2026 vazios). Fonte: S2GPR até 2021, SiafeCE desde 2022 |
| Votações nominais | `/consultas-gerais/votacao-nominal` (filtros legislatura 31.ª e sessão legislativa 1.ª–4.ª; colunas legislatura, sessão legislativa, sessão, data, matéria, detalhe) | Por matéria: PDF `/uploads/votacao_nominal_materia/{id}.pdf` e **XLSX** `/uploads/votacao_nominal_materia_csv/{id}.xlsx` (HTTP 200). O XLSX é "RELATÓRIO DE VOTAÇÃO" com blocos SIM / NÃO / ABSTENÇÃO e, por deputado, o nome e o partido (codificação do arquivo em Latin-1). Os ids são aleatórios e só aparecem na página; o filtro é por JS (a URL com query não filtrou) e há exportação geral `/consultas-gerais/votacao-nominal/votacaoNominalcsv` ainda não testada |
| Proposições (autoria, ementa, situação) | `/portal/proposicoes` leva a `https://www2.al.ce.gov.br/legislativo/proposicoes/numero.php?nome=31_legislatura&tabela={projeto_lei,projeto_indi,projeto_decre,projeto_compl,projeto_emen,projeto_reso,projeto_mens}&opcao={T,D}` (T tramitando, D deliberados). Legislaturas 26–30: páginas estáticas `.../proposicoes/30_legislatura.htm` | HTML paginado (20 por página; projetos de lei tramitando: 2.499 em 125 páginas). Cada item traz nº/ano, **Autor** (nome em maiúsculas), data de entrada, ementa, lei, situação. Http redireciona para https (301) |
| API do portal (OpenAPI 3.0, Swagger) | UI em `/api`; especificação `https://transparencia.al.ce.gov.br/docs?api-docs.json`; GET sem autenticação, JSON `{success, message, data}`, 20 registros por requisição | Só 5 rotas: `/api/contratos`, `/api/empenhos`, `/api/licitacoes`, `/api/pagamentos`, `/api/termos-credenciamento`. **Não há deputados, votos, presença nem proposições.** Útil só para cruzar empenho/pagamento da VDP |
| Remuneração de membros e servidores | `/gestao-de-pessoas/pessoal`, `/gestao-de-pessoas/estrutura-remuneratoria` | A descobrir (formato e se lista deputado) |
| Diárias | `/despesas/despesas-diarias` | A descobrir |
| Pagamentos, empenhos, FPP (Fundo de Previdência Parlamentar) | `/despesas/pagamentos`, `/despesas/despesas-notas-empenho`, `/despesas/fpp/...` | Sem relação direta com deputado individual |
| Emendas parlamentares | `/pagina/transparencia-e-rastreabilidade-de-emendas` | A descobrir |
| Comissões, frentes, oradores, atas, ordem do dia | `/portal/comissoes`, `/pagina/frentes-parlamentares`, `https://www.al.ce.gov.br/legislativo/oradores`, `/atas/legislaturas`, `/legislativo/ordem-do-dia/avulso-de-projeto` | A descobrir |
| Presença em plenário | Sem seção própria no portal | Não encontrada |

Próximos passos:
1. VDP: baixar o CSV de cada mês (2021 até hoje) e somar por deputado; ligar `DEP {NOME}` ao deputado do TSE (nome de urna, remover o prefixo `DEP `). Fonte com link para o CSV do mês na página do político.
2. Votações: abrir `/consultas-gerais/votacao-nominal` no Firefox (aba Rede) para ver como a lista de matérias é carregada e testar `votacaoNominalcsv`; ler o XLSX completo com openpyxl (estrutura SIM/NÃO/ABSTENÇÃO por partido e deputado) e conferir se há ausentes. Só há a 31.ª legislatura (2023–2026).
3. Proposições: percorrer as páginas `numero.php` (tabelas × T/D × páginas), extrair nº/ano, autor, data, ementa, situação; autor vem como nome (sem id), então ligar por nome. Pode haver autoria coletiva ou por comissão.
4. Abrir a ficha de um deputado e a página de remuneração/diárias para ver o que mais existe (votos, comissões, presença em sessões).
5. Se os passos 1 a 3 forem estáveis: `scripts/coletar_ce.py` (cache em `dados/estaduais/CE/`), amostras em `tests/fixtures/contratos/`, e registrar em `ENDPOINTS.md` e `CHANGELOG.md`.
### DF: Distrito Federal (Câmara Legislativa)

Apuração de 2026-10-22: **nada obtido**, site da CLDF inacessível (teste manual do usuário no navegador também falhou). Repetir as tentativas abaixo no futuro.

| URL tentada | Ferramenta | Resultado em 2026-10-22 |
|---|---|---|
| `https://www.cl.df.gov.br/web/portal-transparencia` | navegador (manual) | inacessível |
| `https://www.cl.df.gov.br/web/portal-transparencia` | curl | timeout de 20 s ao conectar na porta 443 |
| `http://www.cl.df.gov.br/web/portal-transparencia`, `https://www.cl.df.gov.br/` | curl | timeout de 20 s |
| `www.cl.df.gov.br` | nslookup | DNS resolve (`189.84.137.29`, `179.124.14.95`), servidor não responde |

### ES: Espírito Santo (Assembleia Legislativa, ALES)

Apuração de 2026-10-22: **nenhum dado obtido**, o site da ALES não responde a partir desta rede. Repetir as tentativas no futuro (ou de outra rede/navegador).

| URL tentada | Ferramenta | Resultado em 2026-10-22 |
|---|---|---|
| `https://www.al.es.gov.br/Transparencia` | curl | timeout de ~21 s ao conectar na porta 443 |
| `https://www.al.es.gov.br/DadosAbertos/Remuneracao` | curl | timeout de ~21 s na porta 443 |
| `http://www.al.es.gov.br/Transparencia` | curl | timeout na porta 80 |
| `al.es.gov.br`, `transparencia.al.es.gov.br` | nslookup/curl | DNS resolve (`201.62.36.42`), servidor não responde; `dadosabertos.` e `sistemas.al.es.gov.br` não resolvem |
| busca web por "al.es.gov.br DadosAbertos Remuneracao" | WebSearch | nada da ALES nos resultados |

**O que a página da Transparência Internacional usa** (`https://transparenciainternacional.org.br/itgp/assembleia-legislativa/espirito-santo/`, acessível): é só a avaliação do ITGP (ALES em 2.º lugar, 71 pontos, "bom"). Não traz dados de deputados nem links para a ALES. A fonte é a planilha pública "banco de dados" (`https://comunidade.transparenciainternacional.org.br/itgp-legislativo-estadual-banco-de-dados`, XLSX com 0/0,5/1 por critério e sem URLs). Ela não serve como fonte de dados de político, mas indica o que a ALES diz publicar (ES, itens avaliados):

| Item do ITGP | ES |
|---|---|
| TL11 base de proposições | sim (1) |
| TL12 salário nominal dos parlamentares (base aberta) | sim (1) |
| TL13 viagens oficiais | sim (1) |
| TL14 (publicação mensal no portal) | sim (1) |
| TL16 presença/ausência dos parlamentares | sim (1) |
| TL15 votações nominais (base aberta, semanal) | **não (0)** |
| TA02 verbas indenizatórias (diárias etc.) | **não (0)** |
| TL04 comissões, TL01/TL02 contatos e biografia | sim (1) |
| TL06 agenda do presidente | não (0) |

Próximos passos:
1. Abrir `https://www.al.es.gov.br/Transparencia` e `/DadosAbertos/Remuneracao` no Firefox (outra rede, se o bloqueio persistir) e ver na aba Rede de onde saem os dados (CSV/JSON/API).
2. Se acessível: conferir remuneração, viagens, presença e proposições (itens com "sim" acima); votações nominais e verba indenizatória a ALES não publica em formato aberto.
3. Se funcionar: `scripts/coletar_es.py`, amostras em `tests/fixtures/contratos/`, `ENDPOINTS.md` e `CHANGELOG.md`.

### GO: Goiás

Apuração de 2026-10-22 em `https://transparencia.al.go.leg.br/` (Transparência Alego). A página inicial é uma SPA (AngularJS) que só mostra o aviso de cookies no HTML; **os dados saem de uma API JSON pública, sem autenticação nem captcha**, descoberta no bundle `/assets/application.transparencia-*.js`. Qualquer caminho do site devolve o mesmo HTML (roteamento no cliente), então só os `/api/...` valem. `robots.txt` bloqueia apenas as páginas HTML `/prestacao-de-contas/gestao-de-pessoas/quadro-de-remuneracao` (a API não é citada).

Base: `https://transparencia.al.go.leg.br/api/transparencia/`. Testado com curl (HTTP 200, `application/json`):

| Endpoint | Parâmetros | O que traz | Anos disponíveis |
|---|---|---|---|
| `verbas_indenizatorias` | `ano`, `mes` | por deputado: `valor_apresentado`, `valor_indenizado`, `deputado{id,nome}` | 2013 a 2026 (`/periodos` lista) |
| `verbas_indenizatorias/deputados` | `ano`, `mes` | lista dos deputados com `id` e nome (nome parlamentar) | idem |
| `verbas_indenizatorias/resumo-anual` | `deputado_id`, `ano` | resumo anual por deputado (não testado com id) | idem |
| `remuneracoes` | `ano`, `mes`, `categoria` (7 = Deputados) | matrícula, nome completo, cargo, `status` (ex.: licença saúde), vencimento, indenizações, auxílios, descontos, líquido | por `ano`/`mes` |
| `remuneracoes/categorias`, `/vinculos` | — | domínios (categoria 7 = "Deputados"; vínculo `DEPUTADOS`) | — |
| `diarias` | `ano`, `mes` | beneficiário (matrícula, cargo), trecho, motivo, datas, qtd. e valor das diárias, passagens, total; inclui assessores | 2014 a 2026 (`/meses-e-anos`) |
| `requerimentos` | `ano` | número, autor (`deputado.nome`), tipo, etapa, `url_download` do PDF | 1999 a 2023 listados em `/anos` |
| `sessoes-plenarias/datas-do-ano`, `/:data/pauta` | — | datas de sessões e pauta | 2013 em diante |
| `processos/busca-simples`, `/busca-avancada`, `/recentes`, `/proposicoes-mais-votadas` | — | proposições (não testado) | — |
| `votacoes.json?tipo=` | `tipo` | `{"error":"Tipo inválido"}` com `tipo=1`; valores válidos não descobertos | — |
| `despesas-com-pessoal`, `gestao-fiscal-anual`, `licitacoes`, `contratos-e-convenios`, `frotas`, `uso-aeronaves`, `orcamentos`, `execucao_orcamentaria` | — | dados institucionais da Casa, sem uso por político | — |

Pontos de atenção:
- A API de remuneração identifica o deputado por **nome civil** (ex.: "ALESSANDRO MOREIRA DOS SANTOS") e a de verbas por **nome parlamentar** ("Alessandro Moreira") com `id` interno da Alego. Cruzar por nome exige normalização ou um mapa nome civil ↔ parlamentar (o `portal.al.go.leg.br/deputados` lista os deputados).
- Valores vêm como string (`"31310.41"`). Mês sem publicação devolve `[]` (ex.: verbas 2026-09 vazio; 2026 só tem meses 1 a 8 publicados).
- `remuneracao_bruta` aparece `0.0` para deputados mesmo com líquido preenchido: usar `vencimento`, `indenizacoes`, `auxilios`.
- Outros hosts citados no bundle: `portal.al.go.leg.br/deputados` (perfil, mesa diretora, contatos), `alegodigital.al.go.leg.br/spl/` (consulta de produção legislativa e sessões, ASP.NET), `opine.al.go.leg.br`, `publicacoes.al.go.leg.br` (PCA em PDF), `saba.al.go.leg.br` (arquivos). Não verificados.

Próximos passos:
1. Fonte de link por dado: verbas e remuneração → `https://transparencia.al.go.leg.br/` (seção correspondente); confirmar as URLs das telas no Firefox.
2. Investigar `portal.al.go.leg.br/deputados` (lista oficial, partido, foto, contato) e `alegodigital.al.go.leg.br/spl/` (proposições e votações nominais, valores de `votacoes.json?tipo=`).
3. Se seguir: `scripts/coletar_go.py`, amostras em `tests/fixtures/contratos/`, `ENDPOINTS.md` e `CHANGELOG.md`.
### MA: Maranhão (Assembleia Legislativa, ALEMA; apurado em 2026-10-22)

**Acesso bloqueado desta rede.** `www.al.ma.leg.br` e `sistemas.al.ma.leg.br` resolvem para 45.238.236.197, mas a porta 443 não responde (WebFetch: `ECONNREFUSED`; curl: timeout após 20 s). Nada foi lido de:
- `https://sistemas.al.ma.leg.br/transparencia/index.html` (portal de transparência)
- `https://www.al.ma.leg.br/sitealema/` (site institucional)

**ITGP** (`https://transparenciainternacional.org.br/itgp/assembleia-legislativa/maranhao/`, ano da avaliação não informado na página): nota **43,5/100 ("Regular")**, 14º de 27 assembleias. Por dimensão: Plataformas 75; Comunicação 72,7; Governança 58,8; Transparência Legislativa 41,7; Transparência Administrativa 36,1; Marcos Legais 28,6; Participação e Engajamento 25; Transformação Digital 10. A página não lista critérios individuais; eles estão no banco de dados: `https://comunidade.transparenciainternacional.org.br/itgp-legislativo-estadual-banco-de-dados`.

Próximos passos:
1. Abrir os dois links da ALEMA no Firefox (outra rede, se o bloqueio persistir) e ver na aba Rede de onde saem os dados (CSV/JSON/API).
2. Baixar o banco do ITGP para saber quais itens (remuneração, verba indenizatória, diárias, presença, votações) a ALEMA publica.
3. Se acessível: `scripts/coletar_ma.py`, amostras em `tests/fixtures/contratos/`, `ENDPOINTS.md` e `CHANGELOG.md`.

### MG: Minas Gerais (Assembleia Legislativa, ALMG; apurado em 2026-10-22)

**Acesso livre: API JSON pública, sem autenticação nem captcha.** `https://www.almg.gov.br/transparencia/inicial/` é só o menu do portal (sem dados). Seções: Assembleia em números, Balanço das atividades, Diário do Legislativo, Licitações, Contratos e convênios, Prestação de contas (`/transparencia/prestacao-de-contas/`), Concursos, Dados abertos. Remuneração, verba indenizatória e gastos de deputados não aparecem no menu inicial; a verba tem página própria: `https://www.almg.gov.br/transparencia/prestacao-de-contas/deputados/verba-indenizatoria/` (não aberta). "Dados abertos" redireciona para `https://dadosabertos.almg.gov.br/`.

Base: `https://dadosabertos.almg.gov.br/api/v2/` (JSON ou XML; `?formato=json`). O `/ws` antigo foi descontinuado. Limite do portal: no máximo 2 requisições simultâneas e 1 s entre elas, com bloqueio sem aviso se exceder. Documentação: Swagger em `https://dadosabertos.almg.gov.br/api/ajuda/swagger/view/lastest#/`; arquivos CSV em `https://dadosabertos.almg.gov.br/documentacao/arquivos` (`verbas-indenizatorias`, `deputados`, `deputados-da-atual-legislatura`, `proposicoes`, `tramitacao-de-proposicoes`, contratos, convênios, contratações, atas de registro de preços, legislação mineira, thesaurus). Testado com curl (HTTP 200):

| Endpoint | O que traz |
|---|---|
| `deputados/em_exercicio` | lista: `id`, `nome`, `partido`, `tagLocalizacao` |
| `deputados/{id}` | ficha: sexo, situação, início da situação, etc. |
| `deputados/lista_telefonica` | `nomeServidor` (nome civil), partido, endereço, telefone |
| `prestacao_contas/verbas_indenizatorias/deputados/{id}/{ano}/{mes}` | por tipo de despesa: `valor`, `descTipoDespesa`, `listaDetalheVerba` com `valorReembolsado` (detalhe por nota; campos não explorados). Mês sem dado devolve `{"list": []}` (2025/1 vazio, 2025/3 preenchido) |
| `comissoes/...`, `pronunciamentos/...`, `contratos`/`contratacoes` | reuniões e composições, discursos, contratos (documentados, não testados) |

Pontos de atenção:
- `proposicoes/pesquisa/direcionada` devolve 400 "Parâmetro de paginação inválido" com `tp`, `ini`, `fim`; parâmetros de paginação corretos estão no Swagger (não consultado).
- Salário/remuneração, presença e votações de deputados: não confirmados; não achei endpoint (ver Swagger). A ITGP diz que a ALMG **não publica base nominal de salários** de servidores efetivos e comissionados.
- O `id` é interno da ALMG; `lista_telefonica` dá o nome civil, útil para cruzar com TSE/Câmara.

**ITGP** (`https://transparenciainternacional.org.br/itgp/assembleia-legislativa/minas-gerais`, ano da avaliação não informado): nota **69,8/100 ("Bom")**, 3º de 27 assembleias. Por dimensão: Comunicação 100; Participação e Engajamento 93,7; Transparência Legislativa 77,1; Transformação Digital 70; Plataformas 60; Governança 58,8; Transparência Administrativa 55,6; Marcos Legais 42,9 (a página deixa o pareamento número-rótulo ambíguo; conferir no banco). Faltas apontadas: norma que regulamente a LAI, norma de registro de interações com grupos de interesse e base nominal de salários. Banco com os critérios: `https://comunidade.transparenciainternacional.org.br/itgp-legislativo-estadual-banco-de-dados`.

Próximos passos:
1. Ler o Swagger para achar remuneração, presença, votações nominais e a paginação das proposições.
2. Baixar o CSV `verbas-indenizatorias` (histórico completo, evita uma chamada por deputado/mês).
3. Fonte de link por dado: página da verba indenizatória acima; confirmar as demais URLs no Firefox.
4. Se seguir: `scripts/coletar_mg.py`, amostras em `tests/fixtures/contratos/`, `ENDPOINTS.md` e `CHANGELOG.md`.

### MS: Mato Grosso do Sul (Assembleia Legislativa, ALEMS; apurado em 2026-10-22)

**Acesso livre; sem captcha nem login.** `https://al.ms.gov.br/Transparencia` é o menu do portal (sem dados). Os links apontam para `www.transparencia.al.ms.gov.br/pages/index.php/...` (portal antigo, em redirecionamento) e para o portal novo `https://transparencia2.al.ms.gov.br/`. Seções do menu: Verbas Indenizatórias (CEAP), Relação Nominal de Servidores (`.../consultaservidores`), Diárias (`.../consultadiarias`), Remuneração Parlamentares (`.../gerdocumento/1200`, categoria 1201), Atividade Legislativa (`.../atividadelegislativa`, hoje `transparencia2.../home/atividadelegislativa`), Licitações e Contratos, Execução Orçamentária, LRF, Estagiários. Não há API JSON/XML anunciada.

**CEAP (verba indenizatória): CSV público, fonte principal.** Página: `https://transparencia2.al.ms.gov.br/ceap` (filtros ano 2012 a 2026, mês, categoria; a tabela carrega por JS). Exportação testada com curl (HTTP 200, `text/csv`, UTF-8 com BOM, separador `;`): `https://transparencia2.al.ms.gov.br/ceap/notas/exportar-csv?ano=2026` (~1,4 MB, ~5,2 mil linhas; `ano=2012` devolve ~4,7 mil linhas). Quatro linhas de cabeçalho/metadados, depois uma linha em branco e as colunas: `Deputado;Ano;Mês;Categoria;CPF/CNPJ;Fornecedor;Documento;Emissão;Valor (R$);Comprovante`. O `Comprovante` é link para o PDF da nota (`http://www.transparencia.al.ms.gov.br/arquivo/...pdf`): dá a fonte por lançamento. Parâmetros de mês/deputado/categoria existem no formulário (nomes não confirmados). 14 categorias (combustíveis, locomoção, divulgação, imóvel de apoio, consultorias, software/internet, segurança, material de expediente, diárias, material de consumo, auxílios alimentação e transporte, equipamentos). Total de 2026 na página: R$ 11.692.887,03.

Pontos de atenção:
- `Deputado` vem como nome de urna com prefixo (`"DEP. HASHIOKA"`): normalizar para cruzar com TSE/Câmara.
- `Mês` por extenso em português; valor como string `"R$ 99,90"`; data `dd/mm/aaaa`.
- Ano corrente vem parcial (publicação por mês).

**Remuneração dos parlamentares e servidores:** `gerdocumento/1200` só lista categorias ("Leis", "Remuneração", "Regulamentação da Cota Parlamentar"; atualizado até 10/10/2026), sem arquivos visíveis; não expandi a categoria 1201 nem `consultaservidores`/`consultadiarias` (JS). Formato dos arquivos desconhecido.

**Atividade legislativa:** a página é só um menu para Projetos e Proposições (sistema "sgpl"), Ordem do Dia, Novos Projetos, Matérias Apreciadas, Atas, Plenário, Comissões, Reuniões CCJR, Atos Administrativos, Relatório de Atividades. Presença e votações nominais: não confirmadas.

**ITGP** (`https://transparenciainternacional.org.br/itgp/assembleia-legislativa/mato-grosso-do-sul`, ano da avaliação não informado): nota **36/100 ("Ruim")**, 18º de 27 assembleias. Por dimensão: Comunicação 81,8; Governança 47; Transparência Legislativa 43,7; Marcos Legais 28,6; Participação e Engajamento 25; Transparência Administrativa 22,2; Plataformas 20; Transformação Digital 20. A página diz que a ALEMS não publica receitas, despesas e licitações básicas (a nota pode estar defasada frente ao portal novo). Critérios individuais: `https://comunidade.transparenciainternacional.org.br/itgp-legislativo-estadual-banco-de-dados`.

Próximos passos:
1. Baixar o CSV do CEAP por ano (2012 a 2026) e ver se há filtro por mês/deputado nos parâmetros (inspecionar `resumo_ceap.js`).
2. Abrir `consultaservidores`, `consultadiarias`, categoria 1201 e o sistema de proposições (sgpl) no Firefox para achar a fonte de remuneração, presença e votações.
3. Fonte de link por dado: CEAP → `https://transparencia2.al.ms.gov.br/ceap` (e o PDF do comprovante).
4. Se seguir: `scripts/coletar_ms.py`, amostras em `tests/fixtures/contratos/`, `ENDPOINTS.md` e `CHANGELOG.md`.

### MT: Mato Grosso (Assembleia Legislativa, ALMT; apurado em 2026-10-22)

**`https://www.al.mt.gov.br/transparencia/` não respondeu:** WebFetch falhou e o curl deu timeout (20 s) em `www.al.mt.gov.br` e `al.mt.gov.br`, do meu ambiente. Conteúdo e links do menu não verificados; abrir no Firefox.

**Portal de transparência (Elotech): `https://almt.eloweb.net/portaltransparencia/1/`.** Livre, sem login; só carrega um SPA React (a página tem o reCAPTCHA `google.com/recaptcha/api.js` carregado, uso não confirmado). Nenhum dado vem no HTML. Pelo bundle JS (`static/js/main.d260357a.chunk.js`) as rotas relevantes são:
- `/verbas` e `/verbas/detalhes` (API `/api/servidores/verbas/{a}/{b}` e `/api/servidores/verbas/detalhes/{a}/{b}/{c}`; parâmetros não identificados);
- `/cotas-parlamentares` (tela própria; API não identificada);
- `/servidores`, `/servidores/aposentados`, `/servidores/detalhes` (`/api/servidores/`);
- `/diarias` e `/diarias/detalhes`; `/ajuda-custo`; `/adiantamento`; `/afastamento`;
- `/emendas-parlamentares` (`/api/emendas-parlamentares/...`), contratos, licitações, almoxarifado, estagiários, terceirizados.
Não achei rota de presença, votações nominais nem proposições: isso fica no site da ALMT (não acessado).

**API não utilizável por curl:** `/api/...` na raiz do host devolve 404 (página de erro da Elotech); sob `/portaltransparencia/api/...` e `/portaltransparencia/actuator/info` volta o HTML do SPA (200, `text/html`). Entidade e exercício são enviados pelo front (`/api/exercicios/entidade/{id}`, `/api/entidades/lista`); o contrato real (host/cabeçalhos) só aparece na aba Rede do Firefox. Nenhum CSV/JSON de download foi confirmado.

**ITGP** (`https://transparenciainternacional.org.br/itgp/assembleia-legislativa/mato-grosso`, ano da avaliação não informado): nota **58,2/100 ("Regular")**, 6º de 27 assembleias e 3º no Centro-Oeste. Pontos fortes: Comunicação, Governança e Plataformas. Fracos: Marcos Legais e dados administrativos. Não atende: dados abertos e acessíveis, agenda de encontros com grupos de interesse, regulamentação da LGPD, proteção a denunciantes. As oito notas por dimensão não puderam ser associadas aos nomes (valores: 28,6; 18,7; 80; 88,2; 41,7; 77,8; 90,9; 40). Critérios individuais: `https://comunidade.transparenciainternacional.org.br/itgp-legislativo-estadual-banco-de-dados`.

Próximos passos:
1. Abrir `al.mt.gov.br/transparencia` no Firefox e listar o menu (verba indenizatória, remuneração, presença, votações).
2. No Firefox, abrir `/verbas` e `/cotas-parlamentares` do Eloweb com a aba Rede aberta para capturar a chamada JSON (URL, cabeçalhos, parâmetros) e ver se há exportação.
3. Fonte de link por dado: telas `https://almt.eloweb.net/portaltransparencia/1/verbas` e `.../cotas-parlamentares` (a confirmar).
4. Se seguir: `scripts/coletar_mt.py`, amostras em `tests/fixtures/contratos/`, `ENDPOINTS.md` e `CHANGELOG.md`.

### PA: Pará (Assembleia Legislativa, ALEPA; apurado em 2026-10-22)

**Portal de transparência: `https://alepa.pa.gov.br/Transparencia/Index`.** Livre, sem login (plataforma ASP.NET com DevExpress; fornecedor `alepa.quartertec.com.br` nas fotos). Menu relevante (todas sob `/Transparencia/Page/`):
- `VerbaIndenizatoria` e `VerbadeGabinete` (não há "cota parlamentar" com esse nome);
- `Frequencia`; `RemuneracaodePessoal`, `QuadrodePessoal`, `EstruturaRemuneratoriaDeputados`, `EstruturaRemuneratoriaServidores`;
- diárias dos parlamentares e emendas parlamentares estaduais (links não abertos); `DadosAbertos`.
Setor responsável: CPD. Páginas com "Última atualização em 22/10/2026".

**Conteúdo carregado depois do HTML:** em `VerbaIndenizatoria`, `VerbadeGabinete` e `RemuneracaodePessoal` o WebFetch só recebeu menu e "Carregando…". Campos, filtros, período e formato (tabela, CSV, PDF) não confirmados; endpoint real só pela aba Rede do Firefox. Nenhum link de arquivo apareceu.

**Frequência:** tabela HTML por deputado (foto, nome e partido, contagens Presente / Licenciado / Ausente; "Total de sessões: 4" no momento da leitura, período não informado). Exportação em PDF/Excel/Word, todas apontando para `/DXR.axd?r=1_89-QHOmx` (não distingui as chamadas). Link por deputado: `/Institucional/Deputado/{id}` (ex.: 1024). Dois deputados vieram sem perfil nem foto. Só presença em sessões; votações nominais não confirmadas.

**Dados abertos:** `/Transparencia/Page/DadosAbertos` redireciona (302) para `https://bancodeleis.alepa.pa.gov.br/api.php`, que documenta só o Banco de Leis: `GET https://bancodeleis.alepa.pa.gov.br/api/leis.php` (JSON, até 50 registros ativos; filtros opcionais `numero`, `ano`, `q`, `tipo`; campos `id`, `numero`, `ano`, `tipo`, `ementa`, `arquivo`, `link_pdf`, `status`). Não traz verbas, remuneração nem presença. Útil no máximo para leis, não para dados de deputado.

**ITGP** (`https://transparenciainternacional.org.br/itgp/assembleia-legislativa/para`, ano da avaliação não informado): nota **41,4/100 ("Regular")**, 15º de 27 assembleias. Por dimensão: Plataformas 65; Comunicação 63,6; Governança 58,8; Transparência Administrativa 41,7; Participação e Engajamento 37,5; Marcos Legais 28,6; Transformação Digital 20; Transparência Legislativa 16,7 (pior). A página diz que a ALEPA não divulga agenda e pautas do plenário e das comissões, o salário nominal dos deputados nem viagens oficiais (a nota pode estar defasada frente ao portal atual). Critérios individuais: `https://comunidade.transparenciainternacional.org.br/itgp-legislativo-estadual-banco-de-dados`.

Próximos passos:
1. No Firefox, abrir `VerbaIndenizatoria`, `VerbadeGabinete`, `RemuneracaodePessoal` e `EstruturaRemuneratoriaDeputados` com a aba Rede aberta para capturar a chamada de dados (URL, parâmetros) e ver se há exportação (Excel/CSV).
2. Abrir as diárias dos parlamentares e as emendas estaduais; achar a fonte de projetos e votações (não há no menu de transparência).
3. Fonte de link por dado: verba indenizatória → `https://alepa.pa.gov.br/Transparencia/Page/VerbaIndenizatoria`; frequência → `.../Frequencia`; remuneração → `.../RemuneracaodePessoal` (a confirmar).
4. Se seguir: `scripts/coletar_pa.py`, amostras em `tests/fixtures/contratos/`, `ENDPOINTS.md` e `CHANGELOG.md`.

### PE: Pernambuco (Assembleia Legislativa, ALEPE; apurado em 2026-10-22)

**Portal de transparência: `https://transparencia.alepe.pe.gov.br/`.** Livre, sem login. É uma SPA React (o WebFetch só recebe o título); rotas e endpoints saíram do bundle JS (`/static/js/main.*.js`). Seções: `/financas/*` (despesas, contratos, licitações, `verbas-indenizatorias`, `remuneracao-ajuda-deputados`, obras, convênios), `/pessoal/*` (servidores efetivos, comissionados, cedidos, lotação, remuneração), `/proposicoes`, `/legislacao`, `/ouvidoria`. Não achei seção de frequência/presença nem de votações nominais.

**Verba indenizatória (JSON aberto, sem login; mesmo que alimenta a tela `/financas/verbas-indenizatorias`), base `https://www.alepe.pe.gov.br/servicos/transparencia/`:**
- `dep/deputados.php?leg=-16` → 163 registros (`id`, `nome`, `partido`, `email`, `foto`, `to_ascii`); o `id` (ex.: 4508) é a chave dos demais.
- `adm/verbaindenizatoria-rubricas.php?ano=2026` → rubricas e teto mensal (I Imóveis 25.326,00; II Locação de veículos 33.025,10; III Assessoria jurídica 21.881,66; IV Consultorias 41.939,86; V Divulgação da atividade parlamentar; ...).
- `adm/verbaindenizatoria-dep-meses.php?dep={id}&ano={ano}` → meses com lançamento (`[{"mes":1},...]`; o site lista os últimos 6 anos).
- `adm/verbaindenizatoria.php?dep={id}&ano={ano}&mes={mes}` → lançamentos (`docid`, `numero`, `tipo` P/C, `deputado`, `mes`, `total`).
- `adm/verbaindenizatorianotas.php?docid={docid}` → notas do lançamento (`rubrica`, `sequencial`, `data`, `cnpj`, `empresa`, `valor`). Dá o fornecedor por CNPJ. Exemplo: Abimael Santos, jan/2026, 2 lançamentos (44.880 e 15.000).
Resposta vazia `[]` quando `dep` não existe. Dado mais completo que em PA/MT; ainda não conferi a diferença entre `tipo` P e C nem o campo de data do lançamento.

**API de dados abertos (`https://dadosabertos.alepe.pe.gov.br/`, `/api/v1/<método>?formato=csv|json&filtros`)**, sem login:
- `parlamentares` (JSON/CSV; só `nomeParlamentar` e `partido` da legislatura atual); `cargos?vinculo=comissionado|efetivo`; `lotacoes`; `servidores?vinculo=...&ano=`; `remuneracao` (por cargo, não por pessoa; competência 10/2026); `licitacoes`; `contratos`.
- `proposicoes/projetos/`, `proposicoes/indicacoes/`, `proposicoes/requerimentos/` (XML; `projetos` trouxe 638 itens com `docid`, `numero`, `ano`, `tipo`, `ementa`, `dataPublicacao` e `autores` com nome do deputado; `?docid=` detalha). Útil para projetos por autor; o `ementa` dos requerimentos vem com HTML escapado.
- Não há votações, presença nem verbas nessa API.

**ITGP** (`https://transparenciainternacional.org.br/itgp/assembleia-legislativa/pernambuco`, ano da avaliação não informado): nota **45,2/100 ("Regular")**, 11º de 27. Por dimensão: Comunicação 72,7; Governança 58,8; Plataformas 50; Participação e Engajamento 43,7; Transformação Digital 40; Transparência Legislativa 37,5; Transparência Administrativa 30,6; Marcos Legais 28,6. Pontos fortes: aplicativo cidadão e ferramenta de consulta popular; agendas do plenário e de parte das comissões publicadas. A página pede melhor divulgação da presença dos parlamentares em plenário e das votações nominais. Critérios individuais: `https://comunidade.transparenciainternacional.org.br/itgp-legislativo-estadual-banco-de-dados`.

Próximos passos:
1. Confirmar `tipo` P/C e o período de dados disponível (anos anteriores a 2026) nos endpoints de verba.
2. Procurar fonte de presença e votações nominais (não há no portal nem na API; testar `https://www.alepe.pe.gov.br` e `https://legis.alepe.pe.gov.br`).
3. Fonte de link por dado: verba → `https://transparencia.alepe.pe.gov.br/financas/verbas-indenizatorias`; projetos → `https://transparencia.alepe.pe.gov.br/proposicoes`; remuneração → `https://transparencia.alepe.pe.gov.br/financas/remuneracao-ajuda-deputados` (a confirmar).
4. Se seguir: `scripts/coletar_pe.py`, amostras em `tests/fixtures/contratos/`, `ENDPOINTS.md` e `CHANGELOG.md`.

### RJ: Rio de Janeiro (Assembleia Legislativa, ALERJ; apurado em 2026-10-22)

**Portal de transparência: `https://transparencia.alerj.rj.gov.br/`.** Livre, sem login. Organizado em relatórios `https://transparencia.alerj.rj.gov.br/section/report/<n>`; só li o índice, não abri cada relatório (formato de exportação e API não confirmados; o índice não cita CSV nem dados abertos).
- Deputados: lista de presença `/17`; benefícios `/33`; subsídio `/62`; folha de pagamento `/73`; DOCIGP (descentralização orçamentária) `http://docigp.alerj.rj.gov.br`; Resolução 178/2019, art. 2º `/107`; sinopse da atividade legislativa (Anuário) `/114`.
- Viagens autorizadas `/66`; diárias `/119`.
- Servidores e estagiários: benefícios `/72`; folha `/73`; tabela remuneratória `/103`; estagiários `/74`, `/75`, `/96`.
- Orçamento e finanças: gestão fiscal, relatório anual, execução orçamentária, contratos, pagamentos, gastos do Legislativo em `/76`, `/98`, `/104`, `/117`, `/118`, `/120`; licitações em sistemas em `www2.alerj.rj.gov.br`.
- Emendas parlamentares impositivas `/121` e acompanhamento da execução `/134`; LOA, PPA, LDO e pareceres `/108` a `/115`; prestações de contas `/125`, `/129`, `/130`, `/132`; LAI `/57` a `/61`, `/88`.
- Não há menção a verba indenizatória/cota parlamentar nem a gabinete no índice (o DOCIGP pode cobrir a descentralização de verba; conferir).

**ITGP** (`https://transparenciainternacional.org.br/itgp/assembleia-legislativa/rio-de-janeiro`, ano da avaliação não informado): nota **24,4/100 ("Ruim")**, 24º de 27. Por dimensão: Comunicação 72,7; Transparência Legislativa 29,2; Transparência Administrativa 27,8; Governança 23,5; Plataformas 20; Participação e Engajamento 12,5; Transformação Digital 10; Marcos Legais 0 (a página deixa dúbio o pareamento das duas últimas; conferir na fonte).

Próximos passos:
1. No Firefox, abrir `/17` (presença), `/33` (benefícios), `/73` (folha), `/119` (diárias), `/121` e `/134` (emendas) e o DOCIGP com a aba Rede aberta, para ver a chamada de dados (URL, parâmetros) e se há exportação.
2. Achar a fonte de projetos e votações (o Anuário `/114` é só sinopse) e de verba/ cota por deputado.
3. Fonte de link por dado: presença → `https://transparencia.alerj.rj.gov.br/section/report/17`; diárias → `.../report/119`; emendas → `.../report/121` (a confirmar).
4. Se seguir: `scripts/coletar_rj.py`, amostras em `tests/fixtures/contratos/`, `ENDPOINTS.md` e `CHANGELOG.md`.

### RN: Rio Grande do Norte
### RR: Roraima
### RS: Rio Grande do Sul
### SC: Santa Catarina
### SE: Sergipe
### SP: São Paulo
