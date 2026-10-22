# Dados por estado

Inventário do que o projeto já coleta, estado por estado, separado por tipo de dado. Os valores não entram aqui, só qual dado temos, de onde vem e se o site o mostra. O que falta coletar de cada Assembleia está em `LEVANTAMENTO_DADOS.md`; ideias de funcionalidade, em `FUTURAS_IMPLEMENTACOES.md`.

Regra do projeto: todo dado sobre um político tem a fonte ao lado, com link para conferir.

## Legenda de status

- `mostrado no site`: o dado chega a `site/dados/` e `site/assets/app.js` o exibe.
- `coletado, não usado no site`: está em `dados/` (ou passa para `site/dados/`), mas nenhuma tela o exibe.
- `disponível na fonte, não coletado`: a fonte oferece, o coletor não guarda.

Como o status foi apurado: leitura dos coletores e geradores em `scripts/` e busca de cada campo em `site/assets/app.js`. Um campo só é marcado como não usado quando `app.js` não o referencia em nenhum ponto. A partir de agora, dado novo entra neste arquivo no mesmo commit do coletor.

## Dados comuns a todos os estados

Valem para os 27 estados. Nos tópicos por estado aparece "igual ao comum" e só as diferenças são listadas. Os arquivos por UF seguem a mesma estrutura em todos os estados.

### Eleições (TSE)

Por candidato eleito (e quem foi ao 2º turno em 2026). Anos: 2018 (só senadores), 2022 (federais e estaduais, governador, senador, presidente), 2024 (prefeito, vice e vereador) e 2026 (mesmos cargos de 2022, com a eleição já apurada). Candidatos não eleitos não entram.

| Tipo | Dado | Campo | Fonte | Status |
|---|---|---|---|---|
| Eleição | identificação | `nome`, `urna`, `nomeSocial`, `numero`, `sequencial` | TSE, Candidatos e Bens de candidatos (`coletar_tse.py`, `dados/tse/<ano>/<UF>.json`) | mostrado no site |
| Eleição | cargo e resultado | `cargo`, `situacao` (eleito ou 2turno), `resultado`, `eleicao` | TSE, Candidatos e Bens de candidatos (`coletar_tse.py`, `dados/tse/<ano>/<UF>.json`) | mostrado no site |
| Eleição | local | `uf`, `unidadeEleitoral`, `municipio` | TSE, Candidatos e Bens de candidatos (`coletar_tse.py`, `dados/tse/<ano>/<UF>.json`) | mostrado no site |
| Eleição | partido e legenda | `partido`, `federacao`, `coligacao`, `composicaoColigacao` | TSE, Candidatos e Bens de candidatos (`coletar_tse.py`, `dados/tse/<ano>/<UF>.json`) | mostrado no site |
| Eleição | votos | `votos` (`turno`, `data`, `votos`, `percentual`) | TSE, Candidatos e Bens de candidatos (`coletar_tse.py`, `dados/tse/<ano>/<UF>.json`) | mostrado no site |
| Eleição | dados pessoais declarados | `nascimento`, `genero`, `ufNascimento`, `estadoCivil`, `corRaca`, `instrucao`, `ocupacao`, `email` | TSE, Candidatos e Bens de candidatos (`coletar_tse.py`, `dados/tse/<ano>/<UF>.json`) | mostrado no site |
| Eleição | bens declarados | `bens` (tipo, descrição, valor) e `totalBens`; evolução do patrimônio entre eleições (calculada em `gerar_politicos.py`) | TSE, Candidatos e Bens de candidatos (`coletar_tse.py`, `dados/tse/<ano>/<UF>.json`) | mostrado no site |
| Eleição | redes e foto | `redes`, `foto` | TSE, Candidatos e Bens de candidatos (`coletar_tse.py`, `dados/tse/<ano>/<UF>.json`) | mostrado no site |
| Eleição | chapa | `sequencialChapa`, `titular` (ligam o vice ao titular para contas e votos) | TSE, Candidatos e Bens de candidatos (`coletar_tse.py`, `dados/tse/<ano>/<UF>.json`) | mostrado no site |
| Eleição | candidatos não eleitos e suplentes | toda a lista de candidaturas (consulta_cand) | TSE, Candidatos e Bens de candidatos | disponível na fonte, não coletado |
| Contas de campanha | receitas e despesas | `receitas`, `despesasContratadas`, `despesasPagas` | TSE, Prestação de contas (`coletar_contas.py`, `dados/tse/contas/<ano>/<UF>.json`) | mostrado no site |
| Contas de campanha | origem do dinheiro | `origensReceita`, `principaisDoadores` (nome, origem, valor), `doadoresOriginarios` | TSE, Prestação de contas (`coletar_contas.py`, `dados/tse/contas/<ano>/<UF>.json`) | mostrado no site |
| Contas de campanha | gastos | `gastosPorCategoria`; custo por voto e mediana (calculados em `gerar_politicos.py`) | TSE, Prestação de contas (`coletar_contas.py`, `dados/tse/contas/<ano>/<UF>.json`) | mostrado no site |
| Contas de campanha | CPF/CNPJ de doadores e fornecedores de campanha | colunas do ZIP; o coletor guarda só o nome do doador, não guarda fornecedor individual | TSE, Prestação de contas | disponível na fonte, não coletado |
| Votação por seção | totais | `totalVotos`, `turno` | TSE, Votação por seção e locais de votação (`coletar_secoes.py`, `dados/tse/secoes/<ano>/<UF>.json`) | mostrado no site |
| Votação por seção | locais de votação | `locaisDeVotacao` (nome, latitude, longitude, votos) | TSE, Votação por seção e locais de votação (`coletar_secoes.py`, `dados/tse/secoes/<ano>/<UF>.json`) | mostrado no site |
| Votação por seção | municípios | `municipios` (principais), `votosPorMunicipio` (mapa) | TSE, Votação por seção e locais de votação (`coletar_secoes.py`, `dados/tse/secoes/<ano>/<UF>.json`) | mostrado no site |
| Votação por seção | endereço das escolas e votos seção a seção | colunas do ZIP; o coletor resume e não guarda o endereço | TSE, Votação por seção e locais de votação | disponível na fonte, não coletado |
| Disputa | comparecimento | `aptos`, `comparecimento`, `abstencoes`, `brancos`, `nulos`, `validos` | TSE, Detalhe da votação por município e zona e Vagas (`coletar_disputa.py`, `dados/tse/disputa/<ano>/<UF>.json`) | mostrado no site |
| Disputa | vagas | `vagas` por cargo e local | TSE, Detalhe da votação por município e zona e Vagas (`coletar_disputa.py`, `dados/tse/disputa/<ano>/<UF>.json`) | mostrado no site |
| Partidos | votos por partido | `totalVotos`, por sigla: votos de legenda, nominais e federação (só cargos proporcionais) | TSE, Votação por partido por município e zona (`coletar_partidos.py`, `dados/tse/partidos/<ano>/<UF>.json`) | mostrado no site |
| Coligações | legendas do cargo | `coligacoes` (tipo C/F/I, nome, composição, situação) e `coligacaoDoPartido` (só o partido de quem foi eleito) | TSE, Consulta de coligações (`coletar_coligacoes.py`, `dados/tse/coligacoes/<ano>/<UF>.json`) | mostrado no site |
| Eleitorado | perfil por município e UF | `total`, `porGenero`, `porFaixaEtaria`, `porEscolaridade` | TSE, Perfil do eleitorado (`coletar_eleitorado.py`, `dados/tse/eleitorado/<ano>/<UF>.json`) | mostrado no site |
| Eleitorado | eleitorado do exterior (ZZ) | `dados/tse/eleitorado/2022/ZZ.json`, `dados/tse/disputa/2022/ZZ.json` | TSE, Perfil do eleitorado (`coletar_eleitorado.py`, `dados/tse/eleitorado/<ano>/<UF>.json`) | coletado, não usado no site |
| Eleitorado | demais colunas do perfil (ex.: estado civil, deficiência) | colunas do ZIP `perfil_eleitorado`, não conferidas coluna a coluna neste inventário | TSE, Perfil do eleitorado | disponível na fonte, não coletado |
| Cassação | motivo de cassação (indeferimento de candidatura) | ZIPs `dados/tse_bruto/motivo_cassacao/` de 2022 e 2024 (baixados por `baixar_tse.py`, fora do git, sem coletor) | TSE, Motivo de cassação | coletado, não usado no site |

### Câmara dos Deputados

Nacional: a bancada de cada estado é o filtro por `uf` dos 513 deputados em exercício. Arquivos em `dados/deputados/<id>.json` e `dados/*.json`.

| Dado | Fonte | Status |
|---|---|---|
| Ficha: `nome`, `nomeCivil`, `partido`, `uf`, `foto`, `email`, `situacao`, `condicaoEleitoral` | API de Dados Abertos da Câmara (`coletar.py`), `/deputados/<id>` | mostrado no site |
| Ficha: `gabinete` (prédio, sala, andar, telefone, email) | API de Dados Abertos da Câmara (`coletar.py`) | mostrado no site |
| Ficha: `nascimento`, `municipioNascimento`, `ufNascimento`, `escolaridade`, `redesSociais` | API de Dados Abertos da Câmara (`coletar.py`) | mostrado no site |
| Ficha: `coletadoEm` (data da coleta) | API de Dados Abertos da Câmara (`coletar.py`) | coletado, não usado no site |
| Ficha: discursos, profissões, mandatos externos, histórico de partido e de status | `/deputados/<id>/discursos`, `/profissoes`, `/mandatosExternos`, `/historico` | disponível na fonte, não coletado |
| Proposições: `proposicoes` (`id`, `tipo`, `numero`, `ano`, `ementa`) | API de Dados Abertos da Câmara (`coletar.py`), `dados/proposicoes/<id>.json` | mostrado no site |
| Proposições: situação: `situacao`, `tramitacao`, `despacho`, `orgao`, `dataSituacao`, `regime`, `palavrasChave`, `dataApresentacao`, `inteiroTeor` | API de Dados Abertos da Câmara (`coletar.py`), `dados/proposicoes_detalhe.json` | mostrado no site |
| Proposições: `ementaDetalhada` | API de Dados Abertos da Câmara (`coletar.py`), `dados/proposicoes_detalhe.json` | coletado, não usado no site |
| Proposições: `finalizada`, `consultadoEm` (controle do cache) | API de Dados Abertos da Câmara (`coletar.py`), `dados/proposicoes_detalhe.json` | coletado, não usado no site |
| Proposições: autores e coautores, temas, votações do projeto | `dados/proposicoes_autores.json`, `proposicoes_temas.json`, `proposicoes_votacoes.json` | mostrado no site |
| Proposições: emendas, pareceres e requerimentos (só projetos entram) | `/proposicoes` | disponível na fonte, não coletado |
| Votações nominais: `id`, `data`, `hora`, `descricao`, `proposicao`, `propId`, `ementa`, `aprovada`, `votos` (deputado, voto) | API de Dados Abertos da Câmara (`coletar.py`), `dados/votacoes/<ano>.json` | mostrado no site |
| Votações nominais: `orgao` da votação | API de Dados Abertos da Câmara (`coletar.py`), `dados/votacoes/<ano>.json` | coletado, não usado no site |
| Votações nominais: orientação das bancadas e blocos | `dados/orientacoes.json`, `dados/blocos.json` | mostrado no site |
| Presença: sessões deliberativas, sessões, comissões e outros eventos por deputado, por ano (2023 a 2026) | `dados/presenca_eventos.json` | mostrado no site |
| Órgãos e frentes: `frentes` da 57ª legislatura (`id`, `titulo`); órgãos (`sigla`, `nome`, `cargo`, `inicio`, `fim`) | API de Dados Abertos da Câmara (`coletar.py`), `dados/orgaos_deputados.json` | mostrado no site |
| Cota parlamentar: `mes`, `tipo`, `valor`, `fornecedor`, `cnpj`, `data`, `documento` | Câmara, CSV `cotas/Ano-<ano>.csv.zip` | mostrado no site |
| Cota parlamentar: `despesas.porMes` (soma por mês, gerada em `gerar.py`) | derivado da cota | coletado, não usado no site |
| Cota parlamentar: limite mensal da UF e média da bancada do estado | calculado em `gerar.py` | mostrado no site |
| Executivo federal: o que o Presidente enviou ao Congresso: `tipo`, `numero`, `ano`, `ementa`, `dataApresentacao`, `situacao`, `dataSituacao`, `inteiroTeor` | API de Dados Abertos da Câmara (`coletar.py`), `dados/executivo.json` | mostrado no site |
| Gastos e pessoal: verba de gabinete, remuneração, viagens e missões | portal da transparência da Câmara | disponível na fonte, não coletado |

