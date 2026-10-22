# Futuras implementações

Ideias levantadas e ainda não feitas. Cada item diz de onde vêm os dados e o custo de coleta.
Ao implementar um endpoint novo, registre-o no `ENDPOINTS.md` e o conjunto no `CHANGELOG.md`.

Já feito a partir de `/proposicoes/{id}/autores`: autor principal/coautor, nomes e partido dos coautores,
total de autores e de partidos, iniciativa (Executivo, Senado, comissão) quando o principal não é deputado.

## Novos endpoints da Câmara (API v2, `https://dadosabertos.camara.leg.br/api/v2`)

| Ideia | Endpoint | Custo | O que daria no site |
|---|---|---|---|
| Temas oficiais | `/proposicoes/{id}/temas` | 1 chamada por projeto (como os autores) | filtrar e agregar propostas por tema (saúde, segurança, economia...) |
| Proposições relacionadas | `/proposicoes/{id}/relacionadas` | 1 por projeto | ligar projetos apensados, substitutos e do mesmo assunto |
| Votações do projeto | `/proposicoes/{id}/votacoes` | 1 por projeto | ligar o projeto às votações já guardadas em `dados/votacoes/` |
| Tramitação completa | `/proposicoes/{id}/tramitacoes` | 1 por projeto; já usada só para o Executivo | linha do tempo, relator e comissões por onde passou |
| Comissões do deputado | `/deputados/{id}/orgaos` | 1 por deputado | "projetos na área da comissão que ele integra" |
| Frentes parlamentares | `/deputados/{id}/frentes` | 1 por deputado | perfil temático do deputado |

## Campos que já coletamos e o site ainda não usa

- `/proposicoes/{id}`: `uriPropPrincipal`, `uriPropAnterior`, `uriPropPosterior` (apensados e substitutos).
- Partido do coautor na data da assinatura: hoje usamos o partido atual e só de deputados em exercício;
  ex-deputados e trocas de partido ficam sem sigla. Exigiria histórico (`/deputados/{id}/historico`).

## Indicadores derivados (só cruzamento dos dados que já temos)

- Proporção de projetos como autor principal versus coautor, por deputado.
- Rede de coautoria: com quem cada deputado mais coassina e índice de colaboração entre partidos.
- Aprovados ou sancionados em que foi autor principal (situação em `proposicoes_detalhe.json`).
- Projetos suprapartidários (`partidosDistintos` alto) versus de bancada única.
- Ranking de deputados por iniciativas próprias (principal) em vez de coautorias.

## Cobertura

- A primeira coleta de autores é limitada a 6.000 projetos por execução (`AUTORES_POR_EXECUCAO`),
  então proposições antigas ficam sem `principal` por alguns dias.
- Senado e assembleias estaduais: só o Senado já separa principal e coautor; avaliar o mesmo nível de detalhe
  (partido dos coautores, total) para senadores.

## Salário, benefícios e gastos de cada político

Pergunta frequente: dá para mostrar quanto cada político ganha e gasta? Para deputados federais e senadores, sim,
quase tudo; nos estados e municípios, muito menos (ver o fim desta seção). Fontes verificadas em 2026-10-22.

**O que já mostramos:** a cota parlamentar (Câmara: `/deputados/{id}/despesas`; Senado: CEAPS), com totais por tipo,
por mês e os 10 maiores fornecedores, e os bens declarados ao TSE.

### Salário (subsídio)

- O valor é igual para todos e definido em lei: hoje R$ 46.366,19 brutos por mês para deputados federais e senadores
  (o mesmo teto do STF; reajustes por decreto legislativo). Dá para mostrar como uma constante com a data do decreto,
  sem coleta. Ministros, presidente e vice também têm valor fixo por decreto.
- Valor líquido e descontos individuais: a página do deputado no portal da Câmara (`www.camara.leg.br/deputados/{id}`)
  mostra "Salário mensal bruto"; o Senado publica a remuneração dos servidores em
  `adm.senado.gov.br/adm-dadosabertos/api/v1/servidores/remuneracoes/{ano}/{mes}` (avaliar se inclui os senadores).
