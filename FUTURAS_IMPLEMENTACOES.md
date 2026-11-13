# Futuras implementações

Ideias levantadas e ainda não feitas, em ordem de complexidade. O que já foi implantado está no `CHANGELOG.md`
(autoria, cota, salário, campanha e patrimônio, perfil das Casas, presença e votações, recursos do senador,
perfil temático, discursos e eventos, aposentadoria de ex-senadores, carreira, vida do projeto, rede de coautoria, fornecedores com dados da Receita e cruzamento com
doadores, recursos, pessoal, verba e presença em plenário do deputado pelo portal, despesa com pessoal e das Casas pelo SICONFI, ministros de Estado em sua primeira etapa, coletores de 17 Assembleias, página das Assembleias como órgão).

Ao implementar um endpoint novo, registre-o no `ENDPOINTS.md` e o conjunto no `CHANGELOG.md`.
Revisado em 2026-11-09 contra o código, os dados em `dados/` e o `CHANGELOG.md`.

**Resumo**

| Nível | O que exige | Pacotes |
|---|---|---|
| 1 | Acabamentos do que já existe | 1.1 Restos de pacotes feitos |
| 3 | Raspagem de HTML ou chave de API | 3.2 Emendas e Portal da Transparência · 3.3 Ministros de Estado: o que fica para depois · 3.4 Ministérios em números · 3.5 Atuação de cada ministro |
| 4 | Fontes grandes, sem padrão ou cruzamentos sensíveis | 4.1 Fornecedores e doadores · 4.2 Assembleias e Câmaras Municipais · 4.3 Ministros dos tribunais superiores · 4.4 Órgãos de controle (resto) · 4.5 Assembleia do Paraná: portal e webservices (2026) · 4.6 Levar às outras Assembleias o que o PR coleta · 4.7 Dados coletados que o site ainda não mostra |

## Nível 1: acabamentos

### 1.1 Restos de pacotes feitos

- **Pular até ter os dados** (não implementar enquanto a fonte não existir):
  - **Comissão x tema:** "projetos na área da comissão que ele integra"; a Câmara não publica o tema de cada comissão.
  - **Fidelidade em blocos:** os blocos usam a composição atual e rótulos que não constam em `/blocos` seguem sem
    fidelidade; a presença em reuniões de comissão não tem total para comparar.
- **Perfil dos eleitos:** a bancada federal já usa a composição de hoje; Assembleias, Senado e Câmaras Municipais seguem com
  os eleitos de 2018/2022/2024 (suplentes que assumiram não entram).

## Nível 3: raspagem ou chave de API

### 3.1 Recursos do deputado no portal da Câmara

Feito em 2026-10-29: benefícios, pessoal (contagem por grupo), verba de gabinete (ano corrente e anteriores da legislatura) e
presença em plenário com ausências justificadas, raspados do portal (`coletar_recursos_camara`, ver `CHANGELOG.md`).
Raspagem é frágil: fonte opcional, com teste de contrato em `scripts/contrato_apis.py`.

### 3.2 Emendas e Portal da Transparência

**Emendas feitas em 2026-10-30** (chave no secret `PORTAL_TRANSPARENCIA_CHAVE` do Actions): coletor
`coletar_emendas.py`, ligação do autor por nome, `site/dados/emendas/<pessoa>.json` e painel na ficha (ver `CHANGELOG.md`).
Conferido em 2026-11-09: o Actions já coletou 2019 a 2026 (`dados/emendas/`, 54 mil linhas), o campo é `autor` e o tipo das Pix
vem como "Emenda Individual - Transferências Especiais" (5.108 linhas). Ligaram 553 autores (`nome+cargo`) e 747 ficaram sem
ligação (`semLigacao.emendas`; vale ver quantos são bancada, comissão ou nome repetido). Falta: medir o tempo da coleta no
Actions, conferir quantos municípios casam com o IBGE e regravar `tests/test_coletar_emendas.py` com amostra real em
`tests/fixtures/contratos/` (hoje o teste usa dados inventados).

Ainda não feito, com a mesma chave:
- Totais por área (função) das emendas.
- Emendas Pix com o favorecido e o plano de ação do Transferegov (hoje só o município e os valores do Portal da Transparência).
- Viagens a serviço e cargos do Executivo federal (ver 3.3).

### 3.3 Ministros de Estado: o que fica para depois

Já existem o coletor da lista do Planalto, requerimentos de informação, convocações e licenças, a ligação às
pessoas, as páginas `ministerios.html` e `ministro.html` e os eventos no histórico. Limites atuais: o Planalto não
publica a data da posse (o início vem da Wikipédia, anotada à mão em `scripts/ministros_posse.json` com o presidente que nomeou; sem ela, da licença do parlamentar ou do dia em que a coleta viu o nome) e a resposta a
requerimento do Senado não é coletada. Levantado em 2026-10-29 e ainda não refeito:

| Ideia | Fonte | Situação em 2026-10-29 | O que daria no site |
|---|---|---|---|
| Data de nomeação e exoneração, interinos | DOU: busca `www.in.gov.br/consulta/-/buscar/dou` (HTML com JSON embutido) ou INLABS (`inlabs.in.gov.br`, exige cadastro) | busca devolveu HTTP 502 duas vezes; INLABS em "Manutenção Programada" | "No cargo desde/até" exatos e link para o decreto |
| Portarias, instruções normativas e resoluções assinadas | DOU (mesmas fontes) | não medido | aba "Atos" e eventos no histórico diário; filtrar só atos normativos, o volume é grande |
| Exposições de motivos de MPs e PLs do Executivo | texto do documento (Câmara `inteiroTeor`, Planalto) | a assinatura não vem em campo da API, só no texto | ligar as propostas de `dados/executivo.json` ao ministro que assinou, não só à Presidência |
| Decretos presidenciais referendados | DOU / Planalto (legislação) | não medido | lista de decretos com a assinatura do ministro |
| Salário, viagens a serviço, cartão corporativo, jetons de conselhos de estatais | API do Portal da Transparência (chave do 3.2) | não medido (falta a chave) | abas de gastos e histórico de viagens; os dados chegam com semanas de atraso |
| Agenda de compromissos | e-Agendas (CGU) | não medido | só reuniões com empresas e entidades privadas; a agenda inteira vira ruído |
| Votos em conselhos (CMN, CNPE, Conama) | atas de cada conselho | não medido | costuma sair só a decisão, sem o voto de cada membro |
| Posse do ministro do Empreendedorismo (Paulo Henrique Rodrigues Pereira) | a definir (Wikipédia desatualizada: ainda mostra Tadeu Alencar) | sem data de posse; hoje vale o dia em que o Planalto passou a listá-lo | completar `scripts/ministros_posse.json` com data e `fonte` |
| Ministros anteriores (antes da primeira coleta) | DOU | depende da busca do DOU | histórico de cada pasta em `ministerios.html` |
| Resposta a requerimento do Senado | API do Senado | não coletada | fechar o ciclo pedido-resposta também para RQS |

