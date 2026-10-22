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

sem coletor (ver `LEVANTAMENTO_DADOS.md`)

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

sem coletor (ver `LEVANTAMENTO_DADOS.md`)

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

sem coletor (ver `LEVANTAMENTO_DADOS.md`)

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

sem coletor (ver `LEVANTAMENTO_DADOS.md`)

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

sem coletor (ver `LEVANTAMENTO_DADOS.md`)

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

sem coletor (ver `LEVANTAMENTO_DADOS.md`)

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

sem coletor (ver `LEVANTAMENTO_DADOS.md`)

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

sem coletor (ver `LEVANTAMENTO_DADOS.md`)

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

sem coletor (ver `LEVANTAMENTO_DADOS.md`)

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

sem coletor (ver `LEVANTAMENTO_DADOS.md`)

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

sem coletor (ver `LEVANTAMENTO_DADOS.md`)

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

sem coletor (ver `LEVANTAMENTO_DADOS.md`)

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

sem coletor (ver `LEVANTAMENTO_DADOS.md`)

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

sem coletor (ver `LEVANTAMENTO_DADOS.md`)

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

sem coletor (ver `LEVANTAMENTO_DADOS.md`)

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

sem coletor (ver `LEVANTAMENTO_DADOS.md`)

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

sem coletor (ver `LEVANTAMENTO_DADOS.md`)

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

sem coletor (ver `LEVANTAMENTO_DADOS.md`)

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

sem coletor (ver `LEVANTAMENTO_DADOS.md`)

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

sem coletor (ver `LEVANTAMENTO_DADOS.md`)

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
| TSE | `dados/tse/eleitorado/2022/ZZ.json`, `dados/tse/disputa/2022/ZZ.json` | eleitorado e disputa do exterior | nenhuma página de estado usa a chave ZZ |
| TSE | `dados/tse_bruto/motivo_cassacao/motivo_cassacao_2022.zip` e `_2024.zip` | motivos de indeferimento de candidatura | baixados por `baixar_tse.py`, sem coletor, fora do git |

## Comparação entre estados

(preenchido ao final do plano)