- Deputados estaduais e vereadores: o subsídio é um percentual do federal (até 75% para estaduais; para vereadores
  depende do tamanho do município, de 20% a 75% do estadual). O valor exato de cada Casa só está no portal de
  transparência dela, sem padrão; dá para mostrar o teto legal calculado e um link.

### Benefícios e estrutura do mandato

| Ideia | Fonte | Custo | O que daria no site |
|---|---|---|---|
| Resumo anual de recursos do senador | `adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/{cod}/recursos-utilizados` (JSON) | 1 chamada por senador (81) | cota por categoria, gastos fora da cota (correios, material, diárias de viagem oficial), auxílio-moradia ou imóvel funcional e número de pessoas no gabinete e nos escritórios de apoio |
| Auxílio-moradia e imóvel funcional (Senado) | `.../senadores/auxilio-moradia-imoveis-funcionais` | 1 chamada para todos | selo "usa imóvel funcional" / "recebe auxílio-moradia" |
| Escritórios de apoio (Senado) | `.../senadores/escritorios-apoio` | 1 chamada para todos | endereço e telefone do escritório no estado |
| Verba de gabinete (Câmara) | portal `www.camara.leg.br/deputados/{id}/verba-gabinete?ano={ano}` (HTML; não está na API v2) | 1 página por deputado, raspagem | quanto do limite mensal para pagar assessores foi usado (o limite passa de R$ 100 mil/mês) |
| Pessoal de gabinete (Câmara) | portal `www.camara.leg.br/deputados/{id}/pessoal-gabinete` (HTML) | 1 página por deputado, raspagem | quantos assessores, cargos e período; nomes são públicos, mas vale mostrar só a contagem |
| Auxílio-moradia, imóvel funcional, viagens em missão e passaporte diplomático (Câmara) | mesma página `www.camara.leg.br/deputados/{id}` (bloco "Recursos") | já é a página que linkamos; raspagem | selos de benefício iguais aos do Senado |
| Aposentadoria de ex-parlamentares | `.../senadores/aposentados`, `aposentados-ipc`, `aposentados-pssc` | 1 chamada cada | quem recebe aposentadoria parlamentar e por qual regime |

Raspagem do portal da Câmara é frágil: tratar como fonte opcional (avisar e seguir, como o TSE) e cobrir com
um teste de contrato em `scripts/contrato_apis.py`.

### Cota parlamentar: campos que já existem e não usamos

- `urlDocumento` já é coletado em `despesas.itens[].documento`, mas `gerar.py` só publica totais: dá para listar
  as maiores notas com link para o documento fiscal.
- `cnpjCpfFornecedor` (API da Câmara e CSV anual `www.camara.leg.br/cotas/Ano-{ano}.csv.zip`, ~7 MB, todos os deputados
  de uma vez): identifica o fornecedor sem depender do nome. Com ele:
  - ranking dos fornecedores que mais recebem da Câmara inteira e quantos deputados usam cada um;
  - cruzamento com os doadores de campanha (`dados/tse/contas/`, pelo nome, já que não guardamos CPF de doador):
    "empresa que doou e depois foi paga pela cota";
  - dados da empresa (atividade, data de abertura, sócios) pelo CNPJ aberto da Receita Federal
    (`dadosabertos.rfb.gov.br`, arquivos grandes; rodar só localmente, como a prestação de contas).
- O CSV anual também resolveria a coleta de despesas em uma chamada só, em vez de uma por deputado.
- Comparativos: gasto do deputado contra a média da bancada do estado (o limite da cota varia por UF) e
  percentual do limite usado no ano.

### Emendas parlamentares

- Portal da Transparência (`api.portaldatransparencia.gov.br/api-de-dados/emendas`): emendas individuais e de
  bancada por autor, com valor empenhado e pago e o município que recebeu. Exige uma chave gratuita (cadastro
  com conta gov.br) enviada no cabeçalho `chave-api-dados`; guardar como secret do Actions.
