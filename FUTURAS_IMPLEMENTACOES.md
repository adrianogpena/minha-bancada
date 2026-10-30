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
| 4 | Fontes grandes, sem padrão ou cruzamentos sensíveis | 4.1 Fornecedores e doadores · 4.2 Assembleias e Câmaras Municipais · 4.3 Ministros dos tribunais superiores · 4.4 Órgãos de controle (resto) |

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

Depois dos ministros de Estado (3.3), o objetivo é ter no site todos os ministros: STF, STJ, TST, TSE, STM e TCU.
Equivalente às abas de votações e propostas: votos em julgamentos, decisões monocráticas e pedidos de vista.
Fontes de cada tribunal ainda não levantadas.

### 4.4 Órgãos de controle

- **TCU, inabilitados:** feito em 2026-10-29 (`coletar_tcu.py`, `identidades.ligar_inabilitados`, aviso na ficha; ver `CHANGELOG.md`).
  Os `inidoneos` (proibidos de licitar, só CNPJ) também foram feitos em 2026-10-29: aviso nos fornecedores por CNPJ.
  Hoje o cruzamento de inabilitados dá zero ligações (5 nomes iguais, todos homônimos de outra UF), porque o TSE não
  publica CPF; o aviso aparece sozinho quando surgir um caso com nome e UF iguais.

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
