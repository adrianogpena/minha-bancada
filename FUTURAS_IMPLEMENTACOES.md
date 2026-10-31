# Futuras implementações

Ideias levantadas e ainda não feitas, em ordem de complexidade. O que já foi implantado está no `CHANGELOG.md`
(autoria, cota, salário, campanha e patrimônio, perfil das Casas, presença e votações, recursos do senador,
perfil temático, discursos e eventos, aposentadoria de ex-senadores, carreira, vida do projeto, rede de coautoria, fornecedores com dados da Receita e cruzamento com
doadores, recursos, pessoal, verba e presença em plenário do deputado pelo portal, despesa com pessoal e das Casas pelo SICONFI, ministros de Estado em sua primeira etapa, coletores de 17 Assembleias).

Ao implementar um endpoint novo, registre-o no `ENDPOINTS.md` e o conjunto no `CHANGELOG.md`.
Revisado em 2026-10-29 contra o código e o `CHANGELOG.md`.

**Resumo**

| Nível | O que exige | Pacotes |
|---|---|---|
| 1 | Acabamentos do que já existe | 1.1 Restos de pacotes feitos |
| 3 | Raspagem de HTML ou chave de API | 3.2 Emendas e Portal da Transparência · 3.3 Ministros de Estado: o que fica para depois · 3.4 Ministérios em números · 3.5 Atuação de cada ministro |
| 4 | Fontes grandes, sem padrão ou cruzamentos sensíveis | 4.1 Fornecedores e doadores · 4.2 Assembleias e Câmaras Municipais · 4.3 Ministros dos tribunais superiores · 4.4 Órgãos de controle (resto) · 4.5 Assembleia do Paraná: portal e webservices (2026) |

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

**Emendas feitas em 2026-10-30, sem ter rodado contra a API real** (chave só no secret `PORTAL_TRANSPARENCIA_CHAVE` do Actions): coletor
`coletar_emendas.py`, ligação do autor por nome, `site/dados/emendas/<pessoa>.json` e painel na ficha (ver `CHANGELOG.md`).
Falta conferir na primeira execução do Actions: nomes dos campos e formato do autor (`autor` x `nomeAutor`), tempo da coleta e se o tipo das Pix vem como "Transferências Especiais", quantos municípios casam com o IBGE e quantos autores
ligam (`site/dados/nucleo/ligacoes.json`, `emendas`); depois regravar `tests/test_coletar_emendas.py` com amostra real.

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
- Ligar cada ministro à pessoa do núcleo em `identidades.py` (ex-parlamentares no TCU e no STF, como Vital do Rêgo e Flávio Dino).
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
| 2. Normas legais | `POST /norma-legal/filtrar`, `GET /norma-legal/{código}` (webservices; leis, decretos legislativos, resoluções: tipo, número, ano, ementa, autores, Diário Oficial, movimentações, proposições ligadas) | "leis de sua autoria" e a lei que nasceu de cada projeto; fecha o ciclo da proposição | Autor vem como texto; ligar por `ligar_nomes`. `dataInicial` evita reler o ano. Registrar o host `http://` (sem HTTPS). |
| 3. Proposições pelo webservice, incremental | `POST /proposicao/filtrar` com `dataInicial`; `GET /proposicao/campos` (tipos, assuntos, situações) | menos tempo de coleta; tabela de situações oficial | `GET /proposicao/{código}` está quebrado no servidor (erro Oracle `ORA-00942`, com HTTP 200 e `sucesso:false`), então os trâmites não vêm; o testador acusa "OK" por isso. Revisar a cada trimestre. |
| 4. Pautas e atas | `/plenario/pautas/{ordem-do-dia,ccj,comissoes-tematicas}/ajax`, `/plenario/atas-sessoes-plenarias/ajax` | "na pauta desta semana" na proposição; link da ata na sessão | Arquivos em PDF; ligar item da pauta à proposição pelo número e ano. Sem partes estruturadas. |
| 5. Gabinete do deputado | `/api/remuneracao/recente` (matrícula, nome, símbolo do cargo, lotação, ex.: "GAB. DEP. FULANO"); páginas `/pessoal/comissionados`, `estaveis`, etc. | tamanho e composição do gabinete (como na Câmara: contagem por grupo) | Ligar a lotação ao deputado em `ESTRATEGIAS`, nunca por função própria. Decidir antes se mostra nomes de servidores ou só contagem por símbolo (o "Mapa dos dados" não leva nomes de pessoas). Sem valores: o salário já vem de `/api/remuneracao/{matrícula}`. |
| 6. Presença e diárias mais enxutas | `/api/presenca/{meses,datas}`, `/api/diarias/ultimo-periodo` | menos requisições; saber o último mês publicado sem testar um a um | `presenca/mensal` devolve 404 sempre; só reavaliar. |
| 7. Monitorar o que vem vazio | `/api/ressarcimento` (POST; `meses` lista só janeiro de 2026 e o POST volta `data: []`), `/api/passagens`, `/api/cartoes`, `/api/estoque` | verba de ressarcimento, passagens e cartões, se publicarem por deputado | 200 sem registros em 2026. Conferir o corpo do POST de ressarcimento em `ressarcimento.min.js` e rever todo mês; hoje as passagens e cartões não trazem o deputado. |
| 8. Despesas do órgão (não são de deputado) | contratos, licitações, dispensas, atas de registro de preço e de adesão, obras, ordem cronológica, SIAFIC, receitas, atos normativos (`/api/atos-normativos?tipo=4`, atos do presidente, e o de ressarcimento da atividade parlamentar) | maiores fornecedores da Assembleia, ligados a `nucleo/fornecedores` por CNPJ; regras da verba | Prioridade baixa. Só os endpoints de `meses` foram abertos, o conteúdo não foi medido. O ato de ressarcimento da atividade parlamentar vale ler primeiro: explica o que a verba cobre. |
| Fora | `/api/rreo`, `/api/gestao_fiscal` | | Exigem reCAPTCHA. A despesa com pessoal e o RGF já vêm do SICONFI (4.2). |

**Antes de cada pacote** (regras do projeto): endpoint já está no `ENDPOINTS.md`; amostra real em `tests/fixtures/contratos/`
(`CONTRATOS` do coletor) e teste offline em `tests/test_coletar_estadual_pr.py`; ligação em `identidades.py`; entrada no
`CHANGELOG.md` e no `site/mapa-dados.html`; fonte com link ao lado de cada dado (votos: URL do PDF e do ZIP da sessão; normas:
página da norma). Medir uma coleta do zero e uma com cache e anotar no `CHANGELOG.md`; o job do PR já tem prazo próprio.

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
