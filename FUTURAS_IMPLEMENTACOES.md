# Futuras implementações

Ideias levantadas e ainda não feitas, em ordem de complexidade (coleta e exibição). Cada pacote junta o que faz
sentido implantar de uma vez: mesma fonte, mesmo coletor ou mesmo bloco do site. Dentro de cada nível, os pacotes
são independentes.

Ao implementar um endpoint novo, registre-o no `ENDPOINTS.md` e o conjunto no `CHANGELOG.md`.
Fontes externas verificadas em 2026-10-22.

Já feito a partir de `/proposicoes/{id}/autores`: autor principal/coautor, nomes e partido dos coautores,
total de autores e de partidos, iniciativa (Executivo, Senado, comissão) quando o principal não é deputado.
Já mostramos também a cota parlamentar (Câmara: `/deputados/{id}/despesas`; Senado: CEAPS), com totais por tipo,
por mês e os 10 maiores fornecedores, os bens declarados e a prestação de contas de campanha (TSE).

**Resumo**

| Nível | O que exige | Pacotes |
|---|---|---|
| 1 | Feito (ver abaixo) | 1.1 a 1.6 |
| 2 | Coleta leve (um arquivo por ano ou ~81 chamadas), exibida em blocos que já existem | 2.1 Recursos do senador · 2.4 Comportamento nas votações |
| 3 | Uma chamada por deputado ou por projeto, ou visualização nova | 3.1 Carreira e histórico partidário · 3.2 Vida do projeto · 3.3 Discursos e agenda · 3.4 Rede de coautoria |
| 4 | Raspagem de HTML ou chave de API | 4.1 Recursos do deputado (portal da Câmara) · 4.2 Emendas e Portal da Transparência |
| 5 | Fontes grandes, sem padrão ou cruzamentos sensíveis | 5.1 Fornecedores e doadores · 5.2 Assembleias e Câmaras Municipais · 5.3 Órgãos de controle |

## Nível 1: feito (2026-10-22)

Só com os dados que já tínhamos; registrado no `CHANGELOG.md`.

- **1.1 Autoria:** proporção principal/coautor, aprovados como autor principal e suprapartidários na aba Propostas; colunas e ordenações "iniciativas próprias" e "aprovados" na lista de deputados; apensados, anterior e posterior ligados à ficha de tramitação (o coletor passou a guardar `apensadoA`, `anterior` e `posterior`; projetos já finalizados no cache só ganham o campo se forem consultados de novo).
- **1.2 Cota:** maiores notas com link para o documento fiscal, percentual do limite acumulado no ano (tabela `LIMITE_COTA_UF` em `gerar.py`, copiada do guia da Câmara, sem data de vigência na página) e comparação com a média dos deputados do estado.
- **1.3 Salário:** linha "Subsídio mensal" na ficha (R$ 46.366,19 para deputados federais, senadores, presidente e vice; teto legal para deputados estaduais/distritais e vereadores).
- **1.4 Campanha e patrimônio:** custo do voto com a mediana do cargo e do partido, dependência do partido e evolução do patrimônio declarado (eleições ligadas por nome e data de nascimento).
- **1.5 Perfil das Casas:** bloco "Perfil dos eleitos" na página de políticos (Assembleia, bancada federal, senadores do estado e Câmara Municipal), com eleitos e eleitorado lado a lado. Usa os eleitos de 2018/2022/2024, não a composição de hoje (suplentes que assumiram não entram).
- **1.6 Presença no Senado:** comparecimento às votações nominais, com licença e missão separadas.

## Nível 2: coleta leve, exibição em blocos que já existem

### 2.1 Recursos e benefícios do senador

Três endpoints do mesmo serviço da CEAPS (`adm.senado.gov.br/adm-dadosabertos/api/v1`), no mesmo passo de
`coletar_ceaps_senado`; aparecem no bloco "Perfil e gastos" do senador.