### Senado

Nacional: 3 senadores por estado em `dados/senado.json`, filtrados por `uf`.

| Dado | Fonte | Status |
|---|---|---|
| Ficha: `id`, `nome`, `nomeCivil`, `partido`, `uf`, `foto`, `pagina`, `email`, `genero`, `participacao`, `titular`, `exercicioDesde`, `fimMandato` | API de Dados Abertos do Senado (`coletar.py`) | mostrado no site |
| Votações nominais: `id`, `data`, `hora`, `descricao`, `proposicao`, `propId`, `ementa`, `aprovada`, `resultadoTexto`, `secreta`, `totais`, `sessao`, `votos` (senador, voto, rótulo) | API de Dados Abertos do Senado (`coletar.py`), `dados/senado_votacoes/<ano>.json` | mostrado no site |
| Votações nominais: `processo` (id do processo da votação) | API de Dados Abertos do Senado (`coletar.py`), `dados/senado_votacoes/<ano>.json` | coletado, não usado no site |
| Autorias: matérias de autoria (`id`, `tipo`, `numero`, `ano`, `ementa`, `principal`, `dataApresentacao`, `situacao`, `dataSituacao`) | API de Dados Abertos do Senado (`coletar.py`), `dados/senado_autorias.json` (fora do git) | mostrado no site |
| Autorias: `dados/senado_materias.json` (situação dos projetos, com `processo`): só alimenta o resumo diário da página Histórico | API de Dados Abertos do Senado (`coletar.py`) | coletado, não usado no site |
| Cota (CEAPS): `mes`, `tipo`, `valor`, `fornecedor`, `data` | Senado, despesas_ceaps (`dados/senado_ceaps.json`, fora do git) | mostrado no site |
| Outros recursos: `foraCota`, `totalForaCota`, `beneficios`, `pessoal`, `escritorios` (nome, endereço) | API de Dados Abertos do Senado (`coletar.py`), `dados/senado_recursos.json` | mostrado no site |
| Comissões e mandatos: comissões de que participa, histórico de mandatos | API do Senado | disponível na fonte, não coletado |

### Assembleia Legislativa

Só as Assembleias com SAPL (AC, AL, AM, PB, PI, RO, TO) têm coletor (`coletar_estaduais.py`, pasta `dados/estaduais/<UF>/`). As outras 20 estão em `LEVANTAMENTO_DADOS.md`.

| Dado | Fonte | Status |
|---|---|---|
| Deputados: `id`, `nome`, `nomeCivil`, `titular`, `email`, `foto` | SAPL da Assembleia (`deputados.json`) | mostrado no site |
| Deputados: `legislatura`, `host` (arquivo `deputados.json`) | SAPL | coletado, não usado no site |
| Projetos: `materias_<ano>.json` (2023 a 2026): `tipo`, `tipoDescricao`, `numero`, `ano`, `dataApresentacao`, `ementa`, `situacao`, `linkTexto`, `idsDeputados` | SAPL, `/materia` | mostrado no site |
| Projetos: `emTramitacao` (chega a `site/dados/estadual/<UF>/<id>.json`) | SAPL | coletado, não usado no site |
| Projetos: `idsAutores` (autores que não são deputados) | SAPL | coletado, não usado no site |
| Votações nominais: `votacoes.json`: `data`, `idMateria`, `sim`, `nao`, `abstencoes`, `aprovada`, `resultado`, `votos` (deputado, voto); `materias_votadas.json`: `tipo`, `numero`, `ano`, `ementa` | SAPL | mostrado no site |
| Presença, cota/verba, remuneração: listados em `LEVANTAMENTO_DADOS.md` como pendentes para todas as Assembleias | portais de transparência | disponível na fonte, não coletado |

### Governo do estado

O governador consta como autor de matérias no SAPL; `coletar_governadores.py` guarda o que enviou à Assembleia em `dados/estaduais/<UF>/governo_<ano>.json` (2023 a 2026). Só nas 7 Assembleias SAPL. Os dados do governador como candidato (bens, contas, votos) estão em Eleições (TSE).

| Dado | Fonte | Status |
|---|---|---|
| Projetos, vetos e mensagens enviados: `tipo`, `tipoDescricao`, `numero`, `ano`, `dataApresentacao`, `ementa`, `situacao`, `linkTexto` | SAPL | mostrado no site |
| Projetos, vetos e mensagens enviados: `emTramitacao`, `idsAutores` | SAPL | coletado, não usado no site |
| Orçamento, despesas e pessoal do Executivo estadual: portais de transparência estaduais | portal de transparência de cada estado | disponível na fonte, não coletado |

### Prefeitura da capital

`coletar_prefeituras.py` (SAPL) e `coletar_prefeitura_{ba,go,sp}.py` guardam o que o prefeito da capital enviou à Câmara Municipal em `dados/municipais/<UF>/prefeitura_<ano>.json` (2025 e 2026). Só 7 capitais têm coletor. As demais e o motivo estão em `dados/municipais/capitais_sem_dados.md`.

| Dado | Fonte | Status |
|---|---|---|
| Projetos, vetos e mensagens enviados: `tipo`, `tipoDescricao`, `numero`, `ano`, `dataApresentacao`, `ementa`, `situacao`, `linkTexto` | SAPL ou sistema próprio da Câmara | mostrado no site |
| Projetos, vetos e mensagens enviados: `coletadoEm`, `idsAutores`, `emTramitacao`; em SP também `enviados` e `vistos` (controle) | idem | coletado, não usado no site |
| Vereadores da capital e votações da Câmara Municipal: sistema da Câmara Municipal | não coletado | disponível na fonte, não coletado |

## Estados

## AC: Acre

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estaduais.py` (SAPL), dados em `dados/estaduais/AC/`. A lista de deputados do SAPL não traz partido (vem do TSE).

| Dado | Fonte | Status |
|---|---|---|
| Deputados | igual ao comum; 25 deputados; host `sapl.al.ac.leg.br` | mostrado no site |
| Projetos (autoria) | igual ao comum; matérias por ano: 2023: 214, 2024: 227, 2025: 327, 2026: 116 | mostrado no site |
| Votações nominais | igual ao comum; 42 votações com votos nominais | mostrado no site |
| Presença, cota/verba, remuneração | pendentes (ver `LEVANTAMENTO_DADOS.md`) | disponível na fonte, não coletado |

### Governo do estado

| Dado | Fonte | Status |
|---|---|---|
| Projetos, vetos e mensagens do governador à Assembleia | igual ao comum; arquivos `governo_2023` a `governo_2026` | mostrado no site |

### Prefeitura da capital

| Dado | Fonte | Status |
|---|---|---|
| Projetos, vetos e mensagens do prefeito de Rio Branco à Câmara Municipal | igual ao comum; fonte: SAPL da Câmara de Rio Branco; arquivos `prefeitura_2025` e `prefeitura_2026` | mostrado no site |

## AL: Alagoas

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estaduais.py` (SAPL), dados em `dados/estaduais/AL/`. A lista de deputados do SAPL não traz partido (vem do TSE).

| Dado | Fonte | Status |
|---|---|---|
| Deputados | igual ao comum; 34 deputados; host `sapl.al.al.leg.br` | mostrado no site |
| Projetos (autoria) | igual ao comum; matérias por ano: 2023: 675, 2024: 593, 2025: 637, 2026: 292 | mostrado no site |
| Votações nominais | coletor roda, mas não achou votações nominais (arquivo `votacoes.json` vazio); a ficha do deputado fica sem votos | mostrado no site |
| Presença, cota/verba, remuneração | pendentes (ver `LEVANTAMENTO_DADOS.md`) | disponível na fonte, não coletado |

### Governo do estado

| Dado | Fonte | Status |
|---|---|---|
| Projetos, vetos e mensagens do governador à Assembleia | coletor roda, mas não achou matérias do governador no SAPL (arquivos `governo_<ano>.json` vazios); sem dados, a página cai no texto padrão | mostrado no site |

### Prefeitura da capital

sem coletor para Maceió: pesquisa de projetos da Câmara de Maceió lista só o cabeçalho da mensagem, sem situação nem link (ver `dados/municipais/capitais_sem_dados.md`).

## AM: Amazonas

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estaduais.py` (SAPL), dados em `dados/estaduais/AM/`. A lista de deputados do SAPL não traz partido (vem do TSE).

| Dado | Fonte | Status |
|---|---|---|
| Deputados | igual ao comum; 26 deputados; host `sapl.al.am.leg.br` | mostrado no site |
| Projetos (autoria) | igual ao comum; matérias por ano: 2023: 1370, 2024: 1007, 2025: 1102, 2026: 592 | mostrado no site |
| Votações nominais | igual ao comum; 3137 votações com votos nominais | mostrado no site |
| Presença, cota/verba, remuneração | pendentes (ver `LEVANTAMENTO_DADOS.md`) | disponível na fonte, não coletado |

### Governo do estado

| Dado | Fonte | Status |
|---|---|---|
| Projetos, vetos e mensagens do governador à Assembleia | igual ao comum; arquivos `governo_2023` a `governo_2026` | mostrado no site |

### Prefeitura da capital

sem coletor para Manaus: Manaus: sem dados atuais (ver `dados/municipais/capitais_sem_dados.md`).

## AP: Amapá

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

sem coletor; motivo: o site da Assembleia (`www.al.ap.leg.br`) não responde desta rede (timeout em 2026-10-22; Wayback devolve 403 "Web Site Blocked" e `sapl.al.ap.leg.br` não resolve). Deputados: só o TSE. Detalhes e nova tentativa: `LEVANTAMENTO_DADOS.md`.

### Governo do estado

sem coletor (depende do coletor da Assembleia)

### Prefeitura da capital

sem coletor para Macapá: o site da Câmara de Macapá não expõe API de proposições (ver `dados/municipais/capitais_sem_dados.md`).

## BA: Bahia

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estadual_ba.py`; dados em `dados/estaduais/BA/`. 63 deputados.