Descartado: Wikidata (consulta SPARQL de 2026-10-29 trouxe 6 ministros sem data de saída, parte já fora do cargo).

### 3.4 Ministérios em números

A descrição de cada pasta (camada 1) está feita (ver `CHANGELOG.md`). **Restos da descrição:**
- `vinculados` só existe em 10 pastas, copiados da página de vinculadas do ministério em gov.br. As outras 28 não têm página
  utilizável (Minas e Energia e Justiça têm, mas incompleta). A fonte seria o decreto de estrutura de cada pasta, que o
  Planalto bloqueia para coleta automática; conferir à mão ou de outro ambiente.
- Alterações legais posteriores à Lei 14.816/2024 não foram conferidas pasta a pasta. Reforma ministerial deixa o texto velho:
  revisar `scripts/ministerios_descricao.json` (e `revisadoEm`) junto com cada mudança em `ministerios.PASTAS`.

Depois da descrição, números de cada ministério em `ministerios.html?pasta=...`:

| Ideia | Fonte | Situação em 2026-10-30 | O que daria no site |
|---|---|---|---|
| Orçamento: dotação, empenhado e pago por ministério | Portal da Transparência (chave do 3.2) ou SIOP | não medido | "A pasta tem R$ X bi este ano e pagou Y%", com série por ano |
| Servidores da pasta | Painel Estatístico de Pessoal | não medido | quantos servidores e quanto custam |
| Contratos e convênios | Portal da Transparência | não medido | maiores fornecedores da pasta, ligados a `nucleo/fornecedores` |
| Pedidos do Congresso por assunto | já em `ministerio/<pasta>.json` | dados existem | "sobre o que mais perguntam a esta pasta" |

Exige ligar o código de órgão do orçamento à chave de `PASTAS` (tabela versionada, não por nome) e, para valores,
normalizar como o resto do projeto (`valor_br`, ids por `ids.gerar_id`).

### 3.5 Atuação de cada ministro

O que o cargo comporta vem da camada 1. A atuação da pessoa, além do que já existe (pedidos durante o mandato, tempo no
cargo, licença do parlamentar):

| Ideia | Fonte | Situação em 2026-10-30 | O que daria no site |
|---|---|---|---|
| Projetos, votos e licenças de quem veio do Legislativo | dados da Câmara e do Senado já coletados | dados existem | resumo do mandato anterior na página do ministro |
| Agenda de compromissos | e-Agendas (CGU) | ver 3.3 | só reuniões com entidades privadas |
| Atos assinados (portarias, instruções normativas) | DOU | ver 3.3 | aba "Atos" |
| Votos em conselhos | atas | ver 3.3 | ver 3.3 |

## Nível 4: fontes grandes, sem padrão ou cruzamentos sensíveis

### 4.1 Fornecedores e doadores

Dados da empresa pela Receita e cruzamento com doadores de campanha (por CNPJ, contas na versão 4) já existem. Falta:
- Fora do escopo por ser sensível: cruzar sócio com político ou parente.

### 4.2 Assembleias e Câmaras Municipais

Sem padrão nacional; cada Casa publica do seu jeito.

- Salário exato de deputados estaduais e vereadores: portal de transparência de cada Casa.
- **SICONFI / Tesouro Nacional:** já temos a despesa com pessoal do Legislativo de cada UF (RGF) e a despesa total da
  função Legislativa dos estados (DCA, coletada em 2026-10-29). O "custo por parlamentar" das Assembleias já aparece no
  mapa; a DCA das Câmaras Municipais (uma consulta por município, incremental) também, coletada em 2026-10-29.
- **Querido Diário** (Open Knowledge Brasil): testado em 2026-10-29, **não implementar por ora**. A API mudou para
  `https://api.queridodiario.org.br` (o domínio antigo redireciona; a rota `/gazettes` responde 405 sem seguir o redirect) e
  oscila (HTTP 520 e timeout em tentativas seguidas). Só 510 dos 5.570 municípios têm diário coletado (`level` 3, ~9%);
  o resto é `level` 0 ou 1, sem texto pesquisável. A busca por texto (`/gazettes?querystring="subsídio dos vereadores"&territory_ids=...`)
  acha a resolução certa (Campinas: R$ 10.070,86 para 2021-2024, resolução 977/2020), mas o valor vem solto em trecho de PDF,
  sem campo estruturado: extrair exigiria regex por trecho e conferência por cidade, e erro aqui vira dado errado sobre
  político. Só valeria para as capitais e cidades grandes cobertas, com link do PDF como fonte. Se for feito, registrar
  o host no `ENDPOINTS.md`.
- Autoria das Assembleias: coautores e total de autores já saem (2026-10-29). Falta o autor principal e o partido dos
  coautores: as fontes não garantem a ordem de assinatura e o partido só chega pelo TSE depois da geração das fichas;
  o Senado também ainda não tem partido dos coautores e total.

### 4.3 Ministros dos tribunais superiores

Feito em 2026-10-30: a composição atual dos seis tribunais (`coletar_tribunais.py`, página `tribunais.html`), lida da
Wikipédia porque os sites oficiais bloqueiam coleta automática (ver `CHANGELOG.md`). Falta:
- (Feito: `identidades.ligar_tribunais` liga o ministro à pessoa do núcleo pelo nome civil, só com mandato na Câmara ou no
  Senado; 106 sem par em 2026-11-09, esperado para quem nunca foi parlamentar.)
- Fonte oficial da lista, se algum tribunal liberar: o bloqueio é por WAF e pode passar de outra rede ou do Actions.
- Ministros anteriores (antes da primeira coleta) e substitutos do TCU (auditores).
- Votos em julgamentos, decisões monocráticas e pedidos de vista (equivalente às abas de votações e propostas); fontes de cada tribunal ainda não levantadas.

### 4.4 Órgãos de controle