| Endpoint | Custo | O que daria no site |
|---|---|---|
| `/senadores/{cod}/recursos-utilizados` | 1 chamada por senador (81) | gastos fora da cota (correios, material, diárias e passagens de viagem oficial), benefícios e número de pessoas no gabinete e nos escritórios de apoio |
| `/senadores/auxilio-moradia-imoveis-funcionais` | 1 chamada para todos | selo "usa imóvel funcional" / "recebe auxílio-moradia" |
| `/senadores/escritorios-apoio` | 1 chamada para todos | endereço e telefone do escritório no estado |
| `/senadores/aposentados`, `aposentados-ipc`, `aposentados-pssc` | 1 chamada cada | ex-senadores com aposentadoria parlamentar e o regime (útil para os perfis de ex-parlamentares) |

### 2.2 Cota da Câmara pelo CSV anual: feito (2026-10-22)

Coleta pelo CSV anual (com `cnpj` em cada despesa) e ranking de fornecedores em `fornecedores.html`; registrado no `CHANGELOG.md`. Falta o cruzamento com a empresa e os doadores (pacote 5.1).

### 2.3 Perfil temático do deputado: feito (2026-10-22)

Temas oficiais dos projetos, comissões e frentes parlamentares, no bloco "Em que áreas atua" do perfil e no filtro por tema da aba Propostas; registrado no `CHANGELOG.md`. Falta "projetos na área da comissão que ele integra": a Câmara não publica o tema de cada comissão.

### 2.4 Comportamento nas votações

Liga as votações já guardadas em `dados/votacoes/` ao partido, ao governo e à presença.

| Ideia | Fonte | O que daria no site |
|---|---|---|
| Orientação de bancada | `votacoesOrientacoes/json/votacoesOrientacoes-{ano}.json` (~2 MB; ou `/votacoes/{id}/orientacoes`) | quanto o deputado segue o partido e o governo ("fidelidade partidária" e "governismo") |
| Presença em eventos | `eventosPresencaDeputados/json/eventosPresencaDeputados-{ano}.json` (~30 MB) | presença em sessões e reuniões de comissão |
| Votações do projeto | `/proposicoes/{id}/votacoes` (1 por projeto) | na página do projeto, link para as votações e como votou a bancada |

## Nível 3: uma chamada por deputado ou projeto, ou visualização nova

### 3.1 Carreira e histórico partidário

Um passo no coletor de deputados, com chamadas por deputado (513 × 4).

- `/deputados/{id}/ocupacoes`, `/profissoes` e `/mandatosExternos`: carreira antes da Câmara (vereador, prefeito,
  deputado estadual), no perfil.
- `/deputados/{id}/historico`: trocas de partido. Resolve também o partido do coautor na data da assinatura; hoje
  usamos o partido atual e só de deputados em exercício, então ex-deputados e trocas de partido ficam sem sigla.

### 3.2 Vida do projeto

Página do projeto com linha do tempo; uma chamada por projeto, coletada de forma incremental como os autores.

- `/proposicoes/{id}/tramitacoes` (hoje usado só para o Executivo): linha do tempo, relator e comissões por onde passou.
- `/proposicoes/{id}/relacionadas`: projetos apensados, substitutos e do mesmo assunto (complementa o 1.1).

### 3.3 Discursos e agenda

- `/deputados/{id}/discursos`: número de discursos, temas e link para o texto.
- `/deputados/{id}/eventos`: audiências e reuniões de que participou.
- Uma chamada por deputado e por período; o volume cresce rápido, então guardar só contagens e os mais recentes.

### 3.4 Rede de coautoria

- Com quem cada deputado mais coassina e índice de colaboração entre partidos. Os dados já existem
  (`proposicoes_autores.json`); o difícil é a exibição (grafo ou matriz entre partidos).

## Nível 4: raspagem ou chave de API

### 4.1 Recursos do deputado no portal da Câmara

Não estão na API v2, só nas páginas do portal (HTML). Uma raspagem por deputado cobre tudo, e o bloco do site é o
mesmo do pacote 2.1 do Senado.