| Dado | Fonte | Status |
|---|---|---|
| Deputados: nome, partido, foto, nome civil, e-mail | ALBA, lista e ficha em HTML (`al.ba.gov.br/deputados`) | mostrado no site |
| Ficha: nascimento, profissão, formação, mandatos, filiações | ALBA, ficha `/deputados/deputado-estadual/<id>` | disponível na fonte, não coletado (fora do contrato; "No cargo até" vem do TSE) |
| Projetos de autoria 2023-2025 (PL, PLC, PEC, PDL, PRS) | ALBA, `/atividade-legislativa-nova/proposicoes`; sem proposição de 2026 na fonte | mostrado no site |
| Requerimentos, indicações, moções; tramitação completa | ALBA | disponível na fonte, não coletado (fora do escopo "só projetos") |
| Verba indenizatória 2023-2026: mês, categoria, valor, processo, nota | ALBA, planilha `verbas-idenizatorias-excel?ano=` | mostrado no site |
| Verba: fornecedor, CNPJ, glosa, PDF da nota | ALBA, `/transparencia/verbas-idenizatorias/<id>/` | disponível na fonte, não coletado (uma requisição por lançamento, cerca de 14 mil) |
| Emendas parlamentares (despesas por deputado e ano, 2017-2026) | Dados Abertos Bahia (CKAN), ZIP com CSV DESPESAS | mostrado no site |
| Emendas: pagamentos e liquidações (credor, data, objeto) | CKAN, CSV PAGAMENTOS no mesmo ZIP | disponível na fonte, não coletado (ligação por `num_codigo`) |
| Votações nominais, presença, API de dados abertos | NoPaper (`albalegis.nopapercloud.com.br`) | bloqueado (HTTP 403 Cloudflare no curl e no Firefox) |
| Remuneração dos deputados | ALBA RH, PDF `ALBA_ECV_Deputados.pdf` | disponível na fonte, não coletado (só PDF) |
| Diárias de deputados | portal de RH da ALBA | não existe (o portal só lista servidores) |

### Governo do estado

sem coletor (depende do coletor da Assembleia)

### Prefeitura da capital

| Dado | Fonte | Status |
|---|---|---|
| Projetos, vetos e mensagens do prefeito de Salvador à Câmara Municipal | igual ao comum; fonte: consulta própria da Câmara de Salvador (Scriptcase); arquivos `prefeitura_2025` e `prefeitura_2026` | mostrado no site |

## CE: Ceará

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estadual_ce.py`; dados em `dados/estaduais/CE/`. 53 deputados (46 titulares ou licenciados e 7 suplentes em exercício).

| Dado | Fonte | Status |
|---|---|---|
| Deputados: nome, partido, foto, e-mail, nome civil | Alece, `al.ce.gov.br/deputados` e fichas (HTML) | mostrado no site |
| Projetos 2023+ (PL, PLC, PEC, PDL, PR) com autoria e situação | Alece, `www2.al.ce.gov.br/legislativo/proposicoes` | mostrado no site |
| Indicações e requerimentos; mensagens do Executivo | Alece, www2 | disponível na fonte, não coletado (milhares; só tipos de projeto entram) |
| Votações nominais (31ª legislatura, 60 matérias, voto por deputado) | Alece, `transparencia.al.ce.gov.br/consultas-gerais/votacao-nominal` (XLSX por matéria) | mostrado no site |
| Verba de desempenho parlamentar (VDP) por mês, com fornecedor e CNPJ, 2022-2026 | Alece, `transparencia.al.ce.gov.br/despesas/verba-desempenho-parlamentar/csv` | mostrado no site |
| VDP: arquivo de 2022, `empenho` e `descricao` | mesmo CSV; o site só lê anos a partir de 2023 | coletado, não usado no site |
| Remuneração mensal 2023+ (bruto, líquido, descontos, teto, 13º) | Alece, `/gestao-de-pessoas/pessoal/csv` (categoria DEPUTADOS) | mostrado no site |
| Diárias 2023+ (quase nenhuma é de deputado) | Alece, `/despesas/despesas-diarias?export=csv` | mostrado no site |
| Emendas parlamentares | Alece, `/pagina/transparencia-e-rastreabilidade-de-emendas` | disponível na fonte, não coletado (a página só mostra o quadro consolidado da LOA, sem arquivo) |
| Presença em plenário | Alece | não existe |
| Comissões, frentes, atas, ordem do dia; API OpenAPI do portal (contratos, empenhos) | Alece | disponível na fonte, não coletado (fora do contrato) |

### Governo do estado

sem coletor (depende do coletor da Assembleia)

### Prefeitura da capital

sem coletor para Fortaleza: SAPL de Fortaleza não registra o autor nas matérias do Executivo (ver `dados/municipais/capitais_sem_dados.md`).

## DF: Distrito Federal

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2026; igual ao comum; 2022 e 2026 trazem deputado distrital no lugar de deputado estadual; sem prefeito, vice e vereador (o DF não tem eleição municipal, por isso sem arquivo de 2024) | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022 (DF sem 2024: não há eleição municipal) | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022 (DF sem 2024: não há eleição municipal) | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022 (DF sem 2024: não há eleição municipal) | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022 (DF sem 2024: não há eleição municipal) | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022 (DF sem 2024: não há eleição municipal) | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022 (DF sem 2024: não há eleição municipal) | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa (Câmara Legislativa do DF)

sem coletor; motivo: `www.cl.df.gov.br` não responde desta rede (timeout em 2026-10-22) e `sapl.cl.df.gov.br` não resolve. Deputados distritais: só o TSE. Detalhes: `LEVANTAMENTO_DADOS.md`.

### Governo do estado

sem coletor (depende do coletor da Assembleia)

### Prefeitura da capital

não se aplica: Brasília não tem prefeito.

## ES: Espírito Santo

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

sem coletor; motivo: `www.al.es.gov.br` (Transparência e Dados Abertos) não responde desta rede (timeout em 2026-10-22). Pelo ITGP, a Assembleia publica proposições, salário nominal, viagens e presença, e não publica votações nominais nem verba indenizatória (não conferido). Deputados: só o TSE.

### Governo do estado

sem coletor (depende do coletor da Assembleia)

### Prefeitura da capital

sem coletor para Vitória: site da Câmara de Vitória responde 403 (desafio Cloudflare) (ver `dados/municipais/capitais_sem_dados.md`).

## GO: Goiás

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estadual_go.py`; dados em `dados/estaduais/GO/`. 43 deputados.

| Dado | Fonte | Status |
|---|---|---|
| Deputados: nome, partido, e-mail, foto, nome civil | Alego, `portal.al.go.leg.br/deputados/em-exercicio` e `/perfil/<id>` | mostrado no site |
| Requerimentos de 2023 (autoria) | Alego Transparência, `/api/transparencia/requerimentos`; de 2024 em diante: não existe na API | mostrado no site |
| Proposições (projetos de lei) | Alego, `processos/busca-avancada` | disponível na fonte, não coletado (a busca devolve vazio sem os parâmetros certos e a busca simples dá 500) |
| Votações nominais 2023+ (2042 votos nominais) | Alego Transparência, `votacoes.json?tipo=detalhes&ano=` | mostrado no site |
| Verba indenizatória mensal 2023-2026 (valor apresentado e indenizado) | Alego Transparência, `/api/transparencia/verbas_indenizatorias`; sem fornecedor nem categoria | mostrado no site |
| Verba: resumo anual | Alego Transparência, `verbas_indenizatorias/resumo-anual` | disponível na fonte, não coletado (redundante com o mensal) |
| Remuneração 2026 | Alego Transparência, `/api/transparencia/remuneracoes?categoria=7`; 2023-2025: não existe na API (0 lançamentos) | mostrado no site |
| Diárias dos deputados 2023-2026 | Alego Transparência, `/api/transparencia/diarias` | mostrado no site |
| Presença | Alego Transparência | disponível na fonte, não coletado (a API só traz datas e pauta das sessões) |
| Emendas | Alego | não existe |

### Governo do estado

sem coletor (depende do coletor da Assembleia)

### Prefeitura da capital

| Dado | Fonte | Status |
|---|---|---|
| Projetos, vetos e mensagens do prefeito de Goiânia à Câmara Municipal | igual ao comum; fonte: SUAP da Câmara de Goiânia; arquivos `prefeitura_2025` e `prefeitura_2026` | mostrado no site |

## MA: Maranhão

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

sem coletor; motivo: `sistemas.al.ma.leg.br` e `www.al.ma.leg.br` não respondem desta rede (timeout em 2026-10-22). Deputados: só o TSE. Detalhes: `LEVANTAMENTO_DADOS.md`.

### Governo do estado

sem coletor (depende do coletor da Assembleia)

### Prefeitura da capital

sem coletor para São Luís: site da Câmara de São Luís responde 403 (ver `dados/municipais/capitais_sem_dados.md`).

## MG: Minas Gerais

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estadual_mg.py`; dados em `dados/estaduais/MG/`. 77 deputados em exercício; 72 ligam à ficha do TSE.

| Dado | Fonte | Status |
|---|---|---|
| Deputados: nome, partido, nome civil, e-mail | ALMG, API `dadosabertos.almg.gov.br/api/v2/deputados/em_exercicio` e `lista_telefonica` | mostrado no site |
| Foto | ALMG | disponível na fonte, não coletado (a API não dá URL de foto; o site usa a do TSE) |
| Ficha: naturalidade, nascimento, profissão, redes sociais; comissões, pronunciamentos, reuniões | ALMG, `deputados/{id}` e rotas de comissões | disponível na fonte, não coletado (fora do contrato) |
| Proposições de autoria 2023-2026 (PL, PLC, PEC, RQC, RQN etc.) | ALMG, `proposicoes/pesquisa/direcionada` (janela mensal; a API corta em 10 mil resultados) | mostrado no site |
| Tramitação e histórico de cada proposição | ALMG, `listaHistoricoTramitacoes` e CSV de tramitação | disponível na fonte, não coletado (sem espaço no contrato) |
| Verba indenizatória 2025-2026 por nota (tipo, fornecedor, CNPJ, data, valor) | ALMG, `prestacao_contas/verbas_indenizatorias/deputados/{id}/{ano}/{mes}` | mostrado no site |
| Verba indenizatória 2023-2024 | ALMG, mesma API | disponível na fonte, não coletado (muda uma constante; cerca de 1 h de coleta) |
| CSV `verbas-indenizatorias` 2019-2026 | ALMG, arquivos abertos | disponível na fonte, não coletado (vem sem valores, emitente e CNPJ) |
| Votações nominais, presença | ALMG | não existe (Swagger conferido em 2026-10-22, nenhuma rota) |
| Remuneração nominal, diárias, emendas | ALMG | não existe (sem rota no Swagger; o ITGP também diz que a ALMG não publica remuneração) |

### Governo do estado

sem coletor (depende do coletor da Assembleia)

### Prefeitura da capital

sem coletor para Belo Horizonte: site da Câmara de Belo Horizonte inalcançável da rede onde se testou (ver `dados/municipais/capitais_sem_dados.md`).

## MS: Mato Grosso do Sul

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estadual_ms.py`; dados em `dados/estaduais/MS/`. 24 deputados; a lista é a dos eleitos de 2022 do TSE (a página da Assembleia é HTML dinâmico).

