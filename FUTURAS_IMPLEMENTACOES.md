# Futuras implementações

Ideias levantadas e ainda não feitas, em ordem de complexidade. O que já foi implantado está no `CHANGELOG.md`
(autoria, cota, salário, campanha e patrimônio, perfil das Casas, presença e votações, recursos do senador,
perfil temático, carreira, vida do projeto, rede de coautoria, fornecedores com dados da Receita e cruzamento com
doadores, despesa com pessoal pelo SICONFI, ministros de Estado em sua primeira etapa, coletores de 17 Assembleias).

Ao implementar um endpoint novo, registre-o no `ENDPOINTS.md` e o conjunto no `CHANGELOG.md`.
Revisado em 2026-10-29 contra o código e o `CHANGELOG.md`.

**Resumo**

| Nível | O que exige | Pacotes |
|---|---|---|
| 1 | Acabamentos do que já existe | 1.1 Restos de pacotes feitos |
| 2 | Uma chamada por deputado, volume grande | 2.1 Discursos e agenda |
| 3 | Raspagem de HTML ou chave de API | 3.1 Recursos do deputado (portal da Câmara) · 3.2 Emendas e Portal da Transparência · 3.3 Ministros de Estado: o que fica para depois |
| 4 | Fontes grandes, sem padrão ou cruzamentos sensíveis | 4.1 Fornecedores e doadores · 4.2 Assembleias e Câmaras Municipais · 4.3 Ministros dos tribunais superiores · 4.4 Órgãos de controle |

## Nível 1: acabamentos

### 1.1 Restos de pacotes feitos

- **Aposentadoria parlamentar (Senado):** `/senadores/aposentados`, `aposentados-ipc` e `aposentados-pssc`
  (`adm.senado.gov.br/adm-dadosabertos/api/v1`, 1 chamada cada). Só faz sentido com perfil de ex-senador.
- **Comissão x tema:** "projetos na área da comissão que ele integra"; a Câmara não publica o tema de cada comissão.
- **Fidelidade em blocos:** os blocos usam a composição atual e rótulos que não constam em `/blocos` seguem sem
  fidelidade; a presença em reuniões de comissão não tem total para comparar.
- **Perfil dos eleitos:** usa os eleitos de 2018/2022/2024, não a composição de hoje (suplentes que assumiram não entram).

## Nível 2: uma chamada por deputado, volume grande

### 2.1 Discursos e agenda

Hoje a ficha mostra só os 5 discursos mais recentes (`/deputados/{id}/discursos`, sem contagem nem tema).
- Contagem de discursos por ano e por tipo, e temas (palavras-chave), para comparar deputados.
- `/deputados/{id}/eventos`: audiências e reuniões de que participou. A presença em sessões e reuniões já vem de
  outro endpoint; aqui seria a lista (título, data, órgão).
- O volume cresce rápido: guardar só contagens e os mais recentes, com a releitura escalonada de `coletar_complementos`.

## Nível 3: raspagem ou chave de API

### 3.1 Recursos do deputado no portal da Câmara

Não estão na API v2, só nas páginas do portal (HTML). Uma raspagem por deputado cobre tudo, no mesmo bloco do site
dos recursos do senador.

| Ideia | Página | O que daria no site |
|---|---|---|
| Benefícios | `www.camara.leg.br/deputados/{id}` (bloco "Recursos") | auxílio-moradia, imóvel funcional, viagens em missão oficial, passaporte diplomático |
| Verba de gabinete | `www.camara.leg.br/deputados/{id}/verba-gabinete?ano={ano}` | quanto do limite mensal para pagar assessores foi usado (o limite passa de R$ 100 mil/mês) |
| Pessoal de gabinete | `www.camara.leg.br/deputados/{id}/pessoal-gabinete` | quantos assessores e em que cargos; nomes são públicos, mas vale mostrar só a contagem |
| Presença em plenário | `www.camara.leg.br/deputados/{id}/presenca-plenario/{ano}` | ausências justificadas e não justificadas (a presença em sessões já existe pela API; só vale se a página trouxer a justificativa) |