- **TCU, inabilitados:** feito em 2026-10-29 (`coletar_tcu.py`, `identidades.ligar_inabilitados`, aviso na ficha; ver `CHANGELOG.md`).
  Os `inidoneos` (proibidos de licitar, só CNPJ) também foram feitos em 2026-10-29: aviso nos fornecedores por CNPJ.
  Hoje o cruzamento de inabilitados dá zero ligações (5 nomes iguais, todos homônimos de outra UF), porque o TSE não
  publica CPF; o aviso aparece sozinho quando surgir um caso com nome e UF iguais.

### 4.5 Assembleia do Paraná: portal e webservices (levantado em 2026-10-31)

**Foco: só 2026.** Coletar apenas 2026 (o `PRIMEIRO_ANO` de 2023 do coletor continua para o que já existe); 2023 a 2025 ficam
como carga futura, com a cobertura abaixo medida para decidir.

O coletor atual (`coletar_estadual_pr.py`) usa remuneração, diárias, presença por sessão e proposições. O portal
`transparencia.assembleia.pr.leg.br` e os webservices têm mais. Os 46 endpoints novos estão registrados no `ENDPOINTS.md`
(grupo "Assembleias (estaduais)", nomes `pr_t_*`, `pr_storage_*`, `pr_webservices_*`). O `/api/` do portal só responde com
`Accept: application/json` e `X-Requested-With: XMLHttpRequest`; o `testar_endpoints.py` passou a mandar os dois para esse host.
Em 2026-10-31 três seguem com erro, sem ser falha do site: `pr_t_presenca_mensal` (404 em todo mês testado) e
`pr_t_rreo` e `pr_t_gestao_fiscal` (403: exigem reCAPTCHA).

**Cobertura dos ZIPs de voto nominal (medida em 2026-10-31):**

| Ano | Sessões | Com ZIP | Itens votados | Planilhas (itens com voto nominal) |
|---|---|---|---|---|
| 2023 | 153 | 137 (90%) | 1.512 | 1.215 (80%) |
| 2024 | 126 | 108 (86%) | 1.379 | 1.048 (76%) |
| 2025 | 139 | 124 (89%) | 1.801 | 1.185 (66%) |
| **2026** | **105** | **87 (83%)** | **958** | **687 (72%)** |

- Todas as planilhas são `NOMINAL`: uma linha por deputado (parlamentar, partido, voto), com item, projeto, autores, ementa,
  sessão, data, turno, quórum, presentes, presidência e resultado. O ZIP traz uma planilha por item.
- Sem ZIP em 2026 (18 sessões): extraordinárias, audiências públicas e sessões recentes. Em outubro só 2 de 10 sessões têm ZIP
  (as de 27/10 ainda dão 404), então o ZIP sai com atraso: reler os últimos 45 dias a cada coleta.
- Votação simbólica e item sem planilha só têm o PDF (campo `arquivo` de `/api/votacoes`); fica como link, sem voto por deputado.

**Pacotes, em ordem de valor** (todos seguem "Dados sem duplicação" e "Coletores de Assembleias estaduais" do `CLAUDE.md`):

| Pacote | Fonte | O que daria no site | Observações |
|---|---|---|---|
| 1. Voto nominal por deputado | `/api/votacoes/{meses,datas,sessoes}` (a sessão vem por dia, com `data=<dia>`, não por data completa), `/api/votacoes` (itens e PDF), `/api/votacoes/dados-abertos?sessao=<id>` (JSON com a URL do ZIP em `storage2.assembleia.pr.leg.br`) | aba de votos na ficha do deputado estadual; alinhamento ao partido e ao governo; presença em votação | Planilha: ler com `openpyxl` ou XML (o `sharedStrings` não serve, repete valores). Id da votação por `ids.gerar_id` de `alep_pr` + sessão + item; guardar sessão, item e URL do ZIP e do PDF como fonte. Deputado por `identidades.ligar_nomes` (UF PR; o nome vem civil, ex. "PEDRO PAULO BAZANA"), partido da planilha só como informação. Projeto ligado à proposição por tipo, número e ano do título. Incremental: sessões já lidas ficam guardadas; reler as dos últimos 45 dias e as sem ZIP. |
| 2. Normas legais (feito em 2026-10-31, coleta e ficha) | `POST /norma-legal/filtrar`, `GET /norma-legal/{código}` (webservices; leis, decretos legislativos, resoluções: tipo, número, ano, ementa, autores, Diário Oficial, movimentações, proposições ligadas) | "leis de sua autoria" e a lei que nasceu de cada projeto; fecha o ciclo da proposição | Autor vem como texto; ligar por `ligar_nomes`. `dataInicial` evita reler o ano. Registrar o host `http://` (sem HTTPS). |
| 3. Proposições pelo webservice, incremental (feito em 2026-10-31: só a proteção contra lista vazia; sem incremental, ver CHANGELOG) | `POST /proposicao/filtrar` com `dataInicial`; `GET /proposicao/campos` (tipos, assuntos, situações) | menos tempo de coleta; tabela de situações oficial | `GET /proposicao/{código}` está quebrado no servidor (erro Oracle `ORA-00942`, com HTTP 200 e `sucesso:false`), então os trâmites não vêm; o testador acusa "OK" por isso. Revisar a cada trimestre. |
| 4. Pautas e atas (feito em 2026-10-31: links na votação; sem ligação à proposição, ver CHANGELOG) | `/plenario/pautas/{ordem-do-dia,ccj,comissoes-tematicas}/ajax`, `/plenario/atas-sessoes-plenarias/ajax` | "na pauta desta semana" na proposição; link da ata na sessão | Arquivos em PDF; ligar item da pauta à proposição pelo número e ano. Sem partes estruturadas. |
| 5. Gabinete do deputado (feito em 2026-10-31: servidores por símbolo e nome; sem valores, ver CHANGELOG) | `/api/remuneracao/recente` (matrícula, nome, símbolo do cargo, lotação, ex.: "GAB. DEP. FULANO"); páginas `/pessoal/comissionados`, `estaveis`, etc. | tamanho e composição do gabinete (como na Câmara: contagem por grupo) | Ligar a lotação ao deputado em `ESTRATEGIAS`, nunca por função própria. Decisão (2026-10-31): mostrar o nome do servidor só se a lotação ligar ao deputado de forma única por `ligar_nomes` (ambígua ou sem par: só a contagem por símbolo); o "Mapa dos dados" segue sem nomes de pessoas. Sem valores: o salário já vem de `/api/remuneracao/{matrícula}`. |
| 6. Presença e diárias mais enxutas (medido em 2026-10-31: sem ganho, não implementar) | `/api/presenca/{meses,datas}`, `/api/diarias/ultimo-periodo` | menos requisições; saber o último mês publicado sem testar um a um | `presenca/mensal` devolve 404 sempre; só reavaliar. Medição: `/api/presenca/ano` é 1 requisição de 109 KB em 0,6 s (57 sessões) e já traz todas as sessões, então `meses`/`datas` só acrescentariam requisições; `/api/diarias/meses` (0,3 s) já lista o que `ultimo-periodo` informa (`{ano, mes}`), e o coletor já lê só os 2 últimos meses. Reabrir só se o `presenca/ano` passar de alguns segundos. |
| 7. Monitorar o que vem vazio (feito em 2026-10-31: só o aviso automático; nada publicado ainda) | `/api/ressarcimento` (POST; `meses` lista só janeiro de 2026 e o POST volta `data: []`), `/api/passagens`, `/api/cartoes`, `/api/estoque` | verba de ressarcimento, passagens e cartões, se publicarem por deputado | 200 sem registros em 2026 (medido em 2026-10-31). O POST de ressarcimento é formulário `ano`+`mes` (o portal manda também reCAPTCHA e CSRF; sem eles o servidor responde igual, `data: []`, e `mes` vazio dá 400); `cartoes/meses` dá 404 e `estoque/meses` vem vazio; `cartoes` tipo 2 traz só rendimentos do cartão de pagamento do órgão (R$ 135 a 151 por mês, sem deputado), fora do monitor e do pacote 8. O coletor chama `avisar_publicados` e avisa quando qualquer um passar a trazer dados; aí levantar o formato, gravar amostra em `tests/fixtures/contratos/` e coletar. O portal exibe o ressarcimento como arquivos por deputado, então pode vir só PDF. |
| 8. Despesas do órgão (não são de deputado; feito em 2026-10-31 para contratos, atas e regras do ressarcimento, só dados, sem tela) | contratos, licitações, dispensas, atas de registro de preço e de adesão, obras, ordem cronológica, SIAFIC, receitas, atos normativos (`/api/atos-normativos?tipo=4`, atos do presidente, e o de ressarcimento da atividade parlamentar) | maiores fornecedores da Assembleia, ligados a `nucleo/fornecedores` por CNPJ; regras da verba | Feito: contratos, atas de registro e de adesão (`orgao_<ano>.json`, `site/dados/orgao/PR.json`) e a resolução 06/2025 do ressarcimento como link (`regras_ressarcimento.json`); ver CHANGELOG. Falta: tela com os maiores fornecedores; ligar o contrato ao fornecedor (só traz nome, sem CNPJ); dispensas (403 em `/api/dispensas`, achar o caminho da página); licitações (`tipo` obrigatório); obras; ordem cronológica; SIAFIC (vazio); receitas (HTML). O ato de ressarcimento da atividade parlamentar vale ler primeiro: explica o que a verba cobre. |
| Fora | `/api/rreo`, `/api/gestao_fiscal` | | Exigem reCAPTCHA. A despesa com pessoal e o RGF já vêm do SICONFI (4.2). |