| Dado | Fonte | Status |
|---|---|---|
| Deputados: nome, partido, nome civil | TSE 2022 (a lista da ALEMS não foi achada em formato coletável) | mostrado no site |
| Foto e e-mail da Assembleia | ALEMS | não existe (não achados) |
| CEAP 2023-2026 por nota (categoria, fornecedor, CNPJ, valor, comprovante em PDF) | ALEMS, `transparencia2.al.ms.gov.br/ceap/notas/exportar-csv?ano=` | mostrado no site |
| CEAP: `documento`, `emissao` | mesmo CSV | coletado, não usado no site |
| CEAP 2012-2022 | ALEMS, mesmo CSV | disponível na fonte, não coletado (fora do recorte) |
| CEAP de 9 substitutos sem ficha no TSE | ALEMS, mesmo CSV | disponível na fonte, não coletado (sem deputado eleito de 2022 para ligar) |
| Remuneração dos parlamentares | portal antigo ALEMS, `gerdocumento/1201` | disponível na fonte, não coletado (só PDF mensal) |
| Diárias | ALEMS, `/consulta-diarias` | não existe (2021-2026 só "Não houve despesa") |
| Proposições e votações nominais | SGPL, `sgpl.consulta.al.ms.gov.br` | bloqueado (API responde 403 "Invalid CAPTCHA solution") |
| Presença, emendas | ALEMS | não existe (não encontradas) |

### Governo do estado

sem coletor (depende do coletor da Assembleia)

### Prefeitura da capital

sem coletor para Campo Grande: site da Câmara de Campo Grande só responde com reCAPTCHA (ver `dados/municipais/capitais_sem_dados.md`).

## MT: Mato Grosso

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estadual_mt.py`; dados em `dados/estaduais/MT/`. 24 deputados; a lista vem do portal de transparência (Elotech).

| Dado | Fonte | Status |
|---|---|---|
| Deputados: nome civil, matrícula; partido e nome parlamentar via TSE (23 de 24) | ALMT, API Elotech `almt.eloweb.net/portaltransparencia-api/api/servidores?cargo=DEPUTADO` | mostrado no site |
| Foto | `www.al.mt.gov.br` | disponível na fonte, não coletado (inacessível desta rede) |
| Remuneração mensal 2023-2026 (vencimentos, descontos, proventos; 13º como linha extra) | ALMT, Elotech `/servidores/{matrícula}`, `dadosFinanceiros` | mostrado no site |
| Diárias 2023-2026 (só as dos deputados) | ALMT, Elotech `/diarias` | mostrado no site |
| Verbas, cotas parlamentares, emendas | ALMT, Elotech | não existe (rotas vazias (verbas e emendas) ou sem chamada de dados (cotas)) |
| Projetos, votações nominais, presença | `www.al.mt.gov.br` | disponível na fonte, não coletado (site inacessível desta rede; o portal Elotech não tem essas rotas) |
| Remuneração: `folha`; diárias: `dataFim`, `passagem`, `quantidade`, `anulado`, `situacao`, `empenho` | Elotech | coletado, não usado no site |

### Governo do estado

sem coletor (depende do coletor da Assembleia)

### Prefeitura da capital

sem coletor para Cuiabá: site da Câmara de Cuiabá responde "Request Rejected" (firewall) (ver `dados/municipais/capitais_sem_dados.md`).

## PA: Pará

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estadual_pa.py`; dados em `dados/estaduais/PA/`. 41 deputados; 37 ligam à ficha do TSE.

| Dado | Fonte | Status |
|---|---|---|
| Deputados: nome, partido, foto, ficha, e-mail, nome civil | ALEPA, `alepa.pa.gov.br/Transparencia/FrequenciaSessoes` (cartões) e fichas | mostrado no site |
| Presença mensal desde fev/2023 (presente, licenciado, ausente) | ALEPA, `FrequenciaSessoes` (POST de callback DevExpress) | mostrado no site |
| Verba indenizatória 2023-2026 por liquidação (data, classificação, descrição, valor) | ALEPA, painéis Quartertec (`alepa.quartertec.com.br`, dashboards 57 e 58); sem fornecedor | mostrado no site |
| Verba de gabinete: total mensal e nº de assessores (só jun a set/2026) | ALEPA, SIGEP `frame_verbagabinete.php` | mostrado no site |
| Verba de gabinete: detalhamento por servidor | SIGEP | disponível na fonte, não coletado (dados de pessoas (CPF mascarado), fora do escopo) |
| Diárias dos parlamentares 2023-2026 | ALEPA, painéis Quartertec; destino e motivo em texto livre | mostrado no site |
| Verba: `data`, `descricao`, `assessores`; diárias: `categoria`, descrição com destino e motivo | painéis Quartertec e SIGEP | coletado, não usado no site |
| Remuneração dos deputados | ALEPA, `EstruturaRemuneratoriaDeputados` | disponível na fonte, não coletado (só PDF de reajustes) |
| Emendas estaduais | portal do Estado, `www.sistemas.pa.gov.br/portaltransparencia/emendas-parlamentares-estaduais` | disponível na fonte, não coletado (outro host, não lido) |
| Projetos e votações nominais | ALEPA | não existe (o Banco de Leis só tem leis, até 50 por consulta) |

### Governo do estado

sem coletor (depende do coletor da Assembleia)

### Prefeitura da capital

sem coletor para Belém: listagens de Belém vêm vazias ou sem autor para projetos do Executivo (ver `dados/municipais/capitais_sem_dados.md`).

## PB: Paraíba

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estaduais.py` (SAPL), dados em `dados/estaduais/PB/`. A lista de deputados do SAPL não traz partido (vem do TSE).

| Dado | Fonte | Status |
|---|---|---|
| Deputados | igual ao comum; 41 deputados; host `sapl.al.pb.leg.br` | mostrado no site |
| Projetos (autoria) | igual ao comum; matérias por ano: 2023: 1660, 2024: 2008, 2025: 2978, 2026: 1691 | mostrado no site |
| Votações nominais | igual ao comum; 148 votações com votos nominais | mostrado no site |
| Presença, cota/verba, remuneração | pendentes (ver `LEVANTAMENTO_DADOS.md`) | disponível na fonte, não coletado |

### Governo do estado

| Dado | Fonte | Status |
|---|---|---|
| Projetos, vetos e mensagens do governador à Assembleia | igual ao comum; arquivos `governo_2023` a `governo_2026` | mostrado no site |

### Prefeitura da capital

| Dado | Fonte | Status |
|---|---|---|
| Projetos, vetos e mensagens do prefeito de João Pessoa à Câmara Municipal | igual ao comum; fonte: SAPL da Câmara de João Pessoa; arquivos `prefeitura_2025` e `prefeitura_2026` | mostrado no site |

## PE: Pernambuco

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estadual_pe.py`; dados em `dados/estaduais/PE/`. 49 deputados em exercício; 8 não ligam à ficha do TSE (suplentes em exercício).

| Dado | Fonte | Status |
|---|---|---|
| Deputados: nome parlamentar, partido, e-mail, foto | ALEPE, `alepe.pe.gov.br/servicos/transparencia/dep/deputados.php?leg=-16` e `dadosabertos.alepe.pe.gov.br/api/v1/parlamentares/` | mostrado no site |
| Nome civil | ALEPE | não existe (a fonte não dá) |
| Projetos, indicações e requerimentos de autoria 2023-2026 (ementa) | ALEPE, `dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/`; autor ligado por nome | mostrado no site |
| Situação, tramitação e texto das proposições | ALEPE | disponível na fonte, não coletado (a API só dá a ementa) |
| Verba indenizatória 2023-2026 por nota (rubrica, data, empresa, CNPJ, valor, pedido ou complemento) | ALEPE, `adm/verbaindenizatoria*.php` | mostrado no site |
| Remuneração | ALEPE, API `remuneracao` | disponível na fonte, não coletado (por cargo, não por pessoa) |
| Servidores, lotações, contratos, licitações | ALEPE | disponível na fonte, não coletado (fora do escopo de deputado) |
| Presença e votações nominais | ALEPE | não existe (`legis.alepe.pe.gov.br` só tem tela de login) |
| Diárias | ALEPE | não existe (não achadas na transparência) |
| Emendas | ALEPE, `/financas` | disponível na fonte, não coletado (seção não investigada; emendas impositivas aparecem só em requerimentos) |

### Governo do estado

sem coletor (depende do coletor da Assembleia)

### Prefeitura da capital

sem coletor para Recife: SAPL do Recife em manutenção (503) (ver `dados/municipais/capitais_sem_dados.md`).

## PI: Piauí

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estaduais.py` (SAPL), dados em `dados/estaduais/PI/`. A lista de deputados do SAPL não traz partido (vem do TSE).

| Dado | Fonte | Status |
|---|---|---|
| Deputados | igual ao comum; 42 deputados; host `sapl.al.pi.leg.br` | mostrado no site |
| Projetos (autoria) | igual ao comum; matérias por ano: 2023: 532, 2024: 356, 2025: 480, 2026: 260 | mostrado no site |
| Votações nominais | igual ao comum; 136 votações com votos nominais | mostrado no site |
| Presença, cota/verba, remuneração | pendentes (ver `LEVANTAMENTO_DADOS.md`) | disponível na fonte, não coletado |

### Governo do estado

| Dado | Fonte | Status |
|---|---|---|
| Projetos, vetos e mensagens do governador à Assembleia | coletor roda, mas não achou matérias do governador no SAPL (arquivos `governo_<ano>.json` vazios); sem dados, a página cai no texto padrão | mostrado no site |

### Prefeitura da capital

sem coletor para Teresina: acompanhamento de processos de Teresina pede número e senha; portal da transparência fora do ar (ver `dados/municipais/capitais_sem_dados.md`).

## PR: Paraná

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estadual_pr.py`; dados em `dados/estaduais/PR/`. 54 deputados.

| Dado | Fonte | Status |
|---|---|---|
| Deputados | ALEP, `assembleia.pr.leg.br/deputados/conheca` | mostrado no site |
| Proposições de autoria (POST `webservices.assembleia.pr.leg.br/api/public/proposicao/filtrar`) | ALEP; autor só por nome, ligado por nome, sem id | mostrado no site |
| Votações nominais | ALEP | disponível na fonte, não coletado (só PDF por sessão) |
| Presença | ALEP, `/api/presenca/ano` | mostrado no site |
| Remuneração | ALEP, `transparencia.assembleia.pr.leg.br/api/remuneracao` | mostrado no site |
| Diárias (ligadas por nome civil) | ALEP, `/api/diarias` | mostrado no site |
| Ressarcimento de despesas (verba) | ALEP, `consultas.assembleia.pr.leg.br` | bloqueado (reCAPTCHA) |
| Passagens e cartões por deputado | ALEP | não existe (não trazem o deputado) |
| Emendas | ALEP | disponível na fonte, não coletado (não investigadas) |