| Ideia | Página | O que daria no site |
|---|---|---|
| Benefícios | `www.camara.leg.br/deputados/{id}` (bloco "Recursos") | auxílio-moradia, imóvel funcional, viagens em missão oficial, passaporte diplomático |
| Verba de gabinete | `www.camara.leg.br/deputados/{id}/verba-gabinete?ano={ano}` | quanto do limite mensal para pagar assessores foi usado (o limite passa de R$ 100 mil/mês) |
| Pessoal de gabinete | `www.camara.leg.br/deputados/{id}/pessoal-gabinete` | quantos assessores e em que cargos; nomes são públicos, mas vale mostrar só a contagem |
| Presença em plenário | `www.camara.leg.br/deputados/{id}/presenca-plenario/{ano}` | presenças, ausências justificadas e não justificadas (complementa o 2.4) |

Raspagem é frágil: tratar como fonte opcional (avisar e seguir, como o TSE) e cobrir com um teste de contrato em
`scripts/contrato_apis.py`.

### 4.2 Emendas e Portal da Transparência

Uma chave gratuita (cadastro com conta gov.br), enviada no cabeçalho `chave-api-dados` e guardada como secret do
Actions, libera tudo abaixo.

- `api.portaldatransparencia.gov.br/api-de-dados/emendas`: emendas individuais e de bancada por autor, com valor
  empenhado e pago e o município que recebeu. No site: quanto cada deputado e senador mandou, para quais municípios
  e áreas, e o mapa dos destinos (o mapa por município já existe para votos).
- "Emendas Pix" (transferências especiais), no mesmo portal e no Transferegov: as de menor rastreio, vale um destaque.
- Viagens a serviço e cargos de ministros e do Executivo federal.

## Nível 5: fontes grandes, sem padrão ou cruzamentos sensíveis

### 5.1 Fornecedores e doadores

Depende do CNPJ do pacote 2.2.

- Dados da empresa (atividade, data de abertura, sócios) pelo CNPJ aberto da Receita Federal
  (`dadosabertos.rfb.gov.br`, arquivos de vários GB; rodar só localmente, como a prestação de contas).
- Cruzamento com os doadores de campanha (`dados/tse/contas/`, pelo nome, já que não guardamos CPF de doador):
  "empresa que doou e depois foi paga pela cota". Mostrar só correspondências exatas e com as duas fontes.

### 5.2 Assembleias e Câmaras Municipais

Sem padrão nacional; cada Casa publica do seu jeito.

- Salário exato de deputados estaduais e vereadores: portal de transparência de cada Casa.
- **SICONFI / Tesouro Nacional**: despesa total de cada Câmara Municipal e Assembleia; dividida pelo número de
  cadeiras dá o "custo por parlamentar" de cada Casa, sem raspar portais locais.
- **Querido Diário** (Open Knowledge Brasil, `queridodiario.ok.org.br/api`): diários oficiais municipais com busca
  por texto; poderia trazer nomeações, leis sancionadas e o subsídio de vereadores em cidades sem SAPL.
- Mesmo nível de detalhe de autoria (principal, coautores, partido, total) para as assembleias estaduais; hoje só
  Câmara e Senado separam principal e coautor.

### 5.3 Órgãos de controle

- **TCU, contas julgadas irregulares** (dados abertos do TCU): lista oficial de responsáveis por contas irregulares,
  usada pela Justiça Eleitoral na Ficha Limpa. O cruzamento é por nome e exige cuidado com homônimos; só mostrar
  com correspondência exata e link para o processo.

## Pendências de cobertura do que já existe

- A primeira coleta de autores é limitada a 6.000 projetos por execução (`AUTORES_POR_EXECUCAO`),
  então proposições antigas ficam sem `principal` por alguns dias.
- Senadores: avaliar o mesmo nível de detalhe de autoria dos deputados (partido dos coautores, total).