**Antes de cada pacote** (regras do projeto): endpoint já está no `ENDPOINTS.md`; amostra real em `tests/fixtures/contratos/`
(`CONTRATOS` do coletor) e teste offline em `tests/test_coletar_estadual_pr.py`; ligação em `identidades.py`; entrada no
`CHANGELOG.md` e no `site/mapa-dados.html`; fonte com link ao lado de cada dado (votos: URL do PDF e do ZIP da sessão; normas:
página da norma). Medir uma coleta do zero e uma com cache e anotar no `CHANGELOG.md`; o job do PR já tem prazo próprio.

### 4.6 Levar às outras Assembleias o que o coletor do PR coleta (levantado em 2026-10-31)

Objetivo: deixar os 16 coletores próprios (BA CE ES GO MG MS MT PA PE RJ RN RR RS SC SE SP) parecidos com o do PR:
proposições, normas legais com autoria, voto nominal, presença, diárias, remuneração, gabinete, pautas e atas, contratos e atas
de registro de preço do órgão, regras da verba. **Fora do escopo: os 7 estados do SAPL genérico** (AC AL AM PB PI RO TO),
a pedido do usuário. Só pesquisa; nada implementado. Relatório completo por estado (URL, método, parâmetros, campos,
amostra, esforço, risco) em `docs/levantamento_estaduais/<UF>.md`.

**Antes de implementar um estado:** reler o relatório da UF, refazer o teste do endpoint (a pesquisa foi uma passada só, em
2026-10-31), registrar o host no `ENDPOINTS.md`, gravar amostra em `tests/fixtures/contratos/` e seguir as regras de
"Coletores de Assembleias estaduais" e "Dados sem duplicação" do `CLAUDE.md` (incremental, prazo, teste offline, ligação por
`identidades.ligar_nomes` com entrada em `ESTRATEGIAS`, `CHANGELOG.md`, `site/mapa-dados.html`).

**Não testados ao vivo (sem resposta desta rede; testar do Actions ou de outra rede antes de qualquer trabalho):**
ES (www.al.es.gov.br e www3 dão timeout), MG (ALMG; relatório baseado em Wayback), RS (ww2.al.rs.gov.br; DNS e timeout),
SE (aleselegis.al.se.leg.br recusa conexão: proposições, normas, voto e presença), GO (alegodigital reseta a conexão:
proposições), MT (www.al.mt.gov.br dá timeout: proposições, normas, voto, presença, pautas, atas), RJ (curl em alerjln1 deu
"Empty reply"; páginas lidas só por WebFetch, em resumo), RR (sapl.al.rr.leg.br responde 403).