### Governo do estado

sem coletor (depende do coletor da Assembleia)

### Prefeitura da capital

sem coletor para Curitiba: consulta de proposições de Curitiba exige CAPTCHA (ver `dados/municipais/capitais_sem_dados.md`).

## RJ: Rio de Janeiro

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estadual_rj.py`; dados em `dados/estaduais/RJ/`. 70 deputados; a lista é a dos eleitos de 2022 do TSE (`www.alerj.rj.gov.br/Deputados` dá 404).

| Dado | Fonte | Status |
|---|---|---|
| Deputados: nome, partido, e-mail | TSE 2022 (suplentes em exercício ficam de fora) | mostrado no site |
| Foto | ALERJ | não existe (não existe na fonte lida) |
| Presença mensal em sessões (faltas; só 2026, fev a set sem julho) | ALERJ, Lotus Notes `alerjln1.alerj.rj.gov.br/ordemdia.nsf/presint?OpenForm` | mostrado no site |
| Emendas impositivas 2025-2026 (autor, valor, órgão, função, objeto, beneficiário, município) | ALERJ, transparência `/121` (XLSX por ano) | mostrado no site |
| Emendas: `numero`, `beneficiario`, `municipio`, `valor` | XLSX `/121` | coletado, não usado no site |
| Acompanhamento da execução das emendas | ALERJ, `/134` | disponível na fonte, não coletado (só painéis Google Data Studio e Power BI) |
| Diárias `/119`, viagens `/66`, folha `/73`, benefícios `/33` | ALERJ, transparência | disponível na fonte, não coletado (só PDF (`/73` é de servidores)) |
| Subsídio dos deputados | ALERJ, `/62` | não existe (página sem arquivo; só o texto constitucional) |
| Verba de gabinete | ALERJ, `docigp.alerj.rj.gov.br/transparencia` | disponível na fonte, não coletado (aplicação Laravel por login e consulta, não explorada) |
| Projetos e votações nominais | ALERJ | disponível na fonte, não coletado (sem fonte aberta achada; o Lotus Notes `alerjln1` só foi explorado para a presença) |

### Governo do estado

sem coletor (depende do coletor da Assembleia)

### Prefeitura da capital

sem coletor para Rio de Janeiro: site da Câmara do Rio inalcançável da rede onde se testou (ver `dados/municipais/capitais_sem_dados.md`).

## RN: Rio Grande do Norte

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estadual_rn.py`; dados em `dados/estaduais/RN/`. 24 deputados; 23 ligam à ficha do TSE.

| Dado | Fonte | Status |
|---|---|---|
| Deputados: nome civil, partido atual, foto | ALRN, API `api-transparencialegislativa.al.rn.leg.br/elegis-api-transp-legislativa/parlamentar` | mostrado no site |
| E-mail | ALRN, `www.al.rn.leg.br/deputado/<id>/<slug>` | disponível na fonte, não coletado (não vem na API de parlamentar) |
| Projetos 2023-2026 (só "Projeto" e "Proposta"; autoria por iniciativa) | ALRN, API `processo?iniciativa=` | mostrado no site |
| Requerimentos, indicações, ofícios | ALRN, API | disponível na fonte, não coletado (fora do escopo) |
| Votações nominais de plenário (83; votos secretos só como placar) | ALRN, API `processo/ultimas-votacoes` e `detalhamento-votacao` | mostrado no site |
| Votações de comissão; 95 votações de plenário | ALRN, API | disponível na fonte, não coletado (sem campo de comissão no contrato; a API devolve 500 nas antigas) |
| Presença 2024-2026 em sessões plenárias | ALRN, API `reuniao/presenca/<id>` | mostrado no site |
| Presença de 2023 e parte de 2024 (212 de 471 sessões) | ALRN, API | disponível na fonte, não coletado (a API responde 500) |
| Cotas (CEAP) | ALRN, `api-transparencia.al.rn.leg.br/verbas` | bloqueado (401; token Bearer embutido no JS do site, não usado por ser credencial) |
| Remuneração dos deputados, diárias, emendas | ALRN | não existe (não encontradas) |

### Governo do estado

sem coletor (depende do coletor da Assembleia)

### Prefeitura da capital

| Dado | Fonte | Status |
|---|---|---|
| Projetos, vetos e mensagens do prefeito de Natal à Câmara Municipal | igual ao comum; fonte: SAPL da Câmara de Natal; arquivos `prefeitura_2025` e `prefeitura_2026` | mostrado no site |

## RO: Rondônia

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estaduais.py` (SAPL), dados em `dados/estaduais/RO/`. A lista de deputados do SAPL não traz partido (vem do TSE).

| Dado | Fonte | Status |
|---|---|---|
| Deputados | igual ao comum; 26 deputados; host `sapl.al.ro.leg.br` | mostrado no site |
| Projetos (autoria) | igual ao comum; matérias por ano: 2023: 601, 2024: 432, 2025: 756, 2026: 730 | mostrado no site |
| Votações nominais | igual ao comum; 367 votações com votos nominais | mostrado no site |
| Presença, cota/verba, remuneração | pendentes (ver `LEVANTAMENTO_DADOS.md`) | disponível na fonte, não coletado |

### Governo do estado

| Dado | Fonte | Status |
|---|---|---|
| Projetos, vetos e mensagens do governador à Assembleia | igual ao comum; arquivos `governo_2023` a `governo_2026` | mostrado no site |

### Prefeitura da capital

sem coletor para Porto Velho: SAPL de Porto Velho não registra o autor nas matérias do Executivo (ver `dados/municipais/capitais_sem_dados.md`).

## RR: Roraima

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estadual_rr.py`; dados em `dados/estaduais/RR/`. 25 deputados.

| Dado | Fonte | Status |
|---|---|---|
| Deputados: nome parlamentar, nome civil, partido, foto, e-mail, ficha | ALERR, `al.rr.leg.br/deputados-estaduais-2023/` e fichas | mostrado no site |
| Verba indenizatória de set/2025 em diante (categoria e valor por deputado e mês; ODT) | ALERR, `transparencia.al.rr.leg.br` (plugin WP Display Files) | mostrado no site |
| Verba até ago/2025 | ALERR, `.../verbas-indenizatorias-de-gabinete-ate-ago25/` | disponível na fonte, não coletado (só PDF) |
| Diárias de out/2025 em diante (XLSX/ODS mensal) | ALERR, `transparencia.al.rr.leg.br` | mostrado no site |
| Diárias até set/2025 | ALERR, `.../diarias-e-passagens-ate-set25/` | disponível na fonte, não coletado (formato por mês não aberto) |
| Verba: `item`, `grupo`; envelope `mesesColetados`; diárias: `dataFim` | ODT e XLSX | coletado, não usado no site |
| Projetos, votações nominais, presença | ALERR, `sapl.al.rr.leg.br` | bloqueado (403 Forbidden) |
| Remuneração por deputado | ALERR | não existe (só planilha de servidores sem remuneração e resumos de folha em PDF) |
| Emendas | ALERR | não existe (link vazio `#` no portal) |

### Governo do estado

sem coletor (depende do coletor da Assembleia)

### Prefeitura da capital

| Dado | Fonte | Status |
|---|---|---|
| Projetos, vetos e mensagens do prefeito de Boa Vista à Câmara Municipal | igual ao comum; fonte: SAPL da Câmara de Boa Vista; arquivos `prefeitura_2025` e `prefeitura_2026` | mostrado no site |

## RS: Rio Grande do Sul

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estadual_rs.py`; dados em `dados/estaduais/RS/`. 55 deputados; a lista é a dos eleitos de 2022 do TSE (`www.al.rs.gov.br` e www2/ww3 não respondem).

| Dado | Fonte | Status |
|---|---|---|
| Deputados: nome parlamentar, nome civil, partido | TSE 2022 | mostrado no site |
| Foto, e-mail, link da ficha da Assembleia | `www.al.rs.gov.br` | disponível na fonte, não coletado (sem resposta desta rede) |
| Diárias 2023-2026 (só linhas cujo favorecido casa com um deputado) | CKAN `dados.rs.gov.br`, pacote "Diárias do Estado" (ZIP por ano) | mostrado no site |
| Diárias: `dataFim`, `tipo`, `origem`, `empenho`; destino e motivo do CSV | CKAN `dados.rs.gov.br` | coletado, não usado no site |
| Remuneração dos deputados | CKAN `dados.rs.gov.br` (folha estadual) | disponível na fonte, não coletado (não aberto; dado por deputado não confirmado) |
| Projetos, votações nominais, presença | `www.al.rs.gov.br` | disponível na fonte, não coletado (timeout desta rede) |
| Emendas | portal do Estado, `www.transparencia.rs.gov.br/emendas-parlamentares/` | disponível na fonte, não coletado (não aberto; é do Executivo) |
| Verba ou cota de gabinete | portal do Estado e CKAN | não existe (não achada (`www.al.rs.gov.br` inacessível)) |

### Governo do estado

sem coletor (depende do coletor da Assembleia)

### Prefeitura da capital

sem coletor para Porto Alegre: site da Câmara de Porto Alegre inalcançável da rede onde se testou (ver `dados/municipais/capitais_sem_dados.md`).

## SC: Santa Catarina

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estadual_sc.py`; dados em `dados/estaduais/SC/`. 41 deputados; 37 ligam à ficha do TSE.

| Dado | Fonte | Status |
|---|---|---|
| Deputados: nome civil, nome de urna, partido, e-mail | ALESC, `transparencia.alesc.sc.gov.br/deputados` + TSE | mostrado no site |
| Foto | ALESC | não existe (não existe na fonte lida) |
| Gabinetes parlamentares (cota de exercício) 2023-2026, com favorecido | ALESC, `/gabinetes-parlamentares/csv/<ano>` | mostrado no site |
| Gabinetes: histórico 2011-2022 | ALESC, mesmo CSV | disponível na fonte, não coletado (pedir `PRIMEIRO_ANO`) |
| Diárias e passagens dos deputados 2023-2026 | ALESC, `/diarias/csv/<ano>` | mostrado no site |
| Diárias: destino e motivo | ALESC, relatório de cada concessão | disponível na fonte, não coletado (só no relatório) |
| Remuneração (contracheque) 2025-2026 | ALESC, `/deputados/contracheque/<id>?ano=&mes=`; 2018-2024: disponível, não coletado | mostrado no site |
| Presença em sessões plenárias (por sessão desde fev/2023, somada por mês) | ALESC, e-Legis `portalelegis.alesc.sc.gov.br/sessoes-plenarias/<codigo>/presenca` | mostrado no site |
| Presença em comissões | ALESC, `/comissoes-permanentes/presenca` | disponível na fonte, não coletado (não coletada) |
| Verba: `data`, `trecho`; diárias: `quantidade`; deputados: `nomeFonte`; `presenca.json`: chave `sessoes` | CSV e e-Legis | coletado, não usado no site |
| Proposições e votações nominais | ALESC, e-Legis `/proposicoes/atividade-parlamentar` | disponível na fonte, não coletado (um documento por proposição, extrato de votação por Ajax, sem exportação) |
| Despesas, pagamentos a credores, receitas | ALESC, CSV `/despesas/dados-abertos`, `/pagamentos/dados-abertos`, `/receitas/dados-abertos` | disponível na fonte, não coletado (do órgão, não por deputado) |