Raspagem é frágil: tratar como fonte opcional (avisar e seguir, como o TSE) e cobrir com um teste de contrato em
`scripts/contrato_apis.py`.

### 3.2 Emendas e Portal da Transparência

Uma chave gratuita (cadastro com conta gov.br), enviada no cabeçalho `chave-api-dados` e guardada como secret do
Actions, libera tudo abaixo. Hoje só há emendas das Assembleias da BA, CE e MS; as federais não existem.

- `api.portaldatransparencia.gov.br/api-de-dados/emendas`: emendas individuais e de bancada por autor, com valor
  empenhado e pago e o município que recebeu. No site: quanto cada deputado e senador mandou, para quais municípios
  e áreas, e o mapa dos destinos (o mapa por município já existe para votos).
- "Emendas Pix" (transferências especiais), no mesmo portal e no Transferegov: as de menor rastreio, vale um destaque.
- Viagens a serviço e cargos do Executivo federal (ver 3.3).

### 3.3 Ministros de Estado: o que fica para depois

Já existem o coletor da lista do Planalto, requerimentos de informação, convocações e licenças, a ligação às
pessoas, as páginas `ministerios.html` e `ministro.html` e os eventos no histórico. Limites atuais: o Planalto não
publica a data da posse (o início vem da licença do parlamentar ou do dia em que a coleta viu o nome) e a resposta a
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
| Ministros anteriores (antes da primeira coleta) | DOU | depende da busca do DOU | histórico de cada pasta em `ministerios.html` |
| Resposta a requerimento do Senado | API do Senado | não coletada | fechar o ciclo pedido-resposta também para RQS |

Descartado: Wikidata (consulta SPARQL de 2026-10-29 trouxe 6 ministros sem data de saída, parte já fora do cargo).

## Nível 4: fontes grandes, sem padrão ou cruzamentos sensíveis

### 4.1 Fornecedores e doadores

Dados da empresa pela Receita e cruzamento com doadores de campanha já existem. Falta:
- Rodar `coletar_contas.py` (versão 4) localmente, com os ZIPs de `baixar_tse.py prestacao_contas`, e commitar, para
  o cruzamento por CNPJ (hoje só por nome nas contas versionadas).
- Fora do escopo por ser sensível: cruzar sócio com político ou parente.

### 4.2 Assembleias e Câmaras Municipais

Sem padrão nacional; cada Casa publica do seu jeito.

- Salário exato de deputados estaduais e vereadores: portal de transparência de cada Casa.
- **SICONFI / Tesouro Nacional:** já temos a despesa com pessoal do Legislativo de cada UF (RGF). Falta a despesa
  total (RREO/DCA) de cada Assembleia e Câmara Municipal; dividida pelo número de cadeiras dá o "custo por
  parlamentar", sem raspar portais locais.
- **Querido Diário** (Open Knowledge Brasil, `queridodiario.ok.org.br/api`): diários oficiais municipais com busca
  por texto; poderia trazer nomeações, leis sancionadas e o subsídio de vereadores em cidades sem SAPL. Ainda não
  está no `ENDPOINTS.md`.
- Mesmo nível de detalhe de autoria (principal, coautores, partido, total) para todas as Assembleias: hoje só
  alguns coletores guardam os coautores (`gerar_estaduais.py`); o Senado também ainda não tem partido dos coautores e total.

### 4.3 Ministros dos tribunais superiores

Depois dos ministros de Estado (3.3), o objetivo é ter no site todos os ministros: STF, STJ, TST, TSE, STM e TCU.
Equivalente às abas de votações e propostas: votos em julgamentos, decisões monocráticas e pedidos de vista.
Fontes de cada tribunal ainda não levantadas.

### 4.4 Órgãos de controle

- **TCU, contas julgadas irregulares** (dados abertos do TCU): lista oficial de responsáveis por contas irregulares,
  usada pela Justiça Eleitoral na Ficha Limpa. O cruzamento é por nome e exige cuidado com homônimos; só mostrar
  com correspondência exata e link para o processo.

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