**Andamento (2026-11-01):**
- **PA feito e commitado** (`066fa803`): voto nominal (155 votações; 4 nomes de urna sem ligação: Delegado Toni Cunha, Eliel Faustino, Igor Normando, Torrinho Torres), normas (sem autoria), pautas e atas, contratos e licitações/registro de preço, gabinete (`srv_`) e remuneração. Ver `CHANGELOG.md`. Falta no PA: **proposições** (paginação do pager DevExpress não resolvida; usar janela de datas ou inspecionar no DevTools); **remuneração 2026 só de janeiro a maio** (a coleta foi interrompida; o Actions completa, conferir) e tempo do zero não medido; anexos de contratos (URL não achada).
- **CE, PE, SC, GO, MT e RR commitados** (`2cc4eef0`, `2cc1013a`).
- **RN, SP, RJ, SE, MS e BA feitos em 2026-11-02 e commitados** (`e85eeb26`). Detalhes de cada um no `CHANGELOG.md`. Pendências:
  - RN: coleta do zero 18 min; gabinete, remuneração, verba e regras exigem token do site (não usado).
  - SP: coleta do zero ~30 min, acima dos 25 min do job `sp` (a primeira no Actions fecha na segunda execução); gabinete parado em 2023.
  - RJ: só as normas de 2023 e 2024 foram coletadas ao vivo (parciais); proposições, pautas, atas e órgão só testados em amostra; resoluções de 2025 e 2026 batem o teto de 1000 linhas (divisão por deputado não exercitada ao vivo). `site/dados/orgao/RJ.json` já existe.
  - SE: diárias e folha de 2023-2024 fora; Alese Legis segue recusando conexão; `pypdf` entrou em `requirements.txt`.
  - MS: hosts em `ENDPOINTS.md` como "não testado" (rodar `scripts/testar_endpoints.py`); `verbas_2026.json` foi restaurado por `git checkout` após a coleta.
  - BA: presença 2021 a 06/2025, contratos e regras da verba; atas de registro de preço fora.
- **Próximos:** ES, MG, RS dependem de acesso (testar do Actions ou de outra rede). Conferido em 2026-11-09: `coletar_estadual_es.py`,
  `_mg.py` e `_rs.py` não têm nada de órgão, pautas, gabinete ou normas, e `dados/estaduais/PA/` não tem proposições
  (nem `materias_<ano>.json`).

**Ordem sugerida** (mais valor com menos esforço primeiro): CE, PE, SC, depois GO, PA, MT, RR, RN, SP, RJ, SE, MS; BA só três
itens; ES, MG e RS dependem de abrir o acesso.