### Governo do estado

sem coletor (depende do coletor da Assembleia)

### Prefeitura da capital

sem coletor para Florianópolis: site da Câmara de Florianópolis só responde com reCAPTCHA (ver `dados/municipais/capitais_sem_dados.md`).

## SE: Sergipe

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estadual_se.py`; dados em `dados/estaduais/SE/`. 24 deputados; 23 ligam à ficha do TSE.

| Dado | Fonte | Status |
|---|---|---|
| Deputados: nome, partido atual, foto, link da ficha no Alese Legis | Alese, carrossel de `al.se.leg.br`; nome civil completado pelo TSE quando um só eleito casa | mostrado no site |
| E-mail | Alese | não existe (não aparece na página inicial) |
| Ressarcimento dos deputados (verba) | Alese, `.../despesas/ressarcimento-dos-deputados/` | disponível na fonte, não coletado (só PDF mensal) |
| Diárias | Alese, `.../despesas/diarias/` | disponível na fonte, não coletado (só PDF) |
| Subsídio e remuneração | Alese, `.../recursos-humanos/subsidio-e-remuneracoes/` | disponível na fonte, não coletado (só PDF) |
| Emendas parlamentares | Alese | disponível na fonte, não coletado (a página só aponta para um painel Power BI do Executivo) |
| Projetos, votações, presença | Alese Legis, `aleselegis.al.se.leg.br` | bloqueado (timeout em 2 tentativas; o ITGP diz que a Alese não publica pautas, presença nem votação nominal) |

### Governo do estado

sem coletor (depende do coletor da Assembleia)

### Prefeitura da capital

sem coletor para Aracaju: SAPL antigo de Aracaju responde 503 (só HTTP) (ver `dados/municipais/capitais_sem_dados.md`).

## SP: São Paulo

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estadual_sp.py`; dados em `dados/estaduais/SP/`. 94 deputados.

| Dado | Fonte | Status |
|---|---|---|
| Deputados: nome, partido, foto, e-mail, nome civil | Alesp, `al.sp.gov.br/repositorioDados` (`deputados.xml`) | mostrado no site |
| Verba de gabinete 2023+ com CNPJ | Alesp, `despesas_gabinetes_<ano>.xml` | mostrado no site |
| Remuneração (folha de subsídio por mês) | Alesp, transparência (HTML) | mostrado no site |
| Presença | Alesp, `legis-api-portal-prd.al.sp.gov.br` | mostrado no site |
| Projetos de autoria (só PL, PLC, PR, PDL, PEC, PCONST) | Alesp, `proposituras.zip` + `documento_autor.zip` | mostrado no site |
| Requerimentos, indicações, moções | Alesp, `proposituras.zip` | disponível na fonte, não coletado (79 mil documentos) |
| Votações nominais | Alesp | disponível na fonte, não coletado (só PDF por sessão) |
| Diárias e emendas | Alesp | não existe (sem fonte) |

### Governo do estado

sem coletor (depende do coletor da Assembleia)

### Prefeitura da capital

| Dado | Fonte | Status |
|---|---|---|
| Projetos, vetos e mensagens do prefeito de São Paulo à Câmara Municipal | igual ao comum; fonte: SPLegis da Câmara de São Paulo (webservice); arquivos `prefeitura_2025` e `prefeitura_2026` | mostrado no site |

## TO: Tocantins

### Eleições (TSE)

| Dado | Fonte | Status |
|---|---|---|
| Eleitos (candidatura, bens, votos) | anos com arquivo: 2018, 2022, 2024, 2026; igual ao comum; 2022 e 2026 trazem deputado estadual | mostrado no site |
| Prestação de contas | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votação por seção | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Disputa (comparecimento e vagas) | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Votos por partido | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Coligações | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |
| Eleitorado | igual ao comum; anos com arquivo: 2022, 2024 | mostrado no site |

### Câmara dos Deputados

| Dado | Fonte | Status |
|---|---|---|
| Bancada federal do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Senado

| Dado | Fonte | Status |
|---|---|---|
| Senadores do estado e seus dados | igual ao comum (filtro por `uf`) | mostrado no site |

### Assembleia Legislativa

Módulo: `scripts/coletar_estaduais.py` (SAPL), dados em `dados/estaduais/TO/`. A lista de deputados do SAPL não traz partido (vem do TSE).

| Dado | Fonte | Status |
|---|---|---|
| Deputados | igual ao comum; 26 deputados; host `sapl.al.to.leg.br` | mostrado no site |
| Projetos (autoria) | igual ao comum; matérias por ano: 2023: 589, 2024: 394, 2025: 542, 2026: 252 | mostrado no site |
| Votações nominais | coletor roda, mas não achou votações nominais (arquivo `votacoes.json` vazio); a ficha do deputado fica sem votos | mostrado no site |
| Presença, cota/verba, remuneração | pendentes (ver `LEVANTAMENTO_DADOS.md`) | disponível na fonte, não coletado |

### Governo do estado

| Dado | Fonte | Status |
|---|---|---|
| Projetos, vetos e mensagens do governador à Assembleia | coletor roda, mas não achou matérias do governador no SAPL (arquivos `governo_<ano>.json` vazios); sem dados, a página cai no texto padrão | mostrado no site |

### Prefeitura da capital

sem coletor para Palmas: Palmas: sem dados atuais (ver `dados/municipais/capitais_sem_dados.md`).

## Coletado e não usado no site

Itens que já estão em `dados/` e que `site/assets/app.js` não exibe. A lista vem do status `coletado, não usado no site` dos blocos acima.

| Origem | Arquivo bruto | Campo | Observação |
|---|---|---|---|
| Câmara | `dados/deputados/<id>.json` | `coletadoEm` | data da coleta do deputado |
| Câmara | `dados/proposicoes_detalhe.json` | `ementaDetalhada` | copiada para `site/dados/deputado/<id>.json`, sem tela |
| Câmara | `dados/proposicoes_detalhe.json` | `finalizada`, `consultadoEm` | controle do cache de consultas; não saem para o site |
| Câmara | `dados/votacoes/<ano>.json` | `orgao` | órgão da votação; não entra no resumo do site |
| Câmara | `site/dados/deputado/<id>.json` | `despesas.porMes` | soma da cota por mês, gerada e não lida |
| Senado | `dados/senado_votacoes/<ano>.json` | `processo` | id do processo da votação |
| Senado | `dados/senado_materias.json` | arquivo todo (`situacao`, `dataSituacao`, `dataApresentacao`, `processo`) | só alimenta o resumo diário da página Histórico |
| Assembleias | `dados/estaduais/<UF>/deputados.json` | `legislatura` | número da legislatura |
| Assembleias | `dados/estaduais/<UF>/materias_<ano>.json` | `idsAutores`, `emTramitacao` | `emTramitacao` chega a `site/dados/estadual/<UF>/<id>.json` e não é exibido |
| Governos | `dados/estaduais/<UF>/governo_<ano>.json` | `idsAutores`, `emTramitacao` | só os campos de `gerar_governo` chegam ao site |
| Prefeituras | `dados/municipais/<UF>/prefeitura_<ano>.json` | `coletadoEm`, `idsAutores`, `emTramitacao` | em SP também `enviados` e `vistos` (controle da coleta) |
| Assembleias | `dados/estaduais/CE/verbas_2022.json`; `emendas_2017..2022.json` (BA) | arquivos de anos anteriores a 2023 | `gerar_estaduais.py` só lê anos a partir de 2023 pelo nome do arquivo |
| Assembleias | `dados/estaduais/CE/verbas_<ano>.json`, `diarias_<ano>.json` | `empenho`, `descricao` | extras além do contrato |
| Assembleias | `dados/estaduais/MS/verbas_<ano>.json` | `documento`, `emissao` | extras além do contrato; o comprovante em PDF vai como `fonte` |
| Assembleias | `dados/estaduais/PA/verbas_<ano>.json`, `diarias_<ano>.json` | `data`, `descricao`, `assessores` (verba); `categoria` e destino/motivo em texto livre (diárias) | o resumo de diárias do site só traz total e quantidade por ano |
| Assembleias | `dados/estaduais/SC/verbas_<ano>.json`, `diarias_<ano>.json`, `deputados.json`, `presenca.json` | `data`, `trecho`; `quantidade`; `nomeFonte`; chave `sessoes` | `sessoes` guarda o cache por sessão lida |
| Assembleias | `dados/estaduais/RJ/emendas_<ano>.json` | `numero`, `beneficiario`, `municipio`, `valor` | o resumo de emendas do site só traz empenhado, pago e quantidade por ano |
| Assembleias | `dados/estaduais/RR/verbas_<ano>.json`, `diarias_<ano>.json` | `item`, `grupo`, `mesesColetados`, `dataFim` | extras além do contrato |
| Assembleias | `dados/estaduais/RS/diarias_<ano>.json` | `dataFim`, `tipo`, `origem`, `empenho` | extras além do contrato |
| Assembleias | `dados/estaduais/MT/remuneracao_<ano>.json`, `diarias_<ano>.json` | `folha`; `dataFim`, `passagem`, `quantidade`, `anulado`, `situacao`, `empenho` | o resumo de remuneração do site usa só o último mês |
| TSE | `dados/tse/eleitorado/2022/ZZ.json`, `dados/tse/disputa/2022/ZZ.json` | eleitorado e disputa do exterior | nenhuma página de estado usa a chave ZZ |
| TSE | `dados/tse_bruto/motivo_cassacao/motivo_cassacao_2022.zip` e `_2024.zip` | motivos de indeferimento de candidatura | baixados por `baixar_tse.py`, sem coletor, fora do git |

## Comparação entre estados

Resumo das seções de Assembleia dos 27 estados, fechado em 2026-10-22 com os coletores de GO, MG, MS, MT, PA, PE, PR, RJ, RN, RR, RS, SC, SE, SP, BA e CE. Objetivo: todos os estados com, no mínimo, a base de dados necessária (ver "Base mínima").

### Matriz UF × dado da Assembleia

Legenda: ✅ coletado e mostrado no site; ◐ coletado e não mostrado; ○ disponível na fonte e não coletado (inclui o que ainda não foi investigado); ✖ bloqueado ou inexistente. Partido e foto valem para o dado da Assembleia (nos estados do SAPL o partido vem só do TSE). Em RJ, RS, MS e MT a lista de deputados vem do TSE ou do portal de transparência. O site mostra tudo o que é coletado a partir de 2023 (`gerar_estaduais.py`), por isso não há ◐ nesta matriz; os campos coletados e não usados estão em "Coletado e não usado no site".