- No site: quanto cada deputado e senador mandou, para quais municípios e áreas, e o mapa dos destinos
  (o mapa por município já existe para votos).
- "Emendas Pix" (transferências especiais) estão no mesmo portal e no Transferegov; são as de menor rastreio,
  vale um destaque.

## Atuação parlamentar além dos projetos

| Ideia | Fonte | Custo | O que daria no site |
|---|---|---|---|
| Presença em plenário (Câmara) | portal `www.camara.leg.br/deputados/{id}/presenca-plenario/{ano}` (HTML); na API, `/arquivos/eventosPresencaDeputados/json/eventosPresencaDeputados-{ano}.json` (~30 MB, todos) | 1 arquivo por ano | presenças, ausências justificadas e não justificadas |
| Presença no Senado | votações já coletadas em `dados/senado_votacoes/` (os votos "não compareceu", "licença" etc. já são classificados) | só cruzamento | taxa de comparecimento às votações nominais |
| Orientação de bancada | `/arquivos/votacoesOrientacoes/json/votacoesOrientacoes-{ano}.json` (~2 MB) ou `/votacoes/{id}/orientacoes` | 1 arquivo por ano | quanto o deputado segue o partido e o governo ("fidelidade partidária" e "governismo") |
| Discursos | `/deputados/{id}/discursos` | 1 por deputado | número de discursos, temas e link para o texto |
| Agenda e eventos | `/deputados/{id}/eventos` | 1 por deputado | audiências e reuniões de que participou |
| Comissões e frentes em lote | `/arquivos/orgaosDeputados/json/orgaosDeputados-L57.json` (~8 MB) e `/arquivos/frentesDeputados/json/frentesDeputados.json` (~150 MB) | 1 arquivo cada | o mesmo das linhas "Comissões" e "Frentes" acima, sem 513 chamadas |
| Temas em lote | `/arquivos/proposicoesTemas/json/proposicoesTemas-{ano}.json` (~10 MB) | 1 arquivo por ano | o mesmo da linha "Temas oficiais", sem uma chamada por projeto |
| Profissões e mandatos anteriores | `/deputados/{id}/ocupacoes`, `/profissoes`, `/mandatosExternos` | 1 por deputado | carreira antes da Câmara (vereador, prefeito, deputado estadual) |

## Dados do TSE que já temos e o site pode explorar mais

- Evolução patrimonial: os bens declarados existem para cada eleição coletada, e `gerar_politicos.py` já liga as
  eleições do mesmo político por nome e UF (`chave_nome`); falta mostrar a variação do total entre uma eleição e
  outra (o TSE não publica mais o CPF, então a ligação continua sendo por nome).
- Perfil agregado de cada Casa: gênero, cor ou raça, instrução, idade e ocupação já são coletados por eleito
  (`coletar_tse.py`), mas só aparecem no perfil individual. Dá para mostrar "quem é a Câmara Municipal de X"
  comparado ao eleitorado (`perfil_eleitorado` já é coletado).
- Custo do voto: receitas de campanha dividido pelos votos recebidos, por cargo e partido.
- Dependência do fundo partidário/eleitoral: participação de "Recursos de partido político" em `origensReceita`.

## Outras fontes confiáveis a avaliar

- **TCU, contas julgadas irregulares** (dados abertos do TCU): lista oficial de responsáveis por contas irregulares,
  usada pela Justiça Eleitoral na Ficha Limpa. O cruzamento é por nome e exige cuidado com homônimos; só mostrar
  com correspondência exata e link para o processo.
- **Querido Diário** (Open Knowledge Brasil, `queridodiario.ok.org.br/api`): diários oficiais municipais com busca
  por texto; poderia trazer nomeações, leis sancionadas e salário de vereadores em cidades sem SAPL.
- **SICONFI / Tesouro Nacional**: despesa total de cada Câmara Municipal e Assembleia; dividida pelo número de
  cadeiras dá o "custo por parlamentar" de cada Casa, sem raspar portais locais.
- **Portal da Transparência (servidores e viagens)**: viagens a serviço e cargos de ministros e do Executivo federal,
  com a mesma chave das emendas.