| UF | O que já coleta | Encontrado (esforço) | Bloqueado, parcial ou não publica |
|---|---|---|---|
| CE | deputados, diárias, ligações, proposições, matérias votadas, remuneração, verbas, votações | **Contratos e atas de registro de preço**: API JSON `transparencia.al.ce.gov.br/api/contratos` (90 páginas de 20, 1.790 linhas, sem chave; CSV completo com 2.098 linhas e órgão solicitante) (baixo). **Gabinete**: lotação "GABINETE DEPUTADA X" no modal em base64 da página `/gestao-de-pessoas/pessoal` (o CSV não traz lotação), 36 a 172 requisições por mês (médio). **Regras da verba (VDP)**: PDFs em `/despesas/verba-desempenho-parlamentar` (baixo). **Proposições a mais**: `numero.php` tem `projeto_indi` (indicações) e `projeto_mens` (mensagens do Executivo), que o coletor não lê (baixo). **Pauta e expediente do dia**: `/legislativo/expediente` e `/legislativo/ordem-do-dia/avulso-de-projeto`, HTML e CSV; o expediente traz a autoria (baixo) | Presença: só proxy pela lista de oradores (`/legislativo/oradores-historico`, 2025 e 2026). Atas: busca 2023 a 2026 volta "Nenhum dado localizado". Leis promulgadas com autoria: não publica |
| PE | deputados, proposições, verbas | **Gabinete**: `dadosabertos.alepe.pe.gov.br/api/v1/servidores/?formato=json` (aceita `?ano=`), 1.281 servidores em 49 lotações "GAB.DEP. <nome>", ligação só por nome (baixo). **Contratos**: `/api/v1/contratos/` (652, de 2013 a 2026; `numeroContrato` repete o CNPJ, então o id estável precisa de outra chave) e `/api/v1/licitacoes/` (baixo). **Presença**: `www.alepe.pe.gov.br/reunioes/` e `/frequencia/?docid=` por reunião, HTML, com presentes, faltosos, missão autorizada e licenciados (médio). **Atas e expediente**: `/atas/?docid=`, `/expediente/?docid=`. **Normas com autoria**: `legis.alepe.pe.gov.br` (`lista.aspx?tiponorma=`, `texto.aspx?id=`), HTML ASP.NET, autoria no texto (médio a alto) | Voto nominal (atas só dizem "aprovado"), diárias e remuneração por deputado (só por cargo em `/api/v1/remuneracao/`): não publica. Atas de registro de preço: endpoint não achado (só na SPA). Regras do ressarcimento: não verificadas. Sem pauta antecipada |
| SC | deputados, diárias, ligações, presença, remuneração, verbas | **Proposições**: `portalelegis.alesc.sc.gov.br/proposicoes/processo-legislativo`, filtros `inicio` e `fim` servem de leitura incremental; número, ementa, data, autoria por nome (o comentário "sem exportação" do coletor está desatualizado). **Gabinete**: `transparencia.alesc.sc.gov.br/servidores?setor_id=<id>`, um id por deputado. **Contratos e atas de registro de preço**: `transparencia.alesc.sc.gov.br/contratos`, HTML com filtros e PDF por contrato. **Pautas e atas**: sessões (`ordem-do-dia`, `ata`), agenda e atas das comissões. **Regras da verba**: links em `leis.alesc.sc.gov.br/alesc/regulamentacao-interna` (HTML). **Extra**: `transparencia.alesc.sc.gov.br/pagamentos/csv/<ano>`, pagamentos e empenhos do órgão em CSV, 2011 a 2026 | Normas: busca sem exportação; melhor caminho é derivar a autoria da proposição que virou lei. Voto nominal: nas 19 sessões amostradas todos os itens eram "Votação simbólica"; pode existir extrato de PLC, confirmar exigiria varredura pesada |
| GO | deputados, diárias, ligações, proposições, matérias votadas, remuneração, verbas, votações | **Contratos**: `/contratos-e-convenios/contratos` (710, com aditivos e PDF). **Atas de registro de preço**: `/contratos-e-convenios/atas-de-registro-de-preco`. **Normas** (resoluções, decretos legislativos e administrativos, com PDF, **sem autoria**): `/legislacoes?tipo=&ano=`. **Regras do ressarcimento e das diárias**: Resolução 1.531/2015 (CEAP) e Decretos 3.017 e 3.018 em `/legislacoes`. **Votação simbólica e total de presentes**: `votacoes.json?tipo=resumo`. Tudo esforço baixo | Atas: `/atas_plenarias` só até 09/2023 (depois, alegodigital). Pautas: só agenda em HTML (`portal.al.go.leg.br/agenda?data=`), sem itens. Gabinete: lotação só "Gabinete Parlamentar". Presença: só derivada do voto. Proposições (projetos de lei): `processos/busca-avancada` vazio, `busca-simples` erro 500, alegodigital reseta (testar no Actions). Requerimentos: API só até 2023 |
| PA | deputados, diárias, ligações, presença, verbas, total mensal de gabinete | **Voto nominal**: HTML, lista mensal e detalhe por votação (SIM, NÃO, ABSTENÇÃO, NÃO VOTARAM), de 2015 em diante, ligação só por nome (médio); é o único estado fora o PR com voto nominal estruturado. **Normas**: API JSON `bancodeleis.alepa.pa.gov.br/api/leis.php`, 50 por chamada, sem autoria (baixo). **Pautas e atas** (links e PDF): callback mês a mês (baixo). **Contratos e licitações/registro de preço**: dashboards 52 e 59, mesma API que o coletor já usa (baixo; URL de download dos anexos não achada). **Gabinete** (lista de servidores): `sigep`, mas a resposta trunca em 103 linhas, então particionar a consulta (médio). **Remuneração por deputado**: `sigep` em dois passos (busca por nome e página de detalhe) (médio). **Proposições**: autor por nome, 10 por chamada, paginação não funcionou; particionar por janela de datas (alto; ver o pager no DevTools). O comentário "projetos e votações: sem fonte" no coletor está desatualizado | Regras do ressarcimento: não publica |
| MT | deputados, diárias, ligações, remuneração | **Gabinete**: portal Elotech `almt.eloweb.net/servidores?lotacao=GAB`, 2.005 servidores em 2026, 5 páginas; o filtro `situacao` não funciona; ligação pelo texto da lotação (baixo). **Contratos e atas**: `/contratos` (2023 a 2026, 91 a 129 por ano), atas são `tipoAto=2` (46 em 2026), PDFs em `/contratos/arquivos` e `/files/arquivo/{id}`, `/contratos/ultimas-atualizacoes` serve de incremental (baixo a médio). **Regras de diárias**: `/publicacoes` (resolução e tabela de diárias, resoluções administrativas, adesões a ARP) | Verba/ressarcimento: não publica (`/servidores/verbas`, `/reembolsos`, `/emendas-parlamentares` vazios). Proposições, normas, voto, presença, pautas e atas: bloqueado, só URLs vistas pela busca (`/proposicao`, `/parlamento/ordem-do-dia`, PDFs em `storage.al.mt.gov.br`); o SAPL `sapl.al.mt.leg.br` está abandonado (2015 a 2018) |
| RR | deputados, diárias, ligações, verbas | **Gabinete**: XLSX mensal `CONSULTA SERVIDORES.xlsx` em `transparencia.al.rr.leg.br/.../gestao-de-pessoal-a-partir-de-set25/`, setor "GAB. DEP. <NOME>", 24 gabinetes, ligação por nome; mesma lista de arquivos (WP Display Files) que o coletor já lê (baixo). **Contratos**: pastas por processo com PDFs em `contratos-a-partir-de-out25`, só links estruturados (médio). **Licitações e contratações diretas**: XLSX mensal em `licitacoes-a-partir-de-out25` (colunas não inspecionadas). **Outras páginas do portal `transparencia.al.rr.leg.br/execucao-orcamentaria-e-financeira/` vistas em 2026-11-09 (só índice e links; arquivos não baixados) e que o coletor não usa**: histórico anterior (`gestao-de-pessoal-ate-ago-25/`, `verbas-indenizatorias-de-gabinete-ate-ago25/`, `diarias-e-passagens-ate-set25/`, `repasses-ate-set25/`), `resumos-da-folha-a-partir-de-set25/` e `resumos-da-folha-ate-ago25/` (PDF), repasses do Estado à Assembleia (`repasses-a-partir-de-out25/`), `/index.php/execucao-orcamentaria-e-financeira/despesas/`, `gestao-fiscal-intro/`, `/planejamento-e-prestacao-de-contas-intro/lei-orcamentaria-anual/` (LOA), `/prestacao-de-contas-intro/parcerias/` e a seção `/funesple/` (receitas, gestão fiscal, prestação de contas). Índices: `*-intro/` de cada tema. Falta baixar cada um para ver colunas e formato | Todo o `sapl.al.rr.leg.br`, inclusive PDFs de ata, responde 403 (proposições, normas, voto, presença, pautas, atas); o portal de transparência não tem essas áreas. Remuneração: só resumos de folha em PDF (links acima). Diário Oficial (`diarios.al.rr.leg.br`): PDF com texto, sem estrutura, normas só com esforço alto e baixa precisão |
| RN | deputados, proposições, matérias votadas, presença, votações | **Contratos e atas de registro de preço**: PNCP com o CNPJ da Assembleia (08493371000164), em 2026 116 contratos e 200 atas; janela máxima de 365 dias, ler ano a ano (baixo). **Pautas**: `processo?reuniao=<id>&faseReuniao=1\|2` na API legislativa aberta, liga ao deputado por id (baixo). **Atas**: link em `api-legisvideos.al.rn.leg.br`, cobertura parcial, formato do PDF não verificado. **Normas**: a API filtra por tipo e data, mas o número oficial da lei não é confiável; usar `publicacao[].linkDOE` e a tramitação. **Extras**: comissões, bancadas, cargos em comissão | Gabinete, remuneração, verba e regras do ressarcimento: exigem token embutido no site (não usado; alternativa é pedir acesso à Assembleia). Diárias: `api-transparencia/diarias` aberta mas só servidores, quase vazia, com registro de teste |
| SP | deputados, ligações, proposições, presença, remuneração, verbas | **Normas com autoria**: XML `legislacao_normas.zip` (sem autor) e API do portal `/processo/detalhes/todos/PL/<ano>/<n>` com `urlNorma` e `autores`. **Pautas e atas**: `/sessoes-plenarias/consulta`, `/sessoes-plenarias/{id}/integra`, `/colegiado/reunioes`. **Contratos e atas de registro de preço**: HTML `/alesp/contratos/` e detalhe com CNPJ e valores (não usar `/processo?listaIdTipoProcesso=134`: traz ofícios do TCE). **Regras da verba**: links das normas (Ato 02/2002, Resolução 822/2001, Resolução 824/2002), HTML | Voto nominal de plenário: só resultado e PDF; existe voto de comissão por deputado em `comissoes_permanentes_votacoes.xml`. Diárias: não publica. Gabinete: `funcionarios_lotacoes.xml` e `funcionarios_cargos.xml` ligam por nome, mas estão parados em 2023 |
| RJ | deputados, emendas, ligações, presença | **Normas com autoria**: `alerjln1 contlei.nsf/LeiOrdInt`, `LeiCompInt`, `DecretoInt`, `ResolucaoInt`. **Proposições**: `scpro2327.nsf/Internet/*Int`, lista com autor, mais nova primeiro. **Pautas plenárias**: `ordemdia.nsf/OrdemInt`. **Atas de comissões**: `compcom.nsf/AtasInt`, `comtemp.nsf/AtasInt`. Baixo a médio, ligação só por nome. Em PDF: contratos (`/section/report/118`), atas de registro de preço (`/51`), folha (`/73`), diárias (`/119`, as da amostra são de servidores civis); subsídio (`/62`) em HTML, só o valor atual | Voto nominal 2023 a 2027: só a pauta, sem resultado. Gabinete: a folha mostra lotação só "DEPUTADO ESTADUAL". Regras e despesas do ressarcimento: não publica. Formato exato (campos, paginação) a confirmar com `comum.sessao()`; `deputadosint` e `DecretoInt` deram "socket hang up"; PDFs de ARP, `docigp.alerj.rj.gov.br` e licitações em `www2` não abertos |
| SE | deputados | Tudo em PDF de texto, listado por `al.se.leg.br/wp-json/wp/v2/pages?slug=<slug>` com link `?wpdmdl=<ID>`: **ressarcimento** (um PDF por mês: deputado, inciso do art. 4º, valor; sem fornecedor nem CNPJ) (baixo a médio); **remuneração** (folha completa mensal) (médio); **gabinete** (coluna Lotação "GABINETE DO DEPUTADO X" do mesmo PDF) (médio); **diárias** (layout quebrado em várias linhas) (médio a alto); **contratos e atas de registro de preço** (830 itens, só título e link) (baixo) | Proposições, normas, voto, presença (e talvez pautas e atas): só no Alese Legis (`aleselegis.al.se.leg.br`), que recusa conexão nas portas 80 e 443. "Atas das sessões" do portal é iframe do webmail |
| MS | deputados, ligações, verbas | **Pautas** (do dia, sem histórico): `al.ms.gov.br/Pauta` e `/Ordemdodia`, HTML sem captcha, com projeto, processo, deputado autor e ementa. **Remuneração**: PDF mensal "Deputado Estadual" em `www.transparencia.al.ms.gov.br/pages/index.php/gerdocumento/1201`, 2020 a 2026, `pdftotext` lê mas o layout é frágil. **Contratos, atas de registro de preço e atas de sessão**: só PDFs em pastas por tipo e ano, sem fornecedor nem valor (links). **Verba**: página explicativa e PDFs de atos (fonte da regra) | Proposições e voto nominal: API do SGPL exige desafio proof-of-work SHA-256 (não resolvido). Gabinete: `transparencia2.al.ms.gov.br/consulta-servidores/data` traz 1.195 servidores mas sem lotação. Presença e normas com autoria: não publica (só PDF e lista JSON do Diário Oficial) |
| BA | deputados, emendas, ligações, proposições, pagamentos, verbas | **Presença**: `al.ba.gov.br/atividade-legislativa/frequencia-sessao/<id>`, por sessão e deputado, de 2021 a 18/06/2025 (depois migrou para o NoPaper, 403). **Contratos**: `.../transparencia/contratos-convenios?...&size=200`, 182 linhas de 2023 em diante, sem CNPJ; licitações com registro de preços em `licita.alba.ba.gov.br` (sem atas). **Regras da verba**: 8 PDFs em `/transparencia/verbas-regula`. Textos de sessão e ordem do dia em PDF, só até 06/2025 | Diárias: `portalrh.alba.ba.gov.br/transparencia-troca/0` (DataTables) mas em 2025 e 2026 só servidores. Remuneração: só o subsídio único de R$ 34.774,64, em PDF. Gabinete e normas com autoria: não publica (normas são atos da Mesa). Voto nominal: NoPaper dá 403, sem espelho no CKAN |
| ES | deputados, diárias, ligações, verbas, parcial | Diárias: CKAN do Estado `portal-da-transparencia-pessoal-diarias`, `Diarias-<ano>.csv` (283 MB em 2026), 117 linhas da ALES nos primeiros 3 MB; diárias de servidores e motoristas, o histórico cita o deputado (ligação por nome no texto, confiança baixa); ganho só o campo `CargoFuncao`. Contratos do órgão: só pelos pagamentos a fornecedores com UnidadeGestora = ALES no `Despesas-<ano>.csv` (sem número de contrato) | Tudo no site da ALES (proposições, normas, voto, presença, folha, gabinete, pautas, atas, contratos, regras) bloqueado por rede. O Observatório do Legislativo (`www3.al.es.gov.br/observatorio/`) tem painéis de leis, proposições e votações em plenário, sem API ou CSV confirmados (inspecionar os XHR). CKAN de pessoal e de contratos do Estado não incluem a ALES |
| MG | deputados, ligações, proposições, verbas | (Wayback, sem medir) **Pautas e atas**: API de plenário traz `uriPauta` e `uriResultado`; endpoint novo `plenario/reunioes/detalhes/...` (v2.1, 2025), não lido. **Contratos**: `prestacao_contas/contratos/indexados` (JSON, só vigentes). **Atas de registro de preço**: HTML `/transparencia/contratos/ARP/` com links para o PNCP. **Normas**: `legislacao/mineira/pesquisa/direcionada` com filtro de data, sem autoria. **Regras da verba**: Deliberação da Mesa 2.446/2009 pela API de legislação. **Foto**: `www.almg.gov.br/a-assembleia/deputados/legislatura-atual/fotos/{id}.jpg` (hoje o coletor grava `foto: None`) | Voto nominal e presença: não estão em nenhuma API; podem estar no resultado de plenário ou em `detalhes` (testar). Remuneração: só o subsídio fixo de R$ 34.774,64 e PDFs mensais agregados. Diárias e gabinete: não aparecem na transparência |
| RS | deputados (via TSE), diárias (CKAN) | Nada novo achado. Contratos do Estado no CKAN não têm a Assembleia | `www.al.rs.gov.br` e `ww2` com timeout ou ECONNREFUSED (45.179.62.33:443); `al.rs.gov.br` e `dados.al.rs.gov.br` não resolvem; CKAN `dados.rs.gov.br` sem pacote legislativo; painel de diárias em Power BI (a página manda pedir pela LAI). Repetir de outra rede |