| UF | Deputados | Partido | Foto | Projetos (autoria) | Votações nominais | Presença | Verba/cota | Fornecedores | Remuneração | Diárias | Emendas |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AC | ✅ | ○ | ✅ | ✅ | ✅ | ○ | ○ | ○ | ○ | ○ | ○ |
| AL | ✅ | ○ | ✅ | ✅ | ✖ | ○ | ○ | ○ | ○ | ○ | ○ |
| AM | ✅ | ○ | ✅ | ✅ | ✅ | ○ | ○ | ○ | ○ | ○ | ○ |
| AP | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ |
| BA | ✅ | ✅ | ✅ | ✅ | ✖ | ✖ | ✅ | ○ | ○ | ✖ | ✅ |
| CE | ✅ | ✅ | ✅ | ✅ | ✅ | ✖ | ✅ | ✅ | ✅ | ✅ | ○ |
| DF | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ |
| ES | ✖ | ✖ | ✖ | ○ | ✖ | ○ | ✖ | ✖ | ○ | ○ | ✖ |
| GO | ✅ | ✅ | ✅ | ✅ | ✅ | ○ | ✅ | ✖ | ✅ | ✅ | ✖ |
| MA | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ |
| MG | ✅ | ✅ | ○ | ✅ | ✖ | ✖ | ✅ | ✅ | ✖ | ✖ | ✖ |
| MS | ✅ | ✅ | ✖ | ✖ | ✖ | ✖ | ✅ | ✅ | ○ | ✖ | ✖ |
| MT | ✅ | ✅ | ○ | ○ | ○ | ○ | ✖ | ✖ | ✅ | ✅ | ✖ |
| PA | ✅ | ✅ | ✅ | ✖ | ✖ | ✅ | ✅ | ✖ | ○ | ✅ | ○ |
| PB | ✅ | ○ | ✅ | ✅ | ✅ | ○ | ○ | ○ | ○ | ○ | ○ |
| PE | ✅ | ✅ | ✅ | ✅ | ✖ | ✖ | ✅ | ✅ | ○ | ✖ | ○ |
| PI | ✅ | ○ | ✅ | ✅ | ✅ | ○ | ○ | ○ | ○ | ○ | ○ |
| PR | ✅ | ✅ | ✅ | ✅ | ○ | ✅ | ✖ | ✖ | ✅ | ✅ | ○ |
| RJ | ✅ | ✅ | ✖ | ○ | ○ | ✅ | ○ | ○ | ✖ | ○ | ✅ |
| RN | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✖ | ✖ | ✖ | ✖ | ✖ |
| RO | ✅ | ○ | ✅ | ✅ | ✅ | ○ | ○ | ○ | ○ | ○ | ○ |
| RR | ✅ | ✅ | ✅ | ✖ | ✖ | ✖ | ✅ | ✖ | ✖ | ✅ | ✖ |
| RS | ✅ | ✅ | ○ | ○ | ○ | ○ | ✖ | ✖ | ○ | ✅ | ○ |
| SC | ✅ | ✅ | ✖ | ○ | ○ | ✅ | ✅ | ✅ | ✅ | ✅ | ○ |
| SE | ✅ | ✅ | ✅ | ✖ | ✖ | ✖ | ○ | ○ | ○ | ○ | ○ |
| SP | ✅ | ✅ | ✅ | ✅ | ○ | ✅ | ✅ | ✅ | ✅ | ✖ | ✖ |
| TO | ✅ | ○ | ✅ | ✅ | ✖ | ○ | ○ | ○ | ○ | ○ | ○ |

Lacunas das células (○ e ✖) estão nos tópicos de cada UF; o motivo e o próximo passo de cada falta da base mínima estão abaixo.

### Dados que faltam por estado

Só a base mínima (as colunas da matriz que a definem). Um estado que também não tem os dados extras (fornecedores, diárias, emendas) está na matriz.

| UF | O que falta da base mínima | Próximo passo |
|---|---|---|
| AC | Partido, Presença, Verba/cota, Remuneração | Partido: usar o partido do TSE na ficha (já ligado) ou ler a ficha do SAPL; Presença: portal de transparência da Assembleia (não investigado); se não houver dado aberto, LAI/e-SIC; Verba/cota: portal de transparência (não investigado); LAI/e-SIC; Remuneração: portal de transparência (não investigado); LAI/e-SIC |
| AL | Partido, Votações nominais, Presença, Verba/cota, Remuneração | Partido: usar o partido do TSE na ficha (já ligado) ou ler a ficha do SAPL; Votações nominais: o SAPL não registra votos nominais (arquivo vazio); conferir a ata das sessões ou pedir por LAI/e-SIC; Presença: portal de transparência da Assembleia (não investigado); se não houver dado aberto, LAI/e-SIC; Verba/cota: portal de transparência (não investigado); LAI/e-SIC; Remuneração: portal de transparência (não investigado); LAI/e-SIC |
| AM | Partido, Presença, Verba/cota, Remuneração | Partido: usar o partido do TSE na ficha (já ligado) ou ler a ficha do SAPL; Presença: portal de transparência da Assembleia (não investigado); se não houver dado aberto, LAI/e-SIC; Verba/cota: portal de transparência (não investigado); LAI/e-SIC; Remuneração: portal de transparência (não investigado); LAI/e-SIC |
| AP | Deputados, Partido, Foto, Projetos (autoria), Votações nominais, Presença, Verba/cota, Remuneração | Deputados: nova tentativa de uma rede sem bloqueio (ou Actions); se o site seguir fora, LAI/e-SIC; Partido: nova tentativa de uma rede sem bloqueio (ou Actions); se o site seguir fora, LAI/e-SIC; Foto: nova tentativa de uma rede sem bloqueio (ou Actions); se o site seguir fora, LAI/e-SIC; Projetos (autoria): nova tentativa de uma rede sem bloqueio (ou Actions); se o site seguir fora, LAI/e-SIC; Votações nominais: nova tentativa de uma rede sem bloqueio (ou Actions); se o site seguir fora, LAI/e-SIC; Presença: nova tentativa de uma rede sem bloqueio (ou Actions); se o site seguir fora, LAI/e-SIC; Verba/cota: nova tentativa de uma rede sem bloqueio (ou Actions); se o site seguir fora, LAI/e-SIC; Remuneração: nova tentativa de uma rede sem bloqueio (ou Actions); se o site seguir fora, LAI/e-SIC |
| BA | Votações nominais, Presença, Remuneração | Votações nominais: NoPaper bloqueia (403 Cloudflare): tentar o Firefox do usuário; senão LAI/e-SIC; Presença: NoPaper bloqueia: mesmo caminho das votações; senão LAI/e-SIC; Remuneração: só existe PDF `ALBA_ECV_Deputados.pdf`: ler o PDF ou pedir CSV por LAI/e-SIC |
| CE | Presença | Presença: a Assembleia não publica presença em plenário: LAI/e-SIC |
| DF | Deputados, Partido, Foto, Projetos (autoria), Votações nominais, Presença, Verba/cota, Remuneração | Deputados: nova tentativa de uma rede sem bloqueio (ou Actions); a CLDF não usa SAPL em `sapl.cl.df.gov.br`; se o site seguir fora, LAI/e-SIC; Partido: nova tentativa de uma rede sem bloqueio (ou Actions); a CLDF não usa SAPL em `sapl.cl.df.gov.br`; se o site seguir fora, LAI/e-SIC; Foto: nova tentativa de uma rede sem bloqueio (ou Actions); a CLDF não usa SAPL em `sapl.cl.df.gov.br`; se o site seguir fora, LAI/e-SIC; Projetos (autoria): nova tentativa de uma rede sem bloqueio (ou Actions); a CLDF não usa SAPL em `sapl.cl.df.gov.br`; se o site seguir fora, LAI/e-SIC; Votações nominais: nova tentativa de uma rede sem bloqueio (ou Actions); a CLDF não usa SAPL em `sapl.cl.df.gov.br`; se o site seguir fora, LAI/e-SIC; Presença: nova tentativa de uma rede sem bloqueio (ou Actions); a CLDF não usa SAPL em `sapl.cl.df.gov.br`; se o site seguir fora, LAI/e-SIC; Verba/cota: nova tentativa de uma rede sem bloqueio (ou Actions); a CLDF não usa SAPL em `sapl.cl.df.gov.br`; se o site seguir fora, LAI/e-SIC; Remuneração: nova tentativa de uma rede sem bloqueio (ou Actions); a CLDF não usa SAPL em `sapl.cl.df.gov.br`; se o site seguir fora, LAI/e-SIC |
| ES | Deputados, Partido, Foto, Projetos (autoria), Votações nominais, Presença, Verba/cota, Remuneração | Deputados: nova tentativa de uma rede sem bloqueio (ou Actions); Partido: nova tentativa de uma rede sem bloqueio (ou Actions); Foto: nova tentativa de uma rede sem bloqueio (ou Actions); Projetos (autoria): nova tentativa de uma rede sem bloqueio (ou Actions); Votações nominais: nova tentativa; pelo ITGP a Assembleia não publica votação nominal: LAI/e-SIC; Presença: nova tentativa de uma rede sem bloqueio (ou Actions); Verba/cota: nova tentativa; pelo ITGP a Assembleia não publica verba indenizatória: LAI/e-SIC; Remuneração: nova tentativa de uma rede sem bloqueio (ou Actions) |
| GO | Presença | Presença: a API só traz datas e pauta; pedir a lista de presença por LAI/e-SIC |
| MA | Deputados, Partido, Foto, Projetos (autoria), Votações nominais, Presença, Verba/cota, Remuneração | Deputados: nova tentativa de uma rede sem bloqueio (ou Actions); se o site seguir fora, LAI/e-SIC; Partido: nova tentativa de uma rede sem bloqueio (ou Actions); se o site seguir fora, LAI/e-SIC; Foto: nova tentativa de uma rede sem bloqueio (ou Actions); se o site seguir fora, LAI/e-SIC; Projetos (autoria): nova tentativa de uma rede sem bloqueio (ou Actions); se o site seguir fora, LAI/e-SIC; Votações nominais: nova tentativa de uma rede sem bloqueio (ou Actions); se o site seguir fora, LAI/e-SIC; Presença: nova tentativa de uma rede sem bloqueio (ou Actions); se o site seguir fora, LAI/e-SIC; Verba/cota: nova tentativa de uma rede sem bloqueio (ou Actions); se o site seguir fora, LAI/e-SIC; Remuneração: nova tentativa de uma rede sem bloqueio (ou Actions); se o site seguir fora, LAI/e-SIC |
| MG | Foto, Votações nominais, Presença, Remuneração | Foto: usar a foto do TSE (já no site) ou montar a URL do portal da ALMG; Votações nominais: o Swagger não tem rota: LAI/e-SIC (ou ler as atas de plenário); Presença: sem rota na API: LAI/e-SIC; Remuneração: a ALMG não publica remuneração nominal na API: LAI/e-SIC |
| MS | Foto, Projetos (autoria), Votações nominais, Presença, Remuneração | Foto: foto da ficha do site da ALEMS (HTML dinâmico); testar o Firefox; Projetos (autoria): SGPL bloqueia por captcha: tentar o Firefox, senão LAI/e-SIC; Votações nominais: SGPL bloqueia por captcha: mesmo caminho; senão LAI/e-SIC; Presença: não encontrada: LAI/e-SIC; Remuneração: só PDF mensal: ler os PDFs ou pedir CSV por LAI/e-SIC |
| MT | Foto, Projetos (autoria), Votações nominais, Presença, Verba/cota | Foto: `www.al.mt.gov.br` não responde desta rede: nova tentativa; Projetos (autoria): `www.al.mt.gov.br` não responde desta rede: nova tentativa ou Firefox; senão LAI/e-SIC; Votações nominais: mesmo caminho dos projetos; senão LAI/e-SIC; Presença: mesmo caminho dos projetos; senão LAI/e-SIC; Verba/cota: as rotas de verbas e cotas do Elotech vêm vazias: LAI/e-SIC |
| PA | Projetos (autoria), Votações nominais, Remuneração | Projetos (autoria): o Banco de Leis só tem leis: procurar outra fonte (sistema legislativo da ALEPA) ou LAI/e-SIC; Votações nominais: não existe na transparência: LAI/e-SIC; Remuneração: só PDF de reajustes: LAI/e-SIC |
| PB | Partido, Presença, Verba/cota, Remuneração | Partido: usar o partido do TSE na ficha (já ligado) ou ler a ficha do SAPL; Presença: portal de transparência da Assembleia (não investigado); se não houver dado aberto, LAI/e-SIC; Verba/cota: portal de transparência (não investigado); LAI/e-SIC; Remuneração: portal de transparência (não investigado); LAI/e-SIC |
| PE | Votações nominais, Presença, Remuneração | Votações nominais: `legis.alepe.pe.gov.br` exige login: LAI/e-SIC; Presença: idem: LAI/e-SIC; Remuneração: a API `remuneracao` é por cargo: LAI/e-SIC |
| PI | Partido, Presença, Verba/cota, Remuneração | Partido: usar o partido do TSE na ficha (já ligado) ou ler a ficha do SAPL; Presença: portal de transparência da Assembleia (não investigado); se não houver dado aberto, LAI/e-SIC; Verba/cota: portal de transparência (não investigado); LAI/e-SIC; Remuneração: portal de transparência (não investigado); LAI/e-SIC |
| PR | Votações nominais, Verba/cota | Votações nominais: só PDF por sessão: extrair o texto dos PDFs (nova tentativa); Verba/cota: o ressarcimento exige reCAPTCHA: tentar o Firefox, senão LAI/e-SIC |
| RJ | Foto, Projetos (autoria), Votações nominais, Verba/cota, Remuneração | Foto: não existe na fonte lida: foto do TSE ou ficha do site da ALERJ; Projetos (autoria): explorar o Lotus Notes `alerjln1` além da presença; senão LAI/e-SIC; Votações nominais: idem; senão LAI/e-SIC; Verba/cota: DOCIGP (`docigp.alerj.rj.gov.br/transparencia`) por login e consulta: explorar; senão LAI/e-SIC; Remuneração: a página de subsídio não tem arquivo: LAI/e-SIC |
| RN | Verba/cota, Remuneração | Verba/cota: API do portal exige token embutido no JS; só com autorização do usuário, senão LAI/e-SIC; Remuneração: não encontrada: LAI/e-SIC |
| RO | Partido, Presença, Verba/cota, Remuneração | Partido: usar o partido do TSE na ficha (já ligado) ou ler a ficha do SAPL; Presença: portal de transparência da Assembleia (não investigado); se não houver dado aberto, LAI/e-SIC; Verba/cota: portal de transparência (não investigado); LAI/e-SIC; Remuneração: portal de transparência (não investigado); LAI/e-SIC |
| RR | Projetos (autoria), Votações nominais, Presença, Remuneração | Projetos (autoria): `sapl.al.rr.leg.br` responde 403: tentar o Firefox do usuário; senão LAI/e-SIC; Votações nominais: idem; Presença: idem; Remuneração: só planilha de servidores sem remuneração: LAI/e-SIC |
| RS | Foto, Projetos (autoria), Votações nominais, Presença, Verba/cota, Remuneração | Foto: `www.al.rs.gov.br` sem resposta: nova tentativa ou Firefox; Projetos (autoria): mesmo caminho da foto; senão LAI/e-SIC; Votações nominais: mesmo caminho da foto; senão LAI/e-SIC; Presença: mesmo caminho da foto; senão LAI/e-SIC; Verba/cota: não achada no portal do Estado nem no CKAN: LAI/e-SIC; Remuneração: abrir a folha estadual do CKAN e filtrar deputados; senão LAI/e-SIC |
| SC | Foto, Projetos (autoria), Votações nominais | Foto: não existe na fonte lida: foto do TSE ou ficha do e-Legis; Projetos (autoria): e-Legis sem exportação: raspar `/proposicoes/atividade-parlamentar` (um documento por proposição); Votações nominais: extrato de votação por Ajax no e-Legis: raspar |
| SE | Projetos (autoria), Votações nominais, Presença, Verba/cota, Remuneração | Projetos (autoria): Alese Legis sem resposta: nova tentativa ou Firefox; senão LAI/e-SIC; Votações nominais: o ITGP diz que não publica: LAI/e-SIC; Presença: o ITGP diz que não publica: LAI/e-SIC; Verba/cota: só PDF mensal: extrair o texto dos PDFs ou LAI/e-SIC; Remuneração: só PDF: extrair o texto dos PDFs ou LAI/e-SIC |
| SP | Votações nominais | Votações nominais: só PDF por sessão: extrair o texto dos PDFs (nova tentativa) |
| TO | Partido, Votações nominais, Presença, Verba/cota, Remuneração | Partido: usar o partido do TSE na ficha (já ligado) ou ler a ficha do SAPL; Votações nominais: o SAPL não registra votos nominais (arquivo vazio); conferir a ata das sessões ou pedir por LAI/e-SIC; Presença: portal de transparência da Assembleia (não investigado); se não houver dado aberto, LAI/e-SIC; Verba/cota: portal de transparência (não investigado); LAI/e-SIC; Remuneração: portal de transparência (não investigado); LAI/e-SIC |

### Dados que só alguns estados têm

Dados coletados em 1 a 3 UFs, mais alguns extras que só uma ou duas Assembleias publicam.

| Dado | UFs | Observação |
|---|---|---|
| Fornecedor com CNPJ na verba | CE, MG, MS, PE, SP | 5 UFs (SC traz o favorecido sem CNPJ; BA tem o CNPJ só na página de cada lançamento) |
| Presença em sessões plenárias | PA, PR, RJ, RN, SC, SP | 6 UFs |
| Verba de gabinete (pessoal): total mensal e nº de assessores | PA | só jun a set/2026 |
| Comprovante da despesa em PDF por item | MS, RR | `fonte` aponta para o PDF da nota (MS) ou do mês (RR) |
| Votos secretos (só o placar) | RN | demais UFs só têm voto nominal |
| Remuneração com 13º em linha própria (`folha`) | MT | demais UFs não separam a folha |
| Emendas por deputado | BA, RJ | BA: despesas por deputado e ano do CKAN; RJ: emendas impositivas 2025-2026 |
| Dados em UF sem Assembleia coletada (só TSE) | AP, DF, ES, MA | sites fora do ar nesta rede |

### Base mínima

Definição: para cada Assembleia, (1) deputados com partido e foto, (2) projetos com autoria, (3) votações nominais, (4) presença, (5) verba ou cota e (6) remuneração. É a lista de oito colunas da matriz (deputados, partido, foto, projetos, votações, presença, verba, remuneração).

Estados que já atingem a base mínima: nenhum.

Situação por UF (itens da base que faltam, de 8):

| UF | Itens que faltam | Total |
|---|---|---|
| AC | Partido, Presença, Verba/cota, Remuneração | 4 |
| AL | Partido, Votações nominais, Presença, Verba/cota, Remuneração | 5 |
| AM | Partido, Presença, Verba/cota, Remuneração | 4 |
| AP | Deputados, Partido, Foto, Projetos (autoria), Votações nominais, Presença, Verba/cota, Remuneração | 8 |
| BA | Votações nominais, Presença, Remuneração | 3 |
| CE | Presença | 1 |
| DF | Deputados, Partido, Foto, Projetos (autoria), Votações nominais, Presença, Verba/cota, Remuneração | 8 |
| ES | Deputados, Partido, Foto, Projetos (autoria), Votações nominais, Presença, Verba/cota, Remuneração | 8 |
| GO | Presença | 1 |
| MA | Deputados, Partido, Foto, Projetos (autoria), Votações nominais, Presença, Verba/cota, Remuneração | 8 |
| MG | Foto, Votações nominais, Presença, Remuneração | 4 |
| MS | Foto, Projetos (autoria), Votações nominais, Presença, Remuneração | 5 |
| MT | Foto, Projetos (autoria), Votações nominais, Presença, Verba/cota | 5 |
| PA | Projetos (autoria), Votações nominais, Remuneração | 3 |
| PB | Partido, Presença, Verba/cota, Remuneração | 4 |
| PE | Votações nominais, Presença, Remuneração | 3 |
| PI | Partido, Presença, Verba/cota, Remuneração | 4 |
| PR | Votações nominais, Verba/cota | 2 |
| RJ | Foto, Projetos (autoria), Votações nominais, Verba/cota, Remuneração | 5 |
| RN | Verba/cota, Remuneração | 2 |
| RO | Partido, Presença, Verba/cota, Remuneração | 4 |
| RR | Projetos (autoria), Votações nominais, Presença, Remuneração | 4 |
| RS | Foto, Projetos (autoria), Votações nominais, Presença, Verba/cota, Remuneração | 6 |
| SC | Foto, Projetos (autoria), Votações nominais | 3 |
| SE | Projetos (autoria), Votações nominais, Presença, Verba/cota, Remuneração | 5 |
| SP | Votações nominais | 1 |
| TO | Partido, Votações nominais, Presença, Verba/cota, Remuneração | 5 |

Resumo por tipo de lacuna e próximo passo:

- **Rede bloqueada ou site fora do ar** (AP, DF, ES, MA; parte de MT, RS, SE, RR, BA, MS): nova tentativa de uma rede sem bloqueio (Actions ou o navegador do usuário). Se abrir, reexecutar o grupo da UF.
- **Dado só em PDF** (SE, PA, MS, BA, PR votações, SP votações): extrair o texto dos PDFs ou pedir a planilha por LAI/e-SIC.
- **Dado que a Assembleia não publica** (votações e presença em MG, PE, SE, CE, PA; remuneração em MG, PE, RR, RJ): pedir por LAI/e-SIC; sem resposta, aceitar a lacuna.
- **Captcha, login ou token** (MS SGPL, PR ressarcimento, PE `legis`, RN cotas, RJ DOCIGP): tentar o Firefox; credencial embutida no JS não é dado aberto e só entra com autorização do usuário.
- **Fonte aberta ainda não coletada** (partido nos estados do SAPL, presença e verba nas UFs do SAPL, projetos e votações de SC, RJ via Lotus Notes, folha do RS): próximo coletor, por ordem de ganho: SAPL (7 UFs de uma vez, se os portais de transparência derem arquivos), SC (e-Legis), RS (CKAN).