**Observações transversais**
- Voto nominal por deputado em formato estruturado só existe no PR e no PA (CE, GO e RN já coletam o que têm; SC, SP, BA, PE e RJ não publicam).
- Gabinete por deputado: sem fonte em BA, GO, MS, RJ e SP; com fonte em CE, PE, SC, MT, RR, SE, PA. RN exige token.
- Contratos e atas do órgão (quando existem) não trazem CNPJ na maioria (BA, PE, GO, RR, SE, MS): só em SP, e via PNCP em RN. O vínculo a `nucleo/fornecedores` fica para depois, como no PR.
- Regras da verba como link: CE, GO, SC, SP, BA, MG, MS (como no `regras_ressarcimento.json` do PR).
- O job manual `.github/workflows/testar-hosts.yml` testa do Actions os hosts das Assembleias sem coletor. **Resultado de 2026-11-13** (run 43412347819): respondem do Actions **MG** (página da verba indenizatória 200; `dadosabertos.almg.gov.br/api/v2` 404 na raiz, testar uma rota), **MT** (`www.al.mt.gov.br` 200; `almt.eloweb.net/servidores` 404, a rota mudou ou exige parâmetro) e **RJ** (`alerjln1` 200). **RR** segue 403 no SAPL. Sem resposta (timeout) também do Actions: AP, DF, MA, ES, RS e SE (Alese Legis); GO alegodigital falha no TLS (curl 35); `sapl.al.ap.leg.br` e `sapl.cl.df.gov.br` não resolvem no DNS. Próximos possíveis: MG, MT e RJ pelo Actions; os outros dependem de outra rede ou de pedido à Casa.

### 4.7 Dados já coletados que o site ainda não mostra (levantado em 2026-11-02)

**Feito em 2026-11-13:** `assembleia.html?uf=XX` com contratos, atas, maiores fornecedores, regras da verba e as leis do PA (13 UFs: BA CE GO MS PA PE PR RJ RN RR SC SE SP), índice em `site/dados/assembleias.json`; ver `CHANGELOG.md`. Contrato só em PDF fica como link, sem valor. **Falta:** pautas e atas (`pautas_<ano>.json`, só em `dados/`), licitações de RR e PA, ler fornecedor e valor dos PDFs (SE, MS, RR, RJ) e MT (sem `orgao/MT.json`).

Conferido em 2026-11-09: `site/dados/orgao/` tem BA CE GO MS PA PE RJ RN RR SC SE SP (sem MT e PR), `site/dados/leis/` só PA, e
não existe `assembleia.html`. Os coletores estaduais e o `gerar_estaduais.py` já gravam estes dados, mas nenhuma página do
site os lê (nenhum arquivo em `site/assets/js` abre `dados/orgao/`; o `site/mapa-dados.html` marca cada um como "Ainda não aparece no site"). O que
aparece hoje, na ficha do deputado estadual (`politico.html?f=t/2022/<UF>&i=<sequencial>`, `estadual.js`), é verba,
remuneração, gabinete, presença, diárias, emendas e normas de autoria.

| Dado | Onde está | UFs | O que daria no site |
|---|---|---|---|
| Contratos e atas de registro de preço do órgão, com maiores fornecedores | `site/dados/orgao/<UF>.json` (`itens`, `fornecedores`, `regrasRessarcimento`, `fonte`) | gerados em 2026-11-02: BA CE GO MS PA PE RN SC SE SP; RR (47 KB) e RJ (3,5 KB, só links de PDF) gerados após a coleta de 2026-11-02; MT falhou (`451 Unavailable For Legal Reasons` em `almt.eloweb.net`, testar do Actions ou de outra rede) e PR não tem `orgao_*.json` local | página "Assembleia de <UF>" com contratos, atas e maiores fornecedores; as regras da verba como links |
| Fornecedor do órgão ligado ao núcleo | `nucleo/fornecedores`, só pelo CNPJ que a fonte publica | SP (795 fornecedores), RN (244), CE, PE, SC, GO, BA, PA | os mesmos contratos em `fornecedores.html` (empresa que também vende ao Legislativo ou doou em campanha) |
| Contratos só com título e link de PDF | `orgao/<UF>.json` (`fornecedores` vazio) | SE (367 itens), MS (87) | lista com link do PDF; fornecedor e valor estão dentro do PDF e não são lidos |
| Pautas e atas de sessão e de comissão | `dados/estaduais/<UF>/pautas_<ano>.json` | PR, PA, RN, SP, RJ, MS, MT | "na pauta desta semana" e link da ata na sessão; a ata já entra como fonte da votação quando houver |
| Licitações e contratações diretas | `dados/estaduais/RR/licitacoes_<ano>.json`, licitações do PA | RR, PA | lista junto dos contratos do órgão |
| Leis e normas sem autoria | `site/dados/leis/PA.json` | PA | página de normas da UF (sem autoria não cabe na ficha do deputado) |

Falta:
- Valor e fornecedor dos contratos só em PDF (SE, MS, RR, RJ): ler o PDF; hoje ficam como link.
- Pautas e atas na página da Assembleia (ou "na pauta desta semana" na proposição) e licitações de RR e PA.

## Pendências de cobertura do que já existe

- A primeira coleta de autores é limitada a 6.000 projetos por execução (`AUTORES_POR_EXECUCAO`),
  então proposições antigas ficam sem `principal` por alguns dias.
- Assembleias de AP, DF e MA ainda sem coletor (README e `LEVANTAMENTO_DADOS.md`, § AP, DF, MA). Em 2026-10-22 os
  sites não responderam desta rede (timeout/DNS), provável bloqueio da rede local. Tentar de outra rede ou do
  Actions e, se responderem, criar `scripts/coletar_estadual_<uf>.py` (ou, se usar SAPL, só o host em `ASSEMBLEIAS`):
  - AP: `http://www.al.ap.leg.br`, `https://sapl.al.ap.leg.br/` (cópia no Wayback de 06/12/2024).
  - DF: `https://www.cl.df.gov.br/web/portal-transparencia`; testar também
    `https://sapl.cl.df.gov.br/api/parlamentares/legislatura/?page_size=1`.
  - MA: `https://sistemas.al.ma.leg.br/transparencia/index.html`, `https://www.al.ma.leg.br/sitealema/`.
- ES tem coletor só de cota e diárias (portal do Estado); faltam proposições, salário e presença
  (`https://www.al.es.gov.br/Transparencia`, `/DadosAbertos/Remuneracao`; sem votações nominais).
- Cada novo coletor estadual segue a seção "Coletores de Assembleias estaduais" do `CLAUDE.md` (incremental, prazo,
  teste offline).
