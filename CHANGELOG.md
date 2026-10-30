# CHANGELOG dos dados

Registro de **quando** cada conjunto de dados entrou no projeto, **de onde** vem (URL) e **como** foi baixado.
Regra: toda fonte nova ou mudança de coleta ganha uma entrada aqui, no mesmo commit.
Datas dos conjuntos que já existiam vêm do primeiro commit que os trouxe (`git log --diff-filter=A`).
Todas as coletas rodam sozinhas no GitHub Actions (`.github/workflows/atualizar.yml`, todo dia às 05:00 de Brasília), salvo onde indicado.

## Emendas parlamentares federais (2026-10-30)
- **De onde:** API do Portal da Transparência, `https://api.portaldatransparencia.gov.br/api-de-dados/emendas` (`portal_transparencia_emendas` em `ENDPOINTS.md`), com chave gratuita no cabeçalho `chave-api-dados` (secret `PORTAL_TRANSPARENCIA_CHAVE`; sem ela o coletor avisa e pula).
- **Como:** `scripts/coletar_emendas.py`, job `emendas` do `atualizar.yml`. Pagina por `ano` e `pagina` (a API devolve lista vazia ao fim), de 2019 em diante; grava `dados/emendas/<ano>.json` (autor como veio, local do gasto com município e UF, função, subfunção, empenhado, liquidado e pago). Anos encerrados vêm do git e não são baixados de novo; o ano passado e o corrente são relidos. Pausa de 0,7 s por página. Tempo da coleta e formato dos campos ainda **não medidos contra a API real** (a chave só existe no Actions): conferir a primeira execução e regravar o teste com amostra real.
- **Ligação e site:** `identidades.ligar_emendas` liga o autor à pessoa que foi parlamentar federal e tem o nome (`nome+cargo`, média; nome repetido não liga, bancada e comissão ficam sem pessoa). `gerar_emendas.py` grava `site/dados/emendas/<pessoa>.json` (totais por ano, todos os municípios de destino com código IBGE e valores, e a lista); `emendas.js` mostra o painel na ficha de deputado, senador e demais. `site/mapa-dados.html` e `site/sobre.html` atualizados.
- **Mapa dos destinos e Emendas Pix:** nenhuma fonte nova. O painel ganha o mapa dos municípios (malha do IBGE em `site/geo/`, um estado por vez, cor pelo valor empenhado) e resumo das emendas Pix (tipo "Transferências Especiais" do mesmo endpoint), com filtro "Só Emendas Pix". O município da emenda liga ao código IBGE por UF + nome (`gerar_emendas.py`, com `dados/municipios_nomes.json`, gerado offline por `gerar_municipios_ibge.py --nomes` a partir dos nomes do TSE e dos mesmos `AJUSTES` de grafia). DF não tem malha municipal. O job `publicar` do `atualizar.yml` passa a rodar `scripts/baixar_malhas.py` (IBGE, `https://servicodados.ibge.gov.br/api/v3/malhas`) antes do `gerar.py`, para as malhas irem em `site/geo/` no deploy (não são commitadas; falha não impede a publicação).

## Coleta da Câmara mais rápida: cache da ficha e leitura incremental (2026-10-30)

O passo "Coletar deputados da Câmara" passou de ~20 min para mais de 22 depois que a ficha ganhou `discursosResumo` e `eventos` (paginam a legislatura inteira de cada deputado). Como `dados/deputados/` não vai para o git, todo dia partia do zero e o escalonamento de complementos (`1 + id % 7` dias) nunca valia no Actions.

- `atualizar.yml`: o job da Câmara restaura `dados/deputados/` com `actions/cache` (chave por execução, `restore-keys` pega a última).
- `coletar.py`: `discursosResumo` e `eventos` leem só desde o corte guardado em `leituraIncremental` (contagem do que é mais antigo que `JANELA_INCREMENTAL` = 7 dias) e somam; releitura completa a cada `RENOVAR_COMPLETA_DIAS` = 14. Não há endpoint novo.
- A primeira execução depois disto ainda é completa (cache vazio); as seguintes não.

## Ministros no histórico, no RSS e no e-mail (2026-10-30)
- **Sem fonte nova.** `ministros_mudancas.py` decide as novidades (troca na lista do Planalto, pedido novo, resposta, prazo vencido, convocação aprovada) e é usado pelo histórico diário, pelo e-mail e pelo RSS, que dizem a mesma coisa. No histórico tudo fica na categoria `ministro` ("Ministros e ministérios"); o ministro da pasta entra em `politicos` (`codigo: min:<pasta>`, nome e cargo), então o filtro por político da página funciona. Dias já gravados não são reescritos.
- **Fique informado:** `gerar_ministros.py` grava `site/dados/indice/MIN.json` (o ministro atual de cada pasta, `codigoFeed: min:<pasta>`). O card 2 ganha "Ministros e ministérios" em "Onde atua"; o feed e o e-mail seguem a pasta (continuam valendo quando o ministro troca). `assinaturas.py` aceita o código `min:<pasta>`.
- **E-mail e RSS:** seção "Ministros — N novidades", com "Fulano, Ministro de Estado da Saúde — RIC 3/2026: …". Entra nos feeds `BR`, `FEDERAL` e `min:<pasta>`.

## Ficha da proposição: ementa inteira, mais dados e leis citadas (2026-10-30)
- **De onde:** a ementa inteira já vinha da API da Câmara; o corte em 180 caracteres era só do índice `proposicoes.json`. Os campos novos (ementa detalhada, palavras-chave, regime, última tramitação, link do inteiro teor, projeto principal) vêm de `proposicoes_detalhe.json` e os temas, de `proposicoes_temas.json`. Fonte nova: LexML (`lexml_norma` em `ENDPOINTS.md`), página `https://www.lexml.gov.br/urn/urn:lex:br:federal:...` de cada lei citada, para a ementa oficial e o link do Planalto.
- **Como:** `leis.py` acha as citações com data completa (lei, lei complementar, decreto-lei, decreto, MP, emenda e Constituição) e monta a URN; `coletar_leis.py` grava `dados/leis.json` (só consulta lei nova; 400 por execução, pausa de 0,5 s). `gerar_proposicoes.py` grava `em`, `ed`, `pc`, `rg`, `tr`, `ds`, `tx`, `pr`, `tm`, `ls` na ficha e `site/dados/leis.json`. Citação sem data ("Lei nº 8.080/90") não liga, para não apontar a lei errada. Tempo da coleta não medido (sem internet para o LexML no teste local além de uma página).

## O que cada ministério faz (2026-10-30)
- **De onde:** texto da Lei 14.600/2023 (versão original, lida no portal da Câmara porque o Planalto bloqueia a coleta automática) e da Lei 14.816/2024 (Ministério do Empreendedorismo). Sem endpoint novo: os links da página são só links.
- **Como:** sem coletor. Escrito à mão em `scripts/ministerios_descricao.json` (resumo, áreas, site, base legal e data de revisão por chave de `ministerios.PASTAS`); `gerar_ministros.py` grava `descricao` em `ministerio/<pasta>.json` e avisa quando falta pasta. A página do ministério mostra o bloco "O que faz" e a do ministro, o resumo da pasta. Pendências (vinculados das 28 pastas restantes e alterações legais após 2024): `FUTURAS_IMPLEMENTACOES.md`, pacote 3.4.
- **Vinculados:** `vinculados` (nome e link) entrou em 10 pastas (Cidades, Comunicações, Cultura, Defesa, MDIC, Integração, Meio Ambiente, Previdência, Saúde, Trabalho), copiados da página "órgãos/entidades vinculadas" do próprio ministério em gov.br, que vira item de `base`. As demais ficam sem a lista (Minas e Energia tem página, mas com 2 itens e sem as agências) até haver página limpa ou conferência no decreto de estrutura.

## Posse e presidente que nomeou cada ministro (2026-10-29)
- **De onde:** Wikipédia em português (`wikipedia_ministros` em `ENDPOINTS.md`), página mais atualizada de cada pasta (`Lista de ministros ... do Brasil`, ou o artigo do ministério ou da pessoa quando a lista não existe ou está parada, como a de Pesca). Fonte secundária: o Planalto e o DOU não publicam essa data de forma consultável.
- **Como:** sem coletor, de propósito (o dado não muda). Anotado à mão em `scripts/ministros_posse.json` (`pasta`, `nome` como no Planalto, `posse`, `nomeadoPor`, `fonte` com a página usada); `identidades.ligar_ministros` aplica ao ministro atual (`inicioFonte: "wikipedia"`, `nomeadoPor`, `inicioUrl`) e sobrepõe a data aproximada da licença e a do Planalto. O presidente é o do governo em que ele assumiu o cargo atual. Sem entrada: Empreendedorismo. O titular é Paulo Henrique Rodrigues Pereira (confirmado pelo responsável pelo projeto); a Wikipédia ainda mostra Tadeu Alencar (desde 03/04/2026), então não serve de fonte. Fica a data aproximada do Planalto até haver outra fonte para a posse.

## Total de autores nos projetos das Assembleias (2026-10-29)
- **De onde:** sem fonte nova; usa `idsAutores` já coletado de cada Assembleia.
- **Como:** `gerar_estaduais.py` grava `totalAutores` (autores contando quem não é deputado) junto de `coautores`; a ficha mostra o total quando passa dos deputados listados.

## Inidôneos pelo TCU nos fornecedores (2026-10-29)
- **De onde:** `https://contas.tcu.gov.br/ords/condenacao/consulta/inidoneos` (`tcu_inidoneos` em `ENDPOINTS.md`): API aberta do TCU, sem chave, 90 empresas e pessoas proibidas de licitar com a administração federal (nome, CPF/CNPJ, processo, deliberação, datas, UF).
- **Como:** `scripts/coletar_tcu.py` (mesmo job `tcu`) pagina como os inabilitados e grava `dados/tcu/inidoneos.json`, fora do git. Só o CNPJ válido é guardado; CPF de pessoa física é descartado. `fornecedores.construir` liga pelo CNPJ base (a sanção é da empresa; o fornecedor já junta matriz e filiais) e `site/dados/inidoneos_tcu.json` (id do fornecedor -> sanções) alimenta o aviso "Inidônea pelo TCU", com o processo, no ranking de fornecedores e no cruzamento com doadores. Só aparece para quem está entre os fornecedores do ano. Contrato semanal: `tcu_inidoneos`.

## Inabilitados pelo TCU (2026-10-29)
- **De onde:** `https://contas.tcu.gov.br/ords/condenacao/consulta/inabilitados` (`tcu_inabilitados` em `ENDPOINTS.md`): API aberta do TCU, sem chave, 846 pessoas proibidas de exercer cargo ou função pública (nome, processo, deliberação, datas, UF e município do caso). Os `inidoneos` (proibidos de licitar) entram na entrada acima.
- **Como:** `scripts/coletar_tcu.py` (job `tcu` do `atualizar.yml`) pagina por `limit=500`/`offset` e grava `dados/tcu/inabilitados.json`, fora do git. O CPF não é guardado. `identidades.ligar_inabilitados` liga por nome completo e UF do caso (`nome+uf`, média; homônimo na mesma UF não liga) e `gerar.py` grava `site/dados/inabilitados_tcu.json`, mostrado na ficha com o número do processo. Na primeira medição, 5 dos 846 nomes batiam com alguém do núcleo, todos homônimos de outra UF: zero ligações.

## Verba de gabinete de anos anteriores e presença em plenário (2026-10-29)
- **De onde:** raspagem de `https://www.camara.leg.br/deputados/<id>/verba-gabinete?ano=<ano>` (`camara_portal_verba_ano`) e `.../presenca-plenario/<ano>` (`camara_portal_presenca`), em `ENDPOINTS.md`.
- **Como:** `ler_verba_ano` e `ler_presenca_plenario` (`scripts/coletar.py`), chamadas por `coletar_recursos_camara` para os anos da legislatura atual. Anos encerrados são lidos uma vez (ficam em `recursos.verbaAnos` e `recursos.presenca`); só a presença do ano corrente é relida todo dia. Falha de página só avisa. Tabelas "Verba de gabinete nos anos anteriores" e "Ausências em plenário" em "Recursos e benefícios". Contrato semanal para as duas páginas.

## Pessoal de gabinete por grupo funcional (2026-10-29)
- **De onde:** raspagem de `https://www.camara.leg.br/deputados/<id>/pessoal-gabinete` (HTML; `camara_portal_pessoal` em `ENDPOINTS.md`), seção "Em exercício".
- **Como:** `ler_pessoal_gabinete` (`scripts/coletar.py`), chamada por `coletar_recursos_camara` logo após a página principal (mais 1 página por deputado, 3 em paralelo); guarda só a contagem por grupo funcional em `recursos.pessoal` (sem nomes nem salários); falha da página só avisa. Aparece em "Recursos e benefícios". Contrato semanal: `camara_portal_pessoal`.

## Recursos do deputado no portal da Câmara (2026-10-29)
- **De onde:** raspagem da página `https://www.camara.leg.br/deputados/<id>` (HTML; `camara_portal_recursos` em `ENDPOINTS.md`): bloco "Recursos" (pessoal de gabinete, imóvel funcional, auxílio-moradia, viagens em missão oficial, passaporte diplomático) e "Verba de gabinete" (gasto, não utilizado, gasto por mês, limite mensal). 1 página por deputado, 3 em paralelo.
- **Como:** `coletar_recursos_camara` (`scripts/coletar.py`), no passo `--so deputados`; grava `dados/camara_recursos.json`, fora do git; fonte opcional (página que falha mantém o valor anterior; páginas sem o bloco viram aviso). `gerar.py` põe `recursos` na ficha do deputado; bloco "Recursos e benefícios" na aba Perfil e gastos. Contrato semanal: `camara_portal_recursos` em `contrato_apis.py` (falha se o bloco sumir).
- **Fora desta etapa:** `pessoal-gabinete` (só a contagem do bloco entra), `presenca-plenario` (já coberta pela API) e `passaporte-diplomatico` (só "Possui" na página principal).

## Discursos e eventos do deputado (2026-10-29)
- **De onde:** API de Dados Abertos da Câmara, `https://dadosabertos.camara.leg.br/api/v2/deputados/<id>/discursos` (agora todos da legislatura, paginados) e `/deputados/<id>/eventos` (`camara_discursos`, `camara_eventos` em `ENDPOINTS.md`).
- **Como:** `coletar_complementos` guarda por deputado `discursosResumo` (total, por ano, por tipo e as palavras mais frequentes nos sumários) e `eventos` (total, por ano e os 5 mais recentes: tipo, título, órgão, link do portal). Mesma releitura escalonada dos demais complementos (1 + id % 7 dias); cada bloco falha sozinho. Mostrado na aba Trajetória da ficha.

## Perfil da bancada federal pela composição atual (2026-10-29)
- **De onde:** sem fonte nova. `perfil_casas/<UF>.json` (`federal`) passa a usar os registros de candidatura de 2022 (TSE, já em `dados/tse/2022/`) dos deputados em exercício, ligados por nome e UF, suplentes que assumiram inclusive; traz `composicao: "atual"` e `emExercicio`. Quem não tem registro ligado fica de fora do perfil.

## Aposentadoria parlamentar de ex-senadores (2026-10-29)
- **De onde:** `https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/aposentados` (1 chamada, ~60 ex-senadores: tipo IPC ou PSSC, início e valor mensal). `aposentados-ipc` e `aposentados-pssc` não foram coletados: só repetem o tipo e a data.
- **Como:** `coletar_aposentados_senado` (`scripts/coletar.py`), no passo do Senado; grava `dados/senado_aposentados.json`, fora do git. A fonte traz só o nome, então `identidades.ligar_aposentados` liga à pessoa do núcleo de mesmo nome completo que já foi candidata ou titular ao Senado (método `nome+cargo`, confiança média; nome repetido não liga). `gerar.py` grava `site/dados/aposentados_senado.json` (por id de pessoa).
- **No site:** bloco "Aposentadoria parlamentar" na ficha da pessoa ligada (página do político e do senador).

## Partido de ex-deputados nos coautores (2026-10-29)

Sem endpoint novo (`/deputados/{id}` e `/deputados/{id}/historico`, já em `ENDPOINTS.md`). `coletar.py` (`coletar_partidos_ex_deputados`) consulta uma vez cada autor de `proposicoes_autores.json` que não está em `dados/deputados/` e grava `dados/partidos_ex_deputados.json` (`partido` final e `historico` de todas as legislaturas), no máximo `EX_DEPUTADOS_POR_EXECUCAO` (500) por execução, os mais novos primeiro. `gerar.py` usa esse arquivo para a sigla dos coautores que já saíram da Câmara. Não medido contra a API real (só teste offline).

## Ministros de Estado: ligação, geração, páginas e histórico (2026-10-29)

Sem fonte nova: `gerar.py` passa a ler `dados/ministros/` (sem internet). `scripts/ministerios.py` acha a pasta pela ementa (127 de 17.169 pedidos ficaram sem pasta) e pelo cargo do Planalto (38 de 38); `identidades.py` liga ministro -> pessoa (nome civil), requerimento -> ministro (`nome+pasta` quando a ementa cita o ministro; `pasta+data` só depois do início conhecido) e autoria do Senado -> senador (`nome+uf`), tudo em `nucleo/ligacoes.json` (`ministros`). Mandato `MINISTRO DE ESTADO` (sem prazo, início aproximado) em `nucleo/mandatos.json`. Saídas: `ministerios.json`, `ministerio/<pasta>.json`, `ministro/<pessoa>.json`, `ministros_autores.json`; páginas `ministerios.html` e `ministro.html`; aviso "Licenciado: Ministro de X" nas fichas de deputado e senador; categoria `ministro` e eventos de requerimento no histórico diário (`historico.py`).
- **Limites:** o Planalto não publica a data da posse, então o início é o da licença do parlamentar (Câmara/Senado) ou o dia em que a coleta viu o nome; sem o ministro da época, só os pedidos que citam o nome ficam ligados a ele, os demais ficam na página da pasta. A resposta a requerimento do Senado não é coletada.

## Ministros de Estado: coletor da primeira etapa (2026-10-29)

`scripts/coletar_ministros.py`, job `ministros` no `atualizar.yml`, grava em `dados/ministros/` (formato no docstring do coletor). A ligação às pessoas e as páginas vieram na etapa seguinte (entrada acima).
- **Lista de ministros:** `https://www.gov.br/planalto/pt-br/conheca-a-presidencia/ministros-e-ministras` (HTML; só os atuais, sem datas; exige `Accept: text/html`, senão o gov.br responde 401/404). Quem entra e sai é marcado pelo dia da coleta (`vistoDesde`/`vistoAte`).
- **Requerimentos na Câmara:** arquivos anuais `https://dadosabertos.camara.leg.br/arquivos/proposicoes/json/proposicoes-<ano>.json` (~74 MB em 2026) e `proposicoesAutores-<ano>.json`, de 2023 em diante. Ficam os RIC com "ministr" na ementa e os REQ de convocação/convite de ministro (o filtro `keywords` da API devolve 0 para REQ). Nos RIC, envio ao ministério, fim do prazo e resposta saem de `/proposicoes/{id}/tramitacoes`, relida só quando o último status muda e até chegar a resposta. Ano encerrado (`comum.ano_encerrado`) não é baixado de novo depois de todas as tramitações lidas.
- **Requerimentos no Senado:** `https://legis.senado.leg.br/dadosabertos/processo?sigla=RQS&ano=<ano>` (1 chamada por ano), tipos "Informações" e "Convocação de autoridades" com "ministr" na ementa.
- **Licenças:** `/deputados/{id}/historico` dos deputados da legislatura fora de exercício (afastamento "Ministro de Estado") e `senador/lista/atual.json` e `afastados.json` do Senado (causa "Ocupação de cargo de ministro/secretário", que não separa ministro de secretário estadual).
- **Medido em 2026-10-29:** coleta do zero 23 min (14.543 tramitações de RIC de 2023 a 2026, 6 conexões; prazo `MINISTROS_PRAZO_MIN`, 25 min no Actions, deixa o resto para o dia seguinte); com cache 46 s (só 2025 e 2026 baixados, nenhuma tramitação a reler).

## Rede de coautoria (2026-10-28)

Sem fonte nova: `scripts/gerar_coautoria.py` cruza `dados/proposicoes_autores.json` (`/proposicoes/{id}/autores`, já coletado) com as proposições de cada deputado. Conta só projetos (`TIPOS_PROJETO`) com mais de um deputado em exercício entre os autores; autor que não é deputado e projeto com mais de 30 deputados ficam de fora. Partido de cada autor na data de apresentação. Gera `coautoria` em `site/dados/deputado/<id>.json` (parceiros mais frequentes, ids) e `site/dados/coautoria.json` (partido × partido). Páginas: bloco "Com quem assina projetos" no perfil do deputado e `coautoria.html`.

## Histórico só com o que é novo de verdade; republicar sem coletar (2026-10-28)

O histórico, o RSS, o resumo por e-mail e os avisos diários passam a registrar só o que tem **data do ato até 3 dias antes da coleta** (`JANELA_ATO_DIAS`), ou nenhuma data. Backlog e publicação atrasada da fonte continuam no site, fora do histórico. O dia do histórico segue sendo o da descoberta, e cada evento guarda a data do ato como a fonte a deu; mudança posterior vira evento novo. Em Assembleia e capital, a mudança de situação não tem data do ato na fonte: o evento mostra a data de apresentação com `dataDoAtoAproximada` (a página escreve "apresentado em ..., data da mudança desconhecida"), entra sempre pela janela e, se passar de `LIMITE_LOTE` por local num dia (fonte reescrevendo situações antigas), vira um evento "lote"; marcos (aprovado, vetado...) ficam individuais. Os resumos semanal e mensal não usam a janela.

Novo `.github/workflows/republicar.yml` (push em `site/`, `scripts/` e workflows, ou manual): baixa os pacotes da última execução bem-sucedida do `atualizar.yml` (agora guardados por 3 dias), roda `gerar.py`, espelha o histórico (`historico.py --so-espelhar`), refaz os feeds e publica. Não coleta, não grava histórico e não envia e-mail. O `atualizar.yml` deixa de rodar no push: só no agendamento e à mão. Coletor novo: rodar o `atualizar.yml` manualmente.

## Histórico: dia da coleta e hora real da execução (2026-10-28)

O dia de cada histórico passou a ser o dia (Brasília) em que a coleta rodou, e não o anterior. Cada arquivo traz `coletaEm` e `coletaAnterior` (hora em que a execução começou, obtida de `gh run view`; nos dias antigos, da lista de execuções do Actions) e a página mostra "novidades entre <coleta anterior> e <coleta>". Os arquivos já gravados foram renomeados +1 dia. Links de e-mail e RSS somam 1 dia ao dia dos fatos.

## ES: CSV de despesas em 3 conexões e leitura incremental (2026-10-27)

`https://dados.es.gov.br/dataset/portal-da-transparencia-despesas-execucao-orcamentaria-e-financeira` (CSV anual no S3, aceita `Range`). Medido: ~0,65 MB/s numa conexão e ~1,8 MB/s em três. O CSV agora é lido em até 3 fatias paralelas com `Range`, com um offset por fatia no `parcial_<ano>.json`. Quando o arquivo muda, só o trecho novo depois do `tamanho` guardado é lido, e uma leitura completa acontece a cada 14 dias (estornos em linhas antigas). O passo de commit do workflow agora faz `git pull --rebase` antes do `git push` (a coleta longa perdia a corrida contra outros pushes).

## TSE 2026: recoleta quando o CDN troca o arquivo (2026-10-27)
- **De onde:** `https://cdn.tse.jus.br/estatistica/sead/odsele/` (`consulta_cand`, `votacao_candidato_munzona`, `bem_candidato`; nenhuma fonte nova).
- **Como:** `coletar_tse.py` faz um HEAD por arquivo e compara o `Last-Modified` com o de `dados/tse/2026/_coleta.json` (`modificados`); baixa de novo só se mudou. Reserva: refaz a cada 7 dias (antes, a cada 2 dias sem olhar o arquivo).

## Status das APIs na página Sobre os dados (2026-10-24)
- **De onde:** as URLs de teste de `ENDPOINTS.md` (nenhuma fonte nova).
- **Como:** o job `publicar` roda `python scripts/testar_endpoints.py --sem-tabela` todo dia antes do `gerar.py`; o resultado (status, data e hora do checkup, último funcionamento, primeira verificação) fica em `dados/status_apis.json`, commitado pelo Actions, e `gerar.py` copia para `site/dados/status_apis.json`. `sobre.html` lista cada API, destaca as que nunca funcionaram desde a primeira verificação e as fora do ar.

## Vida do projeto: tramitações e proposições relacionadas (2026-10-24)
- **De onde:** API da Câmara, `https://dadosabertos.camara.leg.br/api/v2/proposicoes/<id>/tramitacoes` (já usado só no Executivo) e `/relacionadas` (`camara_tramitacoes`, `camara_relacionadas` em `ENDPOINTS.md`).
- **Como:** `coletar_tramitacoes_proposicoes` (`coletar.py`) guarda em `dados/proposicoes_tramitacoes.json` os eventos (data, órgão, tramitação, situação, despacho até 250 caracteres), o último relator designado (lido do despacho) e as relacionadas (id e rótulo). Cada execução consulta no máximo `TRAMITACOES_POR_EXECUCAO` (3000): primeiro os novos, depois os que ainda tramitam, relidos após 7 dias; projeto finalizado não é relido. `gerar.py` grava `site/dados/tramitacao/<id>.json`, e a página da proposição da Câmara mostra "Vida do projeto".

## Carreira do deputado: ocupações anteriores e partido do coautor na data (2026-10-24)
- **De onde:** API da Câmara, `https://dadosabertos.camara.leg.br/api/v2/deputados/<id>/ocupacoes` (`camara_ocupacoes` em `ENDPOINTS.md`); o `/historico` já era coletado.
- **Como:** `coletar.py` guarda `ocupacoes` (título, entidade, UF, anos) no bloco de complementos de cada deputado (mesma releitura escalonada por `id % 7`); o perfil mostra "Ocupações anteriores". `gerar.py` passa a dar ao coautor o partido da data de apresentação do projeto, pelo `historico` da legislatura 57, e cai no partido atual sem histórico ou data. Ex-deputados seguem sem sigla (só deputados em exercício são coletados).

## Assembleias BA, CE e MS: pagamentos das emendas e lançamentos da verba no site (2026-10-24)
- **De onde:** BA: Dados Abertos Bahia (CKAN, `https://dados.ba.gov.br/dataset/emendas-parlamentares`), CSV `VW_PAINEL_EMENDAS_PARLAMENTARES_PAGAMENTOS.csv` do mesmo ZIP das emendas (host já em `ENDPOINTS.md`). CE e MS: nenhuma fonte nova, campos que o coletor já guardava (`empenho`, `descricao`; `documento`, `emissao` e o comprovante).
- **Como:** BA: `coletar_estadual_ba.py` lê o CSV de pagamentos do ZIP já baixado e grava `dados/estaduais/BA/pagamentos_<ano do pagamento>.json` só com pagamentos de 2026 em diante, de emendas dos deputados da lista; cada item guarda `numero` (o `num_codigo` da emenda, sem repetir deputado), `data` ISO, `credor` (só razão social: a fonte não traz CNPJ), `valor`, `objeto`, `empenho` e `efetivado`. `gerar_estaduais.py` junta pelo `numero` e põe `emendas.pagamentos` no JSON do deputado; CE e MS ganham `verba.anos[].lancamentos` (2026 em diante) com empenho, descrição, nº e emissão do documento e o link da fonte; `estadual.js` mostra as duas tabelas.
- **Fora:** liquidações da BA (só ligam por `num_codigo_liqu`; o pagamento já traz o valor); arquivo de 2022 da VDP do CE.

## Ficha do deputado e do senador: trajetória, comissões e mandatos (2026-10-24)
- **De onde:** API de Dados Abertos da Câmara, `https://dadosabertos.camara.leg.br/api/v2/deputados/<id>/profissoes`, `/mandatosExternos`, `/historico` e `/discursos` (`camara_profissoes`, `camara_mandatos_externos`, `camara_historico`, `camara_discursos` em `ENDPOINTS.md`); API do Senado, `https://legis.senado.leg.br/dadosabertos/senador/<codigo>/comissoes.json` e `/mandatos.json` (`senado_comissoes`, `senado_mandatos`).
- **Como:** `coletar.py` grava na ficha do deputado (`dados/deputados/<id>.json`) `profissoes`, `mandatosExternos`, `historico` (só a legislatura 57) e `discursos` (os 5 mais recentes desde 2023-02-01: data, tipo, fase, sumário, link; sem a transcrição), cada bloco com falha própria e `complementosEm`. Para não somar 4 chamadas por deputado por dia, um deputado só é relido depois de `1 + id % 7` dias. `coletar_ficha_senado` grava `dados/senado_ficha.json` (fora do git, entra no pacote do job do Senado): comissões atuais ou encerradas desde 2023 e mandatos com filiações. O `gerar.py` repassa tudo a `site/dados/deputado/<id>.json` e `senador/<id>.json`; o site mostra o bloco Trajetória (deputado) e Comissões e Mandatos (senador), com link da fonte.
- **Também no site:** `ementaDetalhada` da proposição (quando difere da ementa), `orgao` das votações nominais (hoje só PLEN) no resumo, na tela da votação e nas votações do projeto, e `emTramitacao` dos projetos das Assembleias (SAPL). Amostras dos endpoints novas em `tests/fixtures/contratos/`.

## Malhas do mapa em cópia local (2026-10-24)
- **De onde:** IBGE, `https://servicodados.ibge.gov.br/api/v3/malhas` (`ibge_malha_pais`, `ibge_malha_estado` em `ENDPOINTS.md`), a mesma que o mapa consultava no navegador.
- **Como:** `python scripts/baixar_malhas.py` grava `site/geo/br.json` e `site/geo/uf_<código>.json` (qualidade mínima); o mapa lê a cópia local e só cai na API do IBGE se o arquivo faltar. Motivo: a API do IBGE ficou fora do ar e o mapa da página inicial parou de carregar. **Pendente:** rodar o script quando o IBGE voltar e commitar `site/geo/`.

## Dados da empresa pela Receita para os fornecedores (2026-10-24)
- **De onde:** CNPJ aberto da Receita Federal, arquivos mensais `Empresas`, `Estabelecimentos` e `Socios` (0 a 9) mais `Cnaes`, `Naturezas`, `Qualificacoes` e `Municipios`, em `https://arquivos.receitafederal.gov.br/public.php/webdav/<AAAA-MM>/` (compartilhamento público da Receita, Nextcloud/WebDAV, usuário = token `YggdBLfdninEJX9` e senha vazia; o endereço antigo `/dados/cnpj/dados_abertos_cnpj/` responde 404; `receita_cnpj` em `ENDPOINTS.md`).
- **Como:** `scripts/coletar_receita.py` roda só na máquina local (`--listar`, `--baixar`, depois sem opção): guarda em `dados/receita/` apenas as empresas de `nucleo/fornecedores.json` (tipo PJ), a matriz de cada uma (situação, abertura, CNAE, local), razão social, natureza, porte, capital e os sócios (nome, qualificação, entrada); nunca CPF de sócio. `scripts/empresas.py` (no `gerar.py`) grava `nucleo/empresas.json` só das empresas que o site mostra, com a data da primeira nota do ano e os dias desde a abertura. `fornecedores.html` mostra o bloco em cada fornecedor e em cada empresa do cruzamento com doadores, com a fonte e a competência; empresa aberta até 365 dias antes da primeira nota do ano vem em negrito, como fato cadastral e sem juízo.
- **Conferido (2026-10-24):** o servidor real lista os meses 2023-05 a 2026-10; a competência 2026-09 foi baixada (34 ZIPs, cerca de 7 GB em `dados/receita_bruto/`) e coletada: 7.986 de 7.986 empresas fornecedoras encontradas, 87 arquivos em `dados/receita/cnpj/` (3,6 MB), sem campo vazio nas amostras, layout dos CSV conferido. `nucleo/empresas.json` (152 KB) sai do `gerar.py`. O link da fonte no site passou para a página do compartilhamento. `RFB_BASE` e `RFB_TOKEN` trocam endereço e token. Sem `dados/receita/`, o `gerar.py` só avisa, grava `empresas.json` vazio e o site fica sem o bloco.

## Doadores de campanha x fornecedores das cotas, só por CNPJ (2026-10-24)
- **De onde:** nenhuma fonte nova nem endpoint novo: prestação de contas do TSE (`tse_prestacao_contas`, já coletada por `coletar_contas.py`) e os fornecedores de Câmara, Senado e Assembleias (`fornecedores.py`). Roda offline em `gerar.py`. Dados da empresa pela Receita (atividade, abertura, sócios) ficam para a etapa 2 do pacote 5.1.
- **Como:** `coletar_contas.py` (versão 4) passa a guardar o CNPJ de doador pessoa jurídica (`doadoresPJ`, `originariosPJ`: todos, não só os cinco maiores); CPF continua sem ser guardado. `identidades.ligar_doadores` liga doador a fornecedor com CNPJ pela raiz de 8 dígitos (`cnpj`, alta) ou, nas contas ainda sem CNPJ, pelo nome padronizado igual ao de um único fornecedor (`nome`, média); ambíguo não liga e pessoa física fica de fora. `scripts/doadores.py` monta `site/dados/doadores_fornecedores.json` (com `fontes` de doações e pagamentos e quanto o mesmo político pagou à empresa na cota do ano) e grava a ligação em `nucleo/ligacoes.json` (`doadores`). A seção nova de `fornecedores.html` mostra cada cruzamento com a fonte e o método.
- **Contas na versão 4:** os JSONs de `dados/tse/contas/` (2022 e 2024) já têm o CNPJ (`doadoresPJ`); recoletados em 2026-10-29 a partir dos ZIPs locais, sem mudança de conteúdo.

## Datas dos demais coletores e teste de guarda da normalização (2026-10-23)
- **De onde:** nenhuma fonte nova; mudança em `coletar_executivo.py`, `coletar_estaduais.py`, `coletar_estadual_pr.py` e nas prefeituras BA, GO e SP.
- **Como:** as datas passam por `estaduais_comum.data_iso` / `data_br_iso` (só data que existe no calendário); onde a fonte não traz data válida o campo fica `null` (no executivo, `remessa` só é gravada com data válida; na prefeitura de GO, a proposição sem data de criação é ignorada). `tests/test_normalizacao_coletores.py` falha se um coletor voltar a cortar data com `[:10]`, usar `strptime` dd/mm/aaaa ou limpar CNPJ com `re.sub` à mão.

## Câmara e Senado: documento, data e e-mail normalizados na coleta (2026-10-23)
- **De onde:** nenhuma fonte nova; mudança em `scripts/coletar.py` (cota da Câmara pelo CSV e pela API, CEAPS, proposições, votações e perfis).
- **Como:** o CNPJ/CPF do fornecedor passa por `fornecedores.documento` (via `estaduais_comum.fornecedor`): só dígitos, zero à esquerda restaurado, dígito verificador conferido; vazio, mascarado ou inválido vira `null` (antes `""` ou os dígitos como vieram). As datas passam por `estaduais_comum.data_iso` (existente no calendário) e o e-mail por `estaduais_comum.email`.
- **Mudança de dado:** `cnpj` ausente passa de `""` para `null`; documentos com dígito verificador errado deixam de ser gravados. O cache bruto já versionado só muda quando o ano for recoletado.

## E-mail, partido, valor e mês normalizados nos coletores estaduais (2026-10-23)
- **De onde:** nenhuma fonte nova; mudança em `estaduais_comum.py` e nos coletores BA, CE, GO, MG, MT, PA, PE, PR, RN, RR, SC, SE e SP.
- **Como:** `estaduais_comum.email` grava o e-mail em minúsculas, sem `mailto:` e só se tiver forma de e-mail; `sigla_partido` resolve entidades e compacta espaços (o id continua saindo de `identidades.partido_id` no núcleo); PA passa o valor da verba por `valor_br`; MT passa `mesCompetencia` por `mes_numero`.

## Datas e categorias normalizadas nos coletores estaduais (2026-10-23)
- **De onde:** nenhuma fonte nova; mudança em `estaduais_comum.py` e nos coletores BA, CE, MG, MS, PA, PE, RN e SP.
- **Como:** `estaduais_comum.data_br_iso` e a nova `data_iso` (AAAA-MM-DD, também com hora ou `{"$": ...}`) só devolvem data que existe no calendário; os coletores deixam de montar a data à mão (`[:10]`, `split("/")`, f-string). O CE deixa de mapear a categoria da verba de desempenho no coletor: grava a descrição da fonte e o `gerar*` agrupa por `categorias.REGRAS` (acrescentadas "pacote de dados" em telefonia).
- **Mudança de dado:** `categoria` das despesas do CE passa de rótulo curto ("Alimentação e refeição") para a descrição original do empenho; o agrupamento do site continua pelos ids de `categorias.py`.

## Fornecedor normalizado na entrada dos coletores estaduais (2026-10-23)
- **De onde:** nenhuma fonte nova; mudança em `coletar_estadual_{ce,mg,ms,pe,sc,sp}.py`.
- **Como:** `estaduais_comum.fornecedor` grava o nome com espaços compactados e o documento só com dígitos (zeros à esquerda restaurados, dígito verificador conferido por `fornecedores.documento`); vazio, mascarado ou inválido vira `null`. Antes cada coletor gravava o CNPJ como a fonte trouxe.

## Ids estáveis, com hash da fonte (2026-10-23)
- **De onde:** nenhuma fonte nova; mudança no jeito de gerar os ids do núcleo (`site/dados/nucleo/`).
- **Como:** `scripts/ids.py` (`gerar_id`) passa a ser o único gerador: `pes_` (os mesmos ids de antes), `man_`, `can_`, `dsp_`, `for_pf_` e `for_n_`. O id de mandato deixa de depender da pessoa e da data de início e sai do registro da fonte que o criou (sequencial do TSE ou id da Casa); candidaturas guardam `eleicao` e `sequencial`. **Mudam de valor** os ids `man_`, `can_`, `dsp_`, `for_pf_` e `for_n_` (nada deles é salvo em `dados/` nem usado pelas páginas); os `pes_` e `for_<CNPJ>` ficam iguais.
- **Conferido:** teste com a mesma duplicata do TSE em duas ordens de arquivo dá o mesmo id de mandato; `pes_` bate com o sha1 de antes.

## Lista fixa de categorias de despesa (2026-10-23)
- **De onde:** nenhuma fonte nova; mesmos rótulos de despesa da Câmara (`tipoDespesa`), do Senado (CEAPS) e das verbas das Assembleias.
- **Como:** `scripts/categorias.py` define 16 categorias e as regras que ligam o rótulo de cada fonte a uma delas. `gerar.py` e `gerar_estaduais.py` agrupam por categoria: `despesas.porCategoria` (Câmara e Senado, no lugar de `porTipo`) e `verba.anos[].categorias` (Assembleias) trazem `id`, `categoria`, `total` e `originais` (rótulo da fonte e valor). Os arquivos de `dados/` não mudam (rótulo original), então vale para o que já foi coletado. Rótulo novo sem regra vai para `outros` e `gerar.py` avisa.
- **Conferido contra os dados reais:** os 233.603 lançamentos de `dados/estaduais/*/verbas_*.json` (BA, CE, ES, GO, MG, MS, PA, PE, RR, SC, SP) caem todos em regra, nenhum em `outros` por falta de regra. Câmara e Senado ficaram cobertos só pelos rótulos conhecidos e pela amostra do contrato (os dados brutos federais não estão no repositório).

## Ligação de nomes das Assembleias só em `identidades.py` (2026-10-23)
- **De onde:** nenhuma fonte nova; mudança de código nos 17 coletores estaduais com ligação de nome (BA, CE, ES, GO, MG, MS, MT, PA, PE, PR, RJ, RR, RS, SC, SE, SP).
- **Como:** `identidades.ligar_nomes(nomes, deputados, uf)` substitui `estaduais_comum.ligar_nomes`/`ligar_por_palavras` e as funções `ligar` de cada UF (regra de cada UF em `identidades.ESTRATEGIAS`; apelidos de MS em `scripts/ligacoes_manuais.json`). Cada coleta grava `dados/estaduais/<UF>/ligacoes.json` (`nomes`: nome -> [id, método, confiança], `ambiguos`, `semPar`), e o `gerar.py` junta tudo em `site/dados/nucleo/ligacoes.json` (`registros`, `resumoRegistros`), com a pessoa do núcleo. Os arquivos de dados dos coletores não mudam de formato. `ligacoes.json` por UF só passa a existir na próxima coleta de cada UF.
- **Conferido:** os testes de cada UF sobre `ligar` seguem iguais; nenhuma chamada à internet.

## Fichas do TSE sem repetir a disputa em cada candidato (2026-10-23)
- **De onde:** nenhuma fonte nova; mesmos arquivos de `dados/tse/disputa`, `partidos` e `coligacoes`.
- **Como:** em `site/dados/p/t/<ano>/<arquivo>.json`, a chave `_disputas` traz uma vez só o que os eleitos do mesmo cargo e local têm em comum (comparecimento e vagas, votos por partido, coligações). A ficha de cada candidato deixou de carregar `disputa`, `partidoVotos` e `alianca`; `completarEleicao` (`site/assets/js/ficha.js`, chamada em `politico.js`) monta os três ao abrir a página, com as mesmas regras que `gerar_politicos.py` usava (o vice disputa com o titular; as federações somam os partidos do grupo). Fichas aninhadas (eleição de senador e de deputado federal) seguem completas.
- **Conferido contra os dados reais:** das 72.101 fichas de 2022, 2024 e 2026, as 72.101 montadas no navegador ficam iguais às que as funções antigas geravam. `site/dados/p` cai de 194 MB para 179 MB, e o arquivo de um município, que o leitor baixa inteiro, deixa de repetir os mesmos blocos em cada vereador.
- **Não mexi em** `site/dados/deputado/<id>.json`: ali a mesma ementa se repete entre deputados diferentes (uns 38 MB no total), mas cada leitor baixa só o arquivo de um deputado, então tirar a repetição só obrigaria a página a baixar também um arquivo comum, sem ganho para quem lê.

## Núcleo de candidaturas e disputas (2026-10-23)
- **De onde:** nenhuma fonte nova; une o que `coletar_tse.py`, `coletar_contas.py`, `coletar_disputa.py`, `coletar_partidos.py` e `coletar_coligacoes.py` já gravam em `dados/tse/` (eleitos, prestação de contas, comparecimento e vagas, votos por partido, coligações e federações).
- **Como:** `scripts/candidaturas.py` (chamado pelo `gerar.py`, sem internet) grava `site/dados/nucleo/candidaturas/<ano>.json` (um registro por eleito: `pessoa`, `partido` e `federacao` do núcleo, votos, patrimônio e o resumo da campanha: receitas, despesas, origem do dinheiro e custo do voto) e `site/dados/nucleo/disputas/<ano>.json` (uma disputa por cargo e local, juntando comparecimento, votos por partido e coligações; o id `dsp_<ano>_<cargo>_<local>` se deduz da candidatura). O vice aponta para a candidatura do titular (`chapa`), que tem as contas, e disputa com ele. O detalhe das contas (doadores, gastos por categoria) e a votação por seção seguem nas fichas.
- **Medido nos dados atuais:** 72,7 mil candidaturas (65,3 mil com contas), 11,3 mil disputas; todas as candidaturas ligam a uma pessoa. 54 sem disputa coletada e 62 sem prestação de contas (fora a eleição de 2026, ainda sem esses dados). Em `site/dados/p/t/2024/`, `disputa`, `partidoVotos` e `alianca` repetem o mesmo conteúdo na ficha de cada candidato do mesmo cargo e local (cerca de 17 MB); `disputas/<ano>.json` guarda uma vez só, e as fichas deixaram de trazer as cópias (ver "Fichas do TSE sem repetir a disputa em cada candidato").
- **Limite:** o resumo de contas guardado pelo projeto traz o nome dos doadores, não o CPF/CNPJ, então ainda não há ligação entre doador e fornecedor.

## Núcleo de mandatos (2026-10-23)
- **De onde:** nenhuma fonte nova; usa os eleitos do TSE (período legal de cada cargo, `MANDATOS` em `gerar_politicos.py`) e as listas de quem está em exercício (Câmara, Senado e Assembleias com coleta).
- **Como:** `scripts/mandatos.py` (chamado pelo `gerar.py`, sem internet) grava `site/dados/nucleo/mandatos.json`: um registro por mandato com `pessoa` (id do núcleo), `cargo`, `uf`, `municipio`, `eleicao`, `inicio`, `fim`, `partidoEleicao`, `partido`, `status` e, para suplentes, `condicao`. Status: `atual`, `futuro` (eleitos de 2026), `encerrado` e `fora_de_exercicio` (eleito, no período, mas ausente da lista da Casa: o suplente assumiu). Suplente em exercício, que o TSE não lista, ganha mandato próprio com `inicioAproximado` (Câmara e Assembleias; o Senado informa a data de exercício). Segundo turno e não eleitos não geram mandato. `mudouPartido` só acende quando o partido de hoje é outro depois de aplicar fusões (PSL → UNIÃO não conta); as fontes não publicam a data da troca, então não há período por partido.
- **Medido nos dados atuais (sem Câmara e Senado locais):** 72,8 mil mandatos: 71 mil atuais, 1,7 mil futuros (2026), 65 deputados estaduais eleitos fora da lista da Assembleia; 107 suplentes em exercício sem registro no TSE; 206 mandatos atuais com partido diferente do da eleição. O arquivo tem uns 17 MB (o servidor comprime).

## Cadastro de proposições e relação de autoria (2026-10-23)
- **De onde:** nenhuma fonte nova; a mesma coleta de `/proposicoes?idDeputadoAutor=` (e as autorias que já existiam).
- **Como:** tipo, número e ementa de cada proposição da Câmara passam a ficar uma vez só em `dados/proposicoes_cadastro/<ano>.json` (`{id: [tipo, número, ementa]}`, `scripts/cadastro_proposicoes.py`); `dados/proposicoes/<idDeputado>.json` guarda só `{ate, ids}`. A primeira coleta depois da mudança converte os arquivos antigos (campo `itens`), sem consultar a API de novo; um id sem entrada no cadastro (execução interrompida) faz o deputado ser relido desde o início da legislatura. Coletores de detalhe, autoria e votações, `historico.py` e `resumo_email.py` leem os dois formatos, então a comparação com commits antigos continua certa.
- **Medido nos dados atuais:** 406 mil linhas para 228 mil proposições (um projeto de coautoria em massa se repetia uma vez por deputado); simulando a migração, `dados/proposicoes` vai de 86 MB para 4 MB mais 37 MB de cadastro, e os 513 arquivos reconstruídos ficam idênticos aos originais.
- **Relação proposição → pessoa:** `scripts/gerar_proposicoes.py` grava `site/dados/nucleo/autorias.json` (`{porPessoa: {id da pessoa: [[chave da proposição, 1 se principal]]}, semPessoa, proposicoes}`). A chave é a do índice (`c-<id>` Câmara, `s-<id>` Senado) e o id da pessoa é o do núcleo de identidades; autores sem ficha (ex-deputados, Executivo) contam em `semPessoa`.

## Núcleo de fornecedores e ranking nacional (2026-10-23)
- **De onde:** nenhuma fonte nova; une a cota da Câmara, a CEAPS do Senado e as verbas indenizatórias das Assembleias. A CEAPS passou a guardar também o `cpfCnpj` que a API já devolvia (`dados/senado_ceaps.json`, campo `cnpj`; o arquivo é baixado de novo todo dia).
- **Como:** `scripts/fornecedores.py` (chamado pelo `gerar.py`, sem internet) grava `site/dados/nucleo/fornecedores.json` (todos os fornecedores do ano: id, nome, grafias, documento) e `site/dados/fornecedores.json` (ranking dos 300 maiores, com valor por casa e os políticos que mais o usaram, ligados ao id de pessoa). Documento: só dígitos, zero à esquerda recuperado, dígito verificador conferido; mascarado ou inválido vale como ausente. CNPJs com a mesma raiz (matriz e filiais) são um fornecedor só. Despesa sem documento ganha o da mesma empresa quando o nome (sem caixa, acento, pontuação nem S/A, LTDA…) tem um único documento nas outras notas. CPF aparece mascarado e o id é um hash. Substitui `fornecedores_cota.json` e a página Fornecedores passa a mostrar as três origens, com filtro.
- **Medido nas Assembleias de 2026:** 9,2 mil fornecedores; das notas sem CNPJ válido, 262 ganharam o documento pelo nome e 8,6 mil seguem pelo nome (≈R$ 9,7 milhões de R$ 89,8 milhões); 7,5 mil notas sem nome nem documento ficam fora. A Câmara e o Senado não estão no repositório local, então só foram testados com dados de exemplo.

## Núcleo de identidades: id próprio de pessoa e de partido (2026-10-23)
- **De onde:** nenhuma fonte nova; liga o que já é coletado (eleitos do TSE de todas as eleições, deputados da Câmara, `senado.json` e `estaduais/<UF>/deputados.json`).
- **Como:** `scripts/identidades.py` (chamado pelo `gerar.py`, sem internet) grava `site/dados/nucleo/pessoas.json`, `partidos.json` e `ligacoes.json`. O id da pessoa (`pes_` + 12 hex) é o hash de nome civil e nascimento, então é o mesmo em qualquer eleição e na Câmara; Senado e Assembleias, que não trazem nascimento, ligam ao TSE por nome (cargo e UF) ou, no RJ, pelo sequencial, e cada ligação guarda método e confiança. Homônimo ou nascimento divergente não liga e vai para `ligacoes.json` (`ambiguos`). `partidos.json` unifica grafias (PC do B/PCdoB, UB/União Brasil), registra fusões (`sucessor`, `atual`) e as federações do TSE. As fichas do TSE e do Senado e `deputado/<id>.json` ganham `pessoa`.
- **Medido nos dados atuais:** 71,5 mil pessoas para 72,7 mil candidaturas eleitas; das 929 da Assembleias, 847 ligadas ao TSE (179 pelo sequencial, 681 pelo nome civil, 67 pelo nome de urna), 3 ambíguas e 82 sem ligação (suplentes, que não estão entre os eleitos). A mesma pessoa com grafia diferente entre eleições ainda vira duas.

## Página Proposições: busca de projetos e PECs com os políticos ligados (2026-10-23)
- **De onde:** nenhuma fonte nova; usa o que já é coletado (`proposicoes_autores.json`, `proposicoes_detalhe.json`, `proposicoes_votacoes.json`, `senado_autorias.json` e as votações nominais das duas casas).
- **Como:** `scripts/gerar_proposicoes.py` (chamado pelo `gerar.py`) grava `site/dados/proposicoes.json` (índice dos projetos, PECs etc. da Câmara e do Senado, com ementa e situação), `site/dados/proposicao/<c|s>-<ano>.json` (só autores e votações, por ano, sem repetir o que já está nas outras listas) e `site/dados/senadores.json`. A busca roda no navegador (`proposicoes.html`); a ficha (`proposicao.html?k=c-<id>`) junta esses arquivos com `deputados.json` e `votacoes[_senado].json` e lê o voto de cada político de `votacao[_senado]/<id>.json`. Só entram proposições de deputados e senadores em exercício; requerimentos e emendas ficam de fora.

## Anos encerrados não são baixados de novo em MS, MT, PA, RJ, RR, RS e SC (2026-10-23)
- **De onde:** as mesmas fontes, sem endpoint novo.
- **Como:** esses coletores refaziam todo dia 2023 em diante. Agora seguem `estaduais_comum.ano_encerrado`: ano anterior ao passado com arquivo gravado fica como está. RS: ZIP de diárias por ano (CKAN). MT: remuneração (uma consulta por deputado por ano) e diárias. SC: CSVs de gabinete e diárias. PA: painéis de verba e diárias e as 12 consultas mensais de gabinete. RJ: planilha de emendas por ano. RR: planilhas de diárias das pastas mensais. MS: as diárias, que só são conferidas e não gravadas, passam a ser lidas só no ano passado e no corrente. Hoje isso deixa 2023 e 2024 de fora da coleta diária.
- **Continua todo dia:** os ZIPs de proposituras e autores da ALESP, que trazem todos os anos num arquivo só e alimentam as novidades do dia, e a listagem de proposições do Executivo na Câmara (16 consultas pequenas).

## Assembleia do Espírito Santo: cota parlamentar e diárias (2026-10-23)
- **De onde:** Portal da Transparência do Estado no CKAN, `https://dados.es.gov.br/api/3/action/package_show?id=portal-da-transparencia-despesas-execucao-orcamentaria-e-financeira`, recursos `Despesas-<ano>.csv` (despesa de todos os órgãos, `;`, UTF-8 com BOM; o link redireciona para `one.s3.es.gov.br`). Listado em `ENDPOINTS.md` (`es_dados_despesas`). Deputados: eleitos de 2022 do TSE (`www.al.es.gov.br` segue sem responder).
- **Como:** `scripts/coletar_estadual_es.py` (job `es` na matriz `estaduais`) lê o CSV em streaming e guarda só as linhas pagas (`ValorPago` das OB, para não somar empenho, liquidação e pagamento) da `UnidadeGestora` Assembleia Legislativa: cota parlamentar (`SubelementoDespesa` "Cotas Parlamentares", ATO 3879/2024) em `verbas_<ano>.json` e diárias (`ElementoDespesa` "DIÁRIAS - CIVIL") em `diarias_<ano>.json`, só de 2026 em diante (os anos anteriores, ~4,3 GB de CSV, levariam dias de job), ligando o favorecido ao deputado pelo nome. Sem categoria, fornecedor nem destino na fonte (o histórico vai em `motivo`; o mês citado na cota, em `referencia`).
- **Tempo** (medido daqui, contra a fonte real): cada CSV tem 1,2 a 1,5 GB e sai a ~0,9 MB/s; ler 2026 inteiro levou 1.414 s, mais que o prazo de 25 min do job. Por isso a leitura é retomável: com o prazo esgotado, a posição em bytes e as linhas já achadas ficam em `parcial_<ano>.json`, e a coleta seguinte continua com `Range` (do zero: 25 min e 1,07 GB lidos; com o parcial: 2026 terminou em ~4 min). Com cache, o ano só é baixado de novo quando o `last_modified` do recurso no CKAN muda (`recursoModificadoEm`); anos anteriores ao passado não são relidos, e o ano passado só até março. Cada mudança no CSV do ano corrente custa ~23 min.
- **Cobertura:** 26 dos 30 favorecidos da cota em 2026 ligados aos eleitos; suplentes em exercício ficam de fora (não estão nos eleitos do TSE).

## Despesa da função Legislativa dos estados (DCA do SICONFI, 2026-10-29)
- **De onde:** `https://apidatalake.tesouro.gov.br/ords/siconfi/tt/dca` (Declaração de Contas Anuais, Anexo I-E, despesa por função), sem chave. Listada em `ENDPOINTS.md` (`siconfi_dca`).
- **Como:** `scripts/coletar_siconfi.py` passou a gravar, em cada ano de `dados/siconfi/<UF>.json`, `legislativa` com despesa empenhada, liquidada e paga da função 01 (Legislativa) e das subfunções 01.031 (Ação Legislativa, a Assembleia) e 01.032 (Controle Externo, o Tribunal de Contas). A DCA sai depois do fim do ano, então o ano corrente fica sem. Ano encerrado só é guardado como cache se já tiver `legislativa`. Medido contra a API real: SP 2024, ação legislativa liquidada de R$ 1,16 bi.
- **Cobertura:** só os 27 entes estaduais; Câmaras Municipais (uma consulta por município) ficam para depois. `gerar_politicos.custo_assembleia` divide a Ação Legislativa liquidada do último ano com DCA pelas cadeiras (eleitos de 2022) e grava em `perfil_casas/<UF>.json` (`estadual.custo`); o mapa mostra "Custo da Casa" acima do perfil dos eleitos, com link para a consulta.

## Despesa das Câmaras Municipais (DCA do SICONFI, 2026-10-29)

- **Fonte:** `https://apidatalake.tesouro.gov.br/ords/siconfi/tt/dca?an_exercicio=<ano>&no_anexo=DCA-Anexo%20I-E&id_ente=<IBGE do município>`, sem chave (mesmo endpoint da DCA dos estados, `ENDPOINTS.md`).
- **Como:** `scripts/coletar_siconfi_municipios.py` faz uma consulta por município (5.570, 4 simultâneas) e grava a Ação Legislativa (01.031: empenhada, liquidada, paga) e a população em `dados/siconfi_municipios/<UF>.json`, só do último ano com DCA publicada (2025, descoberto pela consulta de São Paulo). Incremental: o que já foi lido não é consultado de novo; município sem DCA é retentado após 30 dias; ano novo recomeça o arquivo. Prazo `ESTADUAIS_PRAZO_MIN` (25 min) no job `siconfi`, que guarda o lido e continua no dia seguinte. Medido contra a API real: AP, 16 municípios em 7 s (~0,5 s por município com 4 em paralelo, ~45 min para o Brasil).
- **Uso:** `gerar_politicos.custo_camara_municipal` divide a liquidada pelas vereadoras e vereadores eleitos em 2024 e grava `custo` em `perfil_casas/<UF>.json` (`municipal.<código TSE>`); o mapa mostra "Custo da Casa" no perfil da Câmara Municipal, com link para a consulta. Das prefeituras que entregaram a DCA; sem ela, nada aparece.

## Despesa com pessoal e limites da LRF por Poder (SICONFI, 2026-10-23)
- **De onde:** API de dados abertos do Tesouro Nacional, `https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rgf` (Relatório de Gestão Fiscal, Anexo 01), sem chave. Listada em `ENDPOINTS.md` (`siconfi_rgf`).
- **Como:** `scripts/coletar_siconfi.py` lê, para cada um dos 27 entes (`id_ente` = código IBGE da UF) e cada ano desde 2023, o Poder Legislativo (`co_poder=L`: Assembleia ou Câmara Legislativa) e o Executivo (`E`), no último período publicado do ano (3.º, 2.º ou 1.º quadrimestre; semestral se o ente optou). Grava `dados/siconfi/<UF>.json` com despesa bruta e líquida com pessoal, receita corrente líquida, DTP e % da RCL, e limites máximo, prudencial e de alerta; `fonte` por linha é a consulta à API. Anos encerrados não são baixados de novo. Job próprio `siconfi` em `atualizar.yml`.
- **Cobertura:** dado da instituição (a Assembleia como um todo), não de cada deputado; inclui AP, DF, ES e MA, cujas Assembleias não respondem a nenhum coletor próprio. Ainda não é mostrado no site.

## Coleta incremental das Assembleias de GO, PE e PR (2026-10-22)
- **De onde:** as mesmas fontes (API de transparência da Alego, portal e dados abertos da ALEPE, transparência e webservices da ALEP), sem endpoint novo.
- **Como:** os coletores passam a seguir o padrão dos outros estados (`estaduais_comum.meses_recentes` e `ano_encerrado`): anos anteriores ao passado com arquivo gravado não são baixados de novo, e nos outros só os meses que faltam no arquivo e os 2 últimos (`MESES_RECENTES`) são relidos. GO: verba e remuneração por mês; votações de anos encerrados vêm do `votacoes.json` anterior. GO também lê a remuneração só a partir de 2026 (a API devolve vazio antes) e só abre a ficha de quem não tem nome civil no `deputados.json` anterior. PR: proposições e diárias deixam de refazer 2023 e 2024 todo dia; diárias guardam `mes` e releem só os meses recentes; presença lê só o ano passado e o corrente; o último mês da remuneração (um POST por deputado) é relido uma vez por semana (`ultimoMesLidoEm`), não todo dia. PE: a verba de anos encerrados não é mais consultada deputado a deputado; se o portal da ALEPE recusar conexão (como no Actions de 2026-10-22), usa a lista de deputados anterior, pula a verba e segue com as proposições dos dados abertos.
- **Tempo com cache** (medido daqui, contra as fontes reais): GO 328 s → 157 s (sobram as diárias, consultadas por deputado: ~135 s); PR 281 s → 12 s (276 s no dia da semana em que relê a remuneração); PE 58 s → 43 s. A primeira execução depois da mudança relê uma vez os meses das diárias do PR (os itens antigos não têm `mes`).

## Assembleias estaduais fora do SAPL: BA, CE, GO, MG, MS, MT, PA, PE, PR, RJ, RN, RR, RS, SC, SE e SP (2026-10-22)
- **De onde:** um portal por UF, todos listados em `ENDPOINTS.md` (grupo "Assembleias (estaduais)"): ALBA, Alece, Alego (portal e API de transparência), ALMG (dados abertos), ALEMS (CEAP em CSV), ALMT (API Elotech), ALEPA (frequência, painéis Quartertec e SIGEP), ALEPE (dados abertos e transparência), ALEP (webservices e transparência), ALERJ (planilha de emendas e Ordem do Dia), ALRN (Transparência Legislativa), ALERR (WordPress), RS (CKAN `dados.rs.gov.br`, diárias), ALESC (CSV e e-Legis), Alese (carrossel) e ALESP (repositório de dados abertos e API de presença).
- **Como:** `scripts/coletar_estadual_<uf>.py`, um por UF, descobertos por `scripts/coletar_estaduais.py` (`python scripts/coletar_estaduais.py <UF>`); cache em `dados/estaduais/<UF>/` e coleta incremental (anos encerrados e meses antigos não são baixados de novo). Cada UF tem um job próprio na matriz `estaduais` de `.github/workflows/atualizar.yml`, com prazo de 25 min por coletor. Amostras reais em `tests/fixtures/contratos/`. Sem coletor: AP, DF e MA (sites sem resposta desta rede); ES, RS e SE só têm o que as fontes abertas dão (diárias; lista de deputados).
- **No site:** `gerar_estaduais.py` junta ao deputado estadual verba, remuneração, presença, diárias e emendas (cada bloco com `fonte`), mostrados no Perfil do deputado; projetos e votações passam a levar o link de `fonte` de cada item. O que cada UF tem e o que ficou de fora está em `LEVANTAMENTO_DADOS.md`.

## Cache de detalhes das proposições da BA (2026-10-22)
- **De onde:** as mesmas páginas da ALBA (`.../atividade-legislativa-nova/proposicao/<slug>`), sem endpoint novo.
- **Como:** cada `materias_<ano>.json` da BA ganhou `vistas` ({proposição: dia em que o detalhe foi lido}), inclusive das que não são de deputado, que antes eram baixadas de novo todo dia. Anos encerrados leem cada detalhe uma vez; o ano corrente relê cada proposição a cada 7 a 20 dias (escalonado por proposição). A primeira execução depois da mudança relê o que não é de deputado, uma vez.

## Coleta incremental das proposições de MG e RN (2026-10-22)
- **De onde:** a mesma API da ALMG (`.../api/v2/proposicoes/pesquisa/direcionada`), agora com `ord=3` (lista da última ação mais recente para a mais antiga, campo `dataUltimaAcao`); no RN, a lista de processos por iniciativa, que já vem da mais nova para a mais antiga.
- **Como:** o job de MG levava mais de 25 min porque refazia 2025 e 2026 inteiros (centenas de páginas, 1 s de pausa cada) todo dia. Agora a coleta diária lê só as páginas até a data da coleta anterior (MG) ou só os projetos entrados desde então (RN) e junta com o que já está em `materias_<ano>.json`. Os arquivos ganharam o campo `completaEm`; a releitura completa se repete a cada 14 dias (`RENOVAR_COMPLETA_DIAS`), e também quando falta algum arquivo de ano. No RN, arquivamentos de projetos antigos só aparecem nessa releitura completa.

## Blocos, votações do projeto e presença em eventos (2026-10-22)
- **De onde:** `https://dadosabertos.camara.leg.br/api/v2/blocos?idLegislatura=57` e `/blocos/{id}/partidos` (8 chamadas); `.../arquivos/votacoesProposicoes/json/votacoesProposicoes-<ano>.json` (um por ano desde 2023, ~7 MB); `.../arquivos/eventosPresencaDeputados/json/eventosPresencaDeputados-<ano>.json` (~30 MB por ano) e `.../arquivos/eventos/json/eventos-<ano>.json` (~1,5 MB), que dá o tipo de cada evento.
- **Como:** `coletar_blocos`, `coletar_votacoes_proposicoes` e `coletar_presenca_eventos` (`scripts/coletar.py`, no passo das proposições) gravam `dados/blocos.json`, `dados/proposicoes_votacoes.json` ({id do projeto: votações}, só projetos dos deputados) e `dados/presenca_eventos.json` ({ano: {sessoesDeliberativas, deputados: {id: {sessoes, comissoes, outros}}}}), todos no git. Anos encerrados da presença não são baixados de novo. As votações de cada projeto vêm do arquivo anual no lugar de `/proposicoes/{id}/votacoes` (uma chamada por projeto). O `atualizar.yml` passou a empacotar e commitar também `proposicoes_temas.json`, `orgaos_deputados.json` e `orientacoes.json`, que ficavam de fora.
- **No site:** (1) fidelidade dos partidos de bloco: o rótulo truncado ("Bl UniPpPsd...") é ligado ao bloco da legislatura cujas siglas, na ordem do nome, consomem o rótulo inteiro; deputados do MDB, PSD, União, PP etc. passam a ter fidelidade. Usa a composição atual dos blocos; rótulos de blocos que não existem em `/blocos` (como "Bl PlFdrPtUniPp...") e os ambíguos continuam sem correspondência. A federação truncada ("Fdr PSDB-CIDADAN") também passou a casar. (2) Bloco "Presença em sessões e reuniões" no perfil do deputado, por ano: sessões deliberativas do Plenário com o total do ano e a mediana dos deputados, reuniões de comissão e audiências, outros eventos. Reuniões e audiências não têm total para comparar (dependem das comissões do deputado). (3) Em cada projeto da aba Propostas, a lista das votações (até 8, as mais recentes): as nominais com resultado, orientação de cada bancada e link para a página da votação; as demais com link para a API.

## Orientação de bancada nas votações (2026-10-22)
- **De onde:** `https://dadosabertos.camara.leg.br/arquivos/votacoesOrientacoes/json/votacoesOrientacoes-<ano>.json` (um por ano com votações nominais guardadas; ~0,7 MB em 2026).
- **Como:** `coletar_orientacoes` (`scripts/coletar.py`, no passo das proposições) grava `dados/orientacoes.json` ({id da votação: {bancada: orientação}}), só das votações nominais já guardadas e sem orientações em branco; no git.
- **No site:** bloco "Fidelidade ao partido e ao governo" no perfil do deputado (percentual de votos iguais à orientação, com as votações em que divergiu), colunas "Fiel ao partido" e "Pró-governo" e as duas ordenações na lista de deputados. Usa o partido atual do deputado; a bancada do partido é a sigla ou a federação ("Fdr ..."). Partidos de bloco ("Bl ...", nome truncado pela Câmara) ficam sem fidelidade, só com governismo. "Liberado" não conta.

## Perfil temático do deputado (2026-10-22)
- **De onde:** `https://dadosabertos.camara.leg.br/arquivos/proposicoesTemas/json/proposicoesTemas-<ano>.json` (um por ano desde 2023, ~10 MB cada), `.../arquivos/orgaosDeputados/json/orgaosDeputados-L57.json` (~8 MB) e `https://dadosabertos.camara.leg.br/api/v2/deputados/{id}/frentes` (1 chamada por deputado, só a legislatura 57; o arquivo `frentesDeputados.json` tem ~150 MB).
- **Como:** `coletar_temas_proposicoes` grava `dados/proposicoes_temas.json` ({id do projeto: temas}, só tipos de projeto) e `coletar_orgaos_deputados` grava `dados/orgaos_deputados.json`, ambos no passo das proposições de `scripts/coletar.py`, no git; `coletar_deputado` guarda `frentes` no cache do deputado.
- **No site:** bloco "Em que áreas atua" no perfil do deputado (temas dos projetos com aprovados e autoria, comissões e órgãos, frentes), tema oficial em cada projeto e filtro por tema na aba Propostas. A ligação "projetos na área da comissão" ficou de fora: a Câmara não publica qual tema corresponde a cada comissão.

## Cota da Câmara pelo CSV anual (2026-10-22)
- **De onde:** `https://www.camara.leg.br/cotas/Ano-<ano>.csv.zip` (~4 MB, todos os deputados do ano, UTF-8, separador `;`).
- **Como:** `coletar_cota_csv` (`scripts/coletar.py`) baixa o arquivo uma vez por execução e `coletar_deputado` usa as despesas dele no lugar de `/deputados/{id}/despesas` (1 chamada a menos por deputado). Se o download falhar, volta para a API. Cada despesa ganhou o campo `cnpj` (só dígitos; a API também o traz, em `cnpjCpfFornecedor`).
- **No site:** página `fornecedores.html` (`site/dados/fornecedores_cota.json`, gerado por `ranking_fornecedores` em `scripts/gerar.py`): os 200 fornecedores que mais receberam, ligados pelo CNPJ/CPF, com quantos deputados os usam e os que mais gastaram com cada um.

## Nível 1 das futuras implementações (2026-10-22)
Só reaproveita dados que já eram coletados, mais três fontes de consulta e um campo novo:
- **Limite mensal da cota por UF:** tabela fixa em `scripts/gerar.py` (`LIMITE_COTA_UF`), copiada de https://www2.camara.leg.br/comunicacao/assessoria-de-imprensa/guia-para-jornalistas/cota-parlamentar (a página não data a tabela; conferida em 2026-10-22). Se a Câmara mudar o limite, atualize a tabela.
- **Subsídio:** constante no `app.js` (R$ 46.366,19, 4ª etapa em 1/2/2025 do Decreto Legislativo 172/2022: https://www2.camara.leg.br/legin/fed/decleg/2022/decretolegislativo-172-21-dezembro-2022-793529-republicacao-166629-pl.html) e tetos de deputado estadual e vereador pela Constituição (arts. 27 e 29).
- **Apensados e substitutos:** `coletar_detalhes_proposicoes` passou a guardar também `apensadoA`, `anterior` e `posterior` (ids tirados de `uriPropPrincipal`, `uriPropAnterior` e `uriPropPosterior` da mesma chamada a `/proposicoes/{id}`; nenhuma chamada nova). Projetos já finalizados no cache só ganham o campo se forem consultados de novo.
- **Gerados sem coleta nova:** autoria por deputado, maiores notas da cota, média do estado, comparação do custo do voto, evolução do patrimônio (eleições ligadas por nome e data de nascimento), perfil dos eleitos de cada Casa (`site/dados/perfil_casas/<UF>.json`) e presença dos senadores.

## Recursos e benefícios do senador (2026-10-22)
- **De onde:** `https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/{cod}/recursos-utilizados?ano=<ano>` (1 chamada por senador em exercício) e `.../senadores/escritorios-apoio` (1 chamada).
- **Como:** `coletar_recursos_senado` (`scripts/coletar.py`), no passo do Senado; grava `dados/senado_recursos.json`, fora do git como a CEAPS. Os escritórios são ligados ao senador por nome sem acento e UF.
- **No site:** bloco "Recursos e benefícios" no perfil do senador (benefícios, pessoal, gastos fora da cota, escritórios). O auxílio-moradia e o imóvel funcional vêm do próprio `recursos-utilizados`, então `auxilio-moradia-imoveis-funcionais` não foi coletado. Aposentados do Senado (`aposentados*`) ficaram de fora: não há perfil de ex-senador.

## Coletas em paralelo (2026-10-22)
O `atualizar.yml` passou de um job sequencial (~20 min) para jobs paralelos: Câmara, Senado, TSE, Executivo, Assembleias, governadores e prefeituras coletam ao mesmo tempo; o job `publicar` junta os pacotes (`scripts/empacotar.sh`), gera o site, salva no git e publica.
Câmara, Senado e TSE são indispensáveis; as outras coletas falham sem impedir a publicação.
Todas as coletas continuam diárias: o "Fique informado" (página, RSS e avisos) depende delas.
Concorrência: Câmara de 6 para 10 requisições em paralelo (`CAMARA_TRABALHADORES`; o Senado segue com 2), e as UFs de Assembleias, governadores e prefeituras são coletadas 4 de cada vez.

## Nomes dos campos (2026-10-21)
Todos os campos dos JSON de `dados/` e `site/dados/` passaram a ter nome por extenso (antes eram siglas de uma ou duas letras, como `sit`, `ap`, `td`, `dep`, `sq`, `ue`).
Os arquivos já commitados foram convertidos de uma vez; o conteúdo não mudou. Exemplos: `sit` → `situacao`, `ap` → `dataApresentacao`, `td` → `tipoDescricao`,
`pdf` → `linkTexto`, `dep` → `idsDeputados`, `sq` → `sequencial`, `ue` → `unidadeEleitoral`, `r`/`d`/`p` da prestação de contas → `receitas`/`despesasContratadas`/`despesasPagas`.
Regra daqui para frente: nenhum campo novo com sigla ou letra solta. `scripts/nomes_legados.py` converte os nomes antigos quando o histórico e o resumo por e-mail
comparam um commit anterior a esta mudança; pode ser apagado depois do primeiro dia comparado só com os nomes novos.
Ficam como estavam, por serem padrão de fora ou protocolo: `uf`, `id`, os campos `n` e `e` da chave pública (JWK, RFC 7517) e as colunas do fluxo de assinaturas.

## Conjuntos já no projeto

### TSE: eleitos, bens, votos, fotos e redes (`dados/tse/<ano>/<UF>.json`)
- **Entrada:** 2022, 2024 e 2026 em 2026-10-17; 2018 (só senadores) em 2026-10-18.
- **De onde:** `https://cdn.tse.jus.br/estatistica/sead/odsele/` (portal https://dadosabertos.tse.jus.br):
  - `consulta_cand/consulta_cand_<ano>.zip` (candidatos e situação)
  - `bem_candidato/bem_candidato_<ano>.zip` (bens declarados)
  - `votacao_candidato_munzona/votacao_candidato_munzona_<ano>.zip` (votos)
  - `consulta_cand/rede_social_candidato_<ano>.zip` (redes sociais; 2022 é um ZIP por UF: `_<UF>.zip`)
  - `https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes<ano>/fotos/foto_cand<ano>_<UF>_div.zip` (fotos, só cargos estaduais e federais; salvas em `site/fotos/<ano>/`)
- **2026-10-21:** removido o campo `reeleicao`: a coluna `ST_REELEICAO` não existe nos arquivos do TSE (2018 a 2026), e o campo ficava sempre falso.
- **Como:** `python scripts/coletar_tse.py` baixa o ZIP por HTTP (requests, streaming) para um arquivo temporário, lê o CSV de dentro, guarda só os eleitos e as colunas usadas e grava um JSON por UF. Anos encerrados são baixados uma vez só; 2026 (em andamento) é refeito a cada 2 dias.

### Câmara dos Deputados: deputados, votações, proposições, despesas (`dados/votacoes/`, `dados/proposicoes/`, `dados/proposicoes_detalhe.json`)
- **Entrada:** 2026-10-17 (os que vão para o git; `dados/deputados*` é refeito a cada execução e fica fora do git).
- **De onde:** API de Dados Abertos da Câmara, `https://dadosabertos.camara.leg.br/api/v2` (documentação: https://dadosabertos.camara.leg.br/swagger/api.html).
- **Como:** `python scripts/coletar.py`, chamadas HTTP JSON paginadas com repetição automática; o histórico de votações cresce a cada execução (continua de onde parou).

### Câmara: autores de cada projeto e ordem de assinatura (`dados/proposicoes_autores.json`)
- **Entrada:** 2026-10-21.
- **De onde:** API da Câmara, `https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id}/autores` (nome, tipo, `ordemAssinatura`, `proponente` e a `uri` do deputado).
- **Como:** `python scripts/coletar.py` (etapa `coletar_autores_proposicoes`), uma chamada por projeto (PL, PLP, PEC, PDL, PRC, PLV, MPV etc.; requerimentos, emendas e pareceres ficam de fora), sem repetir proposições compartilhadas por vários deputados. Guarda `{id: {"p": id do deputado que assinou primeiro, "a": [[id do deputado, nome], ...]}}`; autores que não são deputados (Executivo, Senado, comissões) entram com id nulo e o `tipo` da Câmara (ex.: "Órgão do Poder Executivo"). O site também mostra o total de autores, de quantos partidos (partido atual dos deputados em exercício) e a iniciativa quando o autor principal não é deputado. Autoria não muda, então cada projeto é consultado uma vez só. Como são ~20 mil projetos, cada execução consulta no máximo 6.000 (variável `AUTORES_POR_EXECUCAO`), dos mais novos para os mais antigos; o arquivo se completa em poucos dias. A aba Propostas mostra "autor principal" ou "coautor" assim que a proposição é coletada.

### Senado: votações, matérias e gastos CEAPS (`dados/senado_votacoes/`, `dados/senado_materias.json`)
- **Entrada:** 2026-10-17 (votações e matérias). CEAPS e autorias (`dados/senado_ceaps.json`, `dados/senado_autorias.json`) entraram na versão de 2026-10-18 e não vão para o git (baixados de novo a cada execução).
- **De onde:** `https://legis.senado.leg.br/dadosabertos` (senadores: `/senador/lista/atual`; votações: `/votacao`; autorias e situação das matérias: `/processo?codigoParlamentarAutor=`) e `https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/despesas_ceaps/<ano>` (CEAPS).
- **Como:** `python scripts/coletar.py` (mesmo script da Câmara, etapas do Senado), API JSON.
- **2026-10-21, migração:** os endpoints `/plenario/votacao/nominal/{ano}`, `/senador/{codigo}/autorias` e `/materia/{codigo}`, desativados pelo Senado em 2026-02-01, foram trocados por `/votacao` e `/processo` (histórico no README, seção "Endpoints desativados"). `dados/senado_materias.json` passa a ter `sit`, `data`, `ap` e `proc` vindos do `/processo` (antes `sit` ficava sempre vazio); os votos já salvos foram reclassificados pelo rótulo original ("Presente – Não registrou voto", "Atividade parlamentar" e "Dispositivo não citado" deixam de contar como voto).
- **2026-10-21, votos secretos e placar oficial:** o rótulo "Votou" (votação secreta) deixa de ser "outro" e vira o tipo próprio `secreto`; cada votação passa a guardar `secreta` (campo `votacaoSecreta`), `totais` (placar oficial `totalVotosSim/Nao/Abstencao`, quando a API informa), `sessao` e `processo`. O site usa o placar oficial quando existe, marca votação secreta e ementa não informada, e mostra sessão e ausências. Arquivos antigos são consultados de novo na próxima coleta.

### Presidente: projetos e MPs enviados ao Congresso (`dados/executivo.json`)
- **Entrada:** 2026-10-17.
- **De onde:** API da Câmara (`https://dadosabertos.camara.leg.br/api/v2`), proposições PL, PLP, PEC e MPV de autoria do Presidente desde 2023, com a situação (sancionado, vetado, em tramitação…).
- **Como:** `python scripts/coletar_executivo.py`.
- **2026-10-21, o que o presidente fez em cada item:** lendo a tramitação (`/proposicoes/{id}/tramitacoes`), cada proposição sancionada, vetada ou aguardando sanção passa a guardar `remessa` (data em que o Congresso mandou à sanção), `razoes` e `msc` (onde o DOU publicou as razões do veto e a mensagem do veto) e, nas MPs convertidas, `edicao`; `t: 1` marca a tramitação já lida. A página do político usa isso para mostrar, passo a passo, quem fez o quê.

### Assembleias Legislativas: deputados, projetos e votos nominais (`dados/estaduais/<UF>/`)
- **Entrada:** 2026-10-17, para AC, AL, AM, PB, PI, RO e TO (Assembleias que usam o SAPL do Interlegis).
- **De onde:** API REST do SAPL de cada Assembleia, `https://sapl.al.<uf>.leg.br/api/` (hosts em `ASSEMBLEIAS`, em `scripts/coletar_estaduais.py`).
- **Como:** `python scripts/coletar_estaduais.py` (deputados, matérias de 2023 em diante, votações). Projetos de anos anteriores são consultados de novo só a cada 7 dias.

### Governadores: projetos, vetos e mensagens enviados à Assembleia (`dados/estaduais/<UF>/governo_<ano>.json`)
- **Entrada:** 2026-10-17 (mesmas Assembleias acima).
- **De onde:** SAPL de cada Assembleia, matérias cujo autor é o Governador/Poder Executivo.
- **Como:** `python scripts/coletar_governadores.py`.

### Prefeitos de capitais: projetos enviados à Câmara Municipal (`dados/municipais/<UF>/prefeitura_<ano>.json`)
- **Entrada:** 2026-10-18 (2025 e 2026), para Rio Branco (AC), Boa Vista (RR), Natal (RN), João Pessoa (PB), São Paulo, Salvador e Goiânia.
- **De onde e como:**
  - AC, RR, RN, PB: SAPL da Câmara Municipal, `python scripts/coletar_prefeituras.py`.
  - SP: webservice do SPLegis, `https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx`, `python scripts/coletar_prefeitura_sp.py`.
  - BA (Salvador): grade Scriptcase `https://cmsalvador.sys.inf.br/cl/prop_interna/`, `python scripts/coletar_prefeitura_ba.py`.
  - GO (Goiânia): consulta pública do SUAP `https://suap.camaragyn.go.gov.br/camara/consulta_publica/`, `python scripts/coletar_prefeitura_go.py` (usa os certificados em `scripts/certs/`).
- **Capitais sem coletor e o motivo:** `dados/municipais/capitais_sem_dados.md`.

### Mapas e códigos de municípios
- `dados/municipios_ibge.json` (código TSE do município → código IBGE), refeito em 2026-10-18 com `python scripts/gerar_municipios_ibge.py --gravar`. Nomes e códigos do TSE: `detalhe_votacao_munzona_<ano>.zip` (https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_munzona/), 2024 e 2022 (o DF só tem eleição geral). Códigos do IBGE: API de localidades, https://servicodados.ibge.gov.br/api/v1/localidades/municipios. Ligação por UF + nome sem acento, com 14 grafias ajustadas à mão no script (ex.: Camacã/Camacan, Boa Saúde/Januário Cicco). A versão antiga, sem fonte, tinha 7 códigos trocados entre vizinhos (Lagoa Real, Laje, Lajedão, Lajedinho e Lajedo do Tabocal na BA; Santiago do Sul e Santa Terezinha do Progresso em SC) e não tinha Boa Esperança do Norte (MT, criado depois); o mapa pintava esses municípios errado.
- Malhas do mapa do Brasil: carregadas pelo navegador direto da API do IBGE, `https://servicodados.ibge.gov.br/api/v3/malhas` (`site/assets/app.js`); nada fica salvo no projeto.
- `site/geo/df_ras.json` (Regiões Administrativas do DF), refeito em 2026-10-18 com `python scripts/simplificar_df.py` (sem argumento, baixa e simplifica). Fonte: camada `geonode:regioes_administrativas` do catálogo do IPE-DF, https://catalogo.ipe.df.gov.br/layers/geonode_data:geonode:regioes_administrativas (WFS: `https://catalogo.ipe.df.gov.br/geoserver/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=geonode:regioes_administrativas&outputFormat=application/json&srsName=EPSG:4326`). O resultado é idêntico ao arquivo anterior.

### TSE: prestação de contas de campanha (`dados/tse/contas/<ano>/<UF>.json`)
- **Entrada:** 2026-10-18, para os eleitos de 2022 (1.626) e 2024 (63.722). Aparece na aba "Quem o elegeu?".
- **De onde:** `https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_<ano>.zip` (arquivos `receitas_candidatos_<ano>_BRASIL.csv`, `receitas_candidatos_doador_originario_<ano>_BRASIL.csv` `despesas_contratadas_candidatos_<ano>_BRASIL.csv` e `despesas_pagas_candidatos_<ano>_BRASIL.csv`).
- **Como:** `python scripts/baixar_tse.py prestacao_contas` (ZIP em `dados/tse_bruto/`, fora do git) e depois `python scripts/coletar_contas.py`, que lê os CSV em streaming e guarda por eleito: total arrecadado, total contratado, receita por origem, 5 maiores doadores (só o nome, sem CPF) e 6 maiores tipos de gasto. 2026-10-18: passou a guardar também os 5 maiores doadores originários (só o nome) dos repasses de partido e de outros candidatos, ligando `SQ_RECEITA` do arquivo de doador originário à receita do candidato (feito a partir do ZIP já baixado, sem novo download). 2026-10-18: guarda também o total pago (`despesas_pagas_candidatos_<ano>_BRASIL.csv`, ligado ao candidato por `SQ_DESPESA`), mostrado só quando difere do contratado. Roda só localmente (anos encerrados não mudam); vice usa a prestação do titular da chapa.

### TSE: comparecimento e vagas (`dados/tse/disputa/<ano>/<UF>.json`)
- **Entrada:** 2026-10-18, eleições de 2022 e 2024. Aparece na aba "Quem o elegeu?".
- **De onde:** `https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_munzona/detalhe_votacao_munzona_<ano>.zip` (aptos, comparecimento, abstenções, brancos, nulos, votos válidos) e `.../consulta_vagas/consulta_vagas_<ano>.zip` (vagas).
- **Como:** `python scripts/baixar_tse.py detalhe_votacao_munzona consulta_vagas` e `python scripts/coletar_disputa.py`, que soma as zonas de cada cargo e local (o `*_BRASIL.csv` é ignorado porque repete os outros). Roda só localmente.

### TSE: onde cada eleito foi votado (`dados/tse/secoes/<ano>/<UF>.json`)
- **Entrada:** 2026-10-18, para os eleitos de 2022 e 2024. Aparece na aba "Quem o elegeu?", com mapa.
- **De onde:** `.../votacao_secao/votacao_secao_<ano>_<UF>.zip` (votos por seção; `_BR` para presidente em 2022) e `.../eleitorado_locais_votacao/eleitorado_local_votacao_<ano>.zip` (latitude e longitude dos locais de votação). O mapa usa Leaflet (cdnjs) e blocos do OpenStreetMap, carregados pelo navegador.
- **Como:** `python scripts/baixar_tse.py votacao_secao eleitorado_locais_votacao` e `python scripts/coletar_secoes.py` (uns 4 min por ano). Guarda por eleito os principais locais (5 para vereador, 10 nos demais) e, nos cargos estaduais e federais, os 10 municípios com mais votos. 2026-10-18: nesses cargos (menos presidente) guarda também os votos em todos os municípios (`mp`, código TSE), refeito dos ZIPs já baixados, para o mapa colorido por município; as malhas vêm da API do IBGE no navegador e o código TSE→IBGE de `dados/municipios_ibge.json`. Roda só localmente.

### TSE: perfil do eleitorado (`dados/tse/eleitorado/<ano>/<UF>.json`)
- **Entrada:** 2026-10-18, 2022 e 2024. Aparece na página inicial, abaixo da contagem, ao escolher um estado ou município (o ano mais recente que o estado tem: 2024; o DF só tem 2022).
- **De onde:** `https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitorado/perfil_eleitorado_<ano>.zip` (colunas iguais nos dois anos).
- **Como:** `python scripts/baixar_tse.py perfil_eleitorado` e `python scripts/coletar_eleitorado.py` (1 min), que soma os eleitores por município (`CD_MUNICIPIO`, o código TSE) e por estado em gênero, 8 faixas etárias e 8 graus de escolaridade. `ZZ` (exterior) fica guardado, mas o site não o mostra. Roda só localmente.

### TSE: votos do partido (`dados/tse/partidos/<ano>/<UF>.json`)
- **Entrada:** 2026-10-18, 2022 e 2024, cargos proporcionais (deputados e vereadores). Aparece na aba "Quem o elegeu?", depois de "Comparecimento e vagas".
- **De onde:** `https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_partido_munzona/votacao_partido_munzona_<ano>.zip` (colunas iguais nos dois anos; 2022 tem 4 colunas a mais de coligação que não usamos).
- **Como:** `python scripts/baixar_tse.py votacao_partido_munzona` e `python scripts/coletar_partidos.py`, que soma as zonas por cargo, local e partido: votos de legenda (`QT_TOTAL_VOTOS_LEG_VALIDOS`), nominais (`QT_VOTOS_NOMINAIS_VALIDOS`) e a federação. O quociente eleitoral mostrado é votos válidos dos partidos ÷ vagas (vagas de `consulta_vagas`). Roda só localmente.

### TSE: coligações e federações (`dados/tse/coligacoes/<ano>/<UF>.json`)
- **Entrada:** 2026-10-18, 2022 e 2024. Aparece na aba "Quem o elegeu?" como "Alianças do partido", depois de "Votos do partido".
- **De onde:** `https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_coligacao/consulta_coligacao_<ano>.zip` (colunas iguais nos dois anos).
- **Como:** `python scripts/baixar_tse.py consulta_coligacao` e `python scripts/coletar_coligacoes.py`, que guarda tipo (coligação, federação ou partido isolado), nome, partidos e situação da legenda. Só guarda o partido de quem foi eleito (lê `dados/tse/<ano>/<UF>.json`), por isso precisa rodar depois de `coletar_tse.py`; sem isso o arquivo de 2024 passa de 6 MB. Roda só localmente.

### Histórico diário (`dados/historico/AAAA-MM-DD.json`)
- **Fuso 2026-10-26:** horas das fontes sem offset (Câmara, Senado, Assembleias) são tratadas como `America/Sao_Paulo` (`scripts/fuso.py`, com `tzdata` no `requirements.txt`; vale também para o dia dos fatos do histórico). Votações ganharam `dataHora` (ISO com offset de Brasília), que o site mostra no fuso de quem abre; datas sem hora ficam como salvas.
- **Mudança 2026-10-26:** o dia de cada entrada passou a ser o dia dos fatos em Brasília (dia anterior à coleta de madrugada), não a data UTC do commit. Os arquivos, o índice e `ultimaMudanca` já gravados foram renomeados e deslocados 1 dia para trás (o antigo 2026-10-25 virou 2026-10-24). Cron da coleta: 07:47 UTC. Avisos semanais saem na segunda (segunda a domingo) e os mensais no dia 1 (mês completo).
- **Fuso do runner 2026-10-26:** `TZ=America/Sao_Paulo` no workflow `atualizar.yml`; o `date.today()` dos coletores segue o dia de Brasília, também em execução manual à noite.
- **Entrada:** 2026-10-21, com os dias 2026-10-19 a 2026-10-21 reconstruídos do git. O dia 2026-10-18 não entra: foi a carga inicial de várias fontes e tudo apareceria como novidade.
- **De onde:** não vem de fonte nova. É a diferença, dia a dia, dos conjuntos que já estão no git (Câmara, Senado, Presidência, Assembleias, governos, capitais e eleitos do TSE), lida no commit `Dados atualizados em AAAA-MM-DD`. Cada item guarda os links da fonte oficial: ficha de tramitação e API da Câmara, matéria no Senado, sistema legislativo (SAPL, SPLegis, Scriptcase, SUAP) da Assembleia ou Câmara Municipal e, no TSE, o portal de dados abertos e o arquivo usado.
- **Como:** `python scripts/historico.py` (no workflow, logo depois de salvar os dados do dia). Separa por local (Brasil, estado, capital) e, quando a fonte informa o autor, por político (deputados federais e estaduais, Presidente, governador, prefeito). Registra proposições novas de todos os tipos, mudança de situação só de projetos (PL, PLP, PEC, PDL, MPV…), votações do Plenário (Câmara e Senado) e nominais das Assembleias, matérias do Senado, projetos do Executivo e mudanças de situação ou partido dos eleitos do TSE (acima de 200 registros num arquivo, vira um evento só: é carga em lote). A primeira coleta de uma fonte não vira "novidade", e situação que estava vazia e foi preenchida pela coleta também não. Os arquivos ficam no git (o histórico só cresce) e são copiados para `site/dados/historico/` (`indice.json` lista os dias). A página `site/historico.html` lê esses arquivos; o resumo por e-mail e o RSS apontam para ela (`historico.html?dia=AAAA-MM-DD&locais=...`).

## Outros arquivos do TSE (ainda não usados no site)
Existem em `https://cdn.tse.jus.br/estatistica/sead/odsele/<pasta>/<arquivo>.zip`; URLs e tamanhos conferidos em 2026-10-18 (HTTP 200). Baixados com `python scripts/baixar_tse.py`, para `dados/tse_bruto/` (fora do git).

| Conjunto | Pasta / arquivo | 2022 | 2024 |
|---|---|---|---|
| Prestação de contas (receitas, despesas, doadores) | `prestacao_contas/prestacao_de_contas_eleitorais_candidatos_<ano>.zip` | 467 MB | 1,3 GB |
| Votos do partido por município/zona (já usado) | `votacao_partido_munzona/votacao_partido_munzona_<ano>.zip` | 26 MB | 6 MB |
| Votos por seção | `votacao_secao/votacao_secao_<ano>_<UF>.zip` (um por UF, `ZZ` = exterior; SP: 901 MB e 476 MB) | por UF | por UF |
| Perfil do eleitorado (já usado) | `perfil_eleitorado/perfil_eleitorado_<ano>.zip` | 77 MB | 334 MB |
| Comparecimento, brancos e nulos | `detalhe_votacao_munzona/detalhe_votacao_munzona_<ano>.zip` | 4 MB | 1,5 MB |
| Coligações (já usado) | `consulta_coligacao/consulta_coligacao_<ano>.zip` | 0,4 MB | 11 MB |
| Vagas | `consulta_vagas/consulta_vagas_<ano>.zip` | 0,2 MB | 0,6 MB |
| Motivo de cassação (só indeferimento de candidatura; pouco útil para eleitos) | `motivo_cassacao/motivo_cassacao_<ano>.zip` | 0,2 MB | 0,6 MB |

Filiação partidária e certidões criminais: não achadas em dadosabertos.tse.jus.br.

## Downloads do TSE (script `scripts/baixar_tse.py`)

- 2026-10-18 20:01: `dados/tse_bruto/consulta_vagas/consulta_vagas_2022.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_vagas/consulta_vagas_2022.zip (0.2 MB, sha256 `be65a63ef644c91e…`)
- 2026-10-18 20:01: `dados/tse_bruto/consulta_vagas/consulta_vagas_2024.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_vagas/consulta_vagas_2024.zip (0.6 MB, sha256 `6f2f45b872904672…`)
- 2026-10-18 20:01: `dados/tse_bruto/detalhe_votacao_munzona/detalhe_votacao_munzona_2022.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_munzona/detalhe_votacao_munzona_2022.zip (4.4 MB, sha256 `402c9983670e012c…`)
- 2026-10-18 20:01: `dados/tse_bruto/detalhe_votacao_munzona/detalhe_votacao_munzona_2024.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_munzona/detalhe_votacao_munzona_2024.zip (1.5 MB, sha256 `6ea9094561410ed0…`)
- 2026-10-18 20:01: `dados/tse_bruto/consulta_coligacao/consulta_coligacao_2022.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_coligacao/consulta_coligacao_2022.zip (0.4 MB, sha256 `26be7b36352cc037…`)
- 2026-10-18 20:01: `dados/tse_bruto/consulta_coligacao/consulta_coligacao_2024.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_coligacao/consulta_coligacao_2024.zip (11.0 MB, sha256 `32fdd73f469a4ebc…`)
- 2026-10-18 20:01: `dados/tse_bruto/motivo_cassacao/motivo_cassacao_2022.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/motivo_cassacao/motivo_cassacao_2022.zip (0.2 MB, sha256 `e4f0b5c061763e12…`)
- 2026-10-18 20:01: `dados/tse_bruto/motivo_cassacao/motivo_cassacao_2024.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/motivo_cassacao/motivo_cassacao_2024.zip (0.6 MB, sha256 `50519d09bb4219a5…`)
- 2026-10-18 20:02: `dados/tse_bruto/votacao_partido_munzona/votacao_partido_munzona_2022.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_partido_munzona/votacao_partido_munzona_2022.zip (26.3 MB, sha256 `ee46ca2c66389a20…`)
- 2026-10-18 20:02: `dados/tse_bruto/votacao_partido_munzona/votacao_partido_munzona_2024.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_partido_munzona/votacao_partido_munzona_2024.zip (6.2 MB, sha256 `2831f03711e379a6…`)
- 2026-10-18 20:32: `dados/tse_bruto/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2022.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2022.zip (467.3 MB, sha256 `21dc6069bb956379…`)
- 2026-10-18 20:51: `dados/tse_bruto/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2024.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2024.zip (1335.3 MB, sha256 `f0463d92d97a3323…`)
- 2026-10-18 20:53: `dados/tse_bruto/perfil_eleitorado/perfil_eleitorado_2022.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitorado/perfil_eleitorado_2022.zip (76.7 MB, sha256 `4bccad7e39ec13ea…`)
- 2026-10-18 20:53: `dados/tse_bruto/perfil_eleitorado/perfil_eleitorado_2024.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitorado/perfil_eleitorado_2024.zip (333.6 MB, sha256 `fd6703bdaa89aba0…`)
- 2026-10-18 20:53: `dados/tse_bruto/votacao_secao/votacao_secao_2022_AC.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_AC.zip (6.7 MB, sha256 `d17b815a4d6faa49…`)
- 2026-10-18 20:54: `dados/tse_bruto/votacao_secao/votacao_secao_2022_AL.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_AL.zip (30.3 MB, sha256 `d5ae3a20a8ecc32b…`)
- 2026-10-18 20:55: `dados/tse_bruto/votacao_secao/votacao_secao_2022_AM.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_AM.zip (44.0 MB, sha256 `1ba6c258320799f5…`)
- 2026-10-18 20:55: `dados/tse_bruto/votacao_secao/votacao_secao_2022_AP.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_AP.zip (7.3 MB, sha256 `e7f0c8836f5dcbb0…`)
- 2026-10-18 21:01: `dados/tse_bruto/votacao_secao/votacao_secao_2022_BA.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_BA.zip (191.5 MB, sha256 `54d397ff4b5a39d6…`)
- 2026-10-18 21:05: `dados/tse_bruto/votacao_secao/votacao_secao_2022_CE.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_CE.zip (111.5 MB, sha256 `47a8a151d4b51196…`)
- 2026-10-18 21:06: `dados/tse_bruto/votacao_secao/votacao_secao_2022_DF.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_DF.zip (34.3 MB, sha256 `eb9184e4927df556…`)
- 2026-10-18 21:06: `dados/tse_bruto/votacao_secao/votacao_secao_2022_ES.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_ES.zip (49.9 MB, sha256 `2c5dbd8fe808b1e4…`)
- 2026-10-18 21:06: `dados/tse_bruto/votacao_secao/votacao_secao_2022_GO.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_GO.zip (94.8 MB, sha256 `be46c92b743a95ad…`)
- 2026-10-18 21:06: `dados/tse_bruto/votacao_secao/votacao_secao_2022_MA.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_MA.zip (71.3 MB, sha256 `7422ee2870be969a…`)
- 2026-10-18 21:14: `dados/tse_bruto/votacao_secao/votacao_secao_2022_MG.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_MG.zip (295.1 MB, sha256 `e35b85dcc15fea43…`)
- 2026-10-18 21:15: `dados/tse_bruto/votacao_secao/votacao_secao_2022_MS.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_MS.zip (38.4 MB, sha256 `0e377349b066b24b…`)
- 2026-10-18 21:15: `dados/tse_bruto/votacao_secao/votacao_secao_2022_MT.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_MT.zip (34.6 MB, sha256 `371117d76ec7f115…`)
- 2026-10-18 21:15: `dados/tse_bruto/votacao_secao/votacao_secao_2022_PA.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_PA.zip (97.0 MB, sha256 `efec9371ca3e571e…`)
- 2026-10-18 21:15: `dados/tse_bruto/votacao_secao/votacao_secao_2022_PB.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_PB.zip (48.0 MB, sha256 `6918c138a450eb21…`)
- 2026-10-18 21:16: `dados/tse_bruto/votacao_secao/votacao_secao_2022_PE.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_PE.zip (122.2 MB, sha256 `058f042466913b54…`)
- 2026-10-18 21:16: `dados/tse_bruto/votacao_secao/votacao_secao_2022_PI.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_PI.zip (33.0 MB, sha256 `3883b3e9a67ce1b2…`)
- 2026-10-18 21:16: `dados/tse_bruto/votacao_secao/votacao_secao_2022_PR.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_PR.zip (161.0 MB, sha256 `67048a3c8d94b96c…`)
- 2026-10-18 21:16: `dados/tse_bruto/votacao_secao/votacao_secao_2022_RJ.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_RJ.zip (314.5 MB, sha256 `0adf67cbe0573691…`)
- 2026-10-18 21:16: `dados/tse_bruto/votacao_secao/votacao_secao_2022_RN.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_RN.zip (34.7 MB, sha256 `b211fba5ddfecf2c…`)
- 2026-10-18 21:16: `dados/tse_bruto/votacao_secao/votacao_secao_2022_RO.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_RO.zip (20.7 MB, sha256 `399bd2850ac81cd4…`)
- 2026-10-18 21:16: `dados/tse_bruto/votacao_secao/votacao_secao_2022_RR.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_RR.zip (7.7 MB, sha256 `66b18486f64797d2…`)
- 2026-10-18 21:16: `dados/tse_bruto/votacao_secao/votacao_secao_2022_RS.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_RS.zip (181.9 MB, sha256 `a6ca495c557673c7…`)
- 2026-10-18 21:16: `dados/tse_bruto/votacao_secao/votacao_secao_2022_SC.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_SC.zip (100.2 MB, sha256 `a658388c8b6094c1…`)
- 2026-10-18 21:16: `dados/tse_bruto/votacao_secao/votacao_secao_2022_SE.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_SE.zip (25.9 MB, sha256 `96530d4198fa97a3…`)
- 2026-10-18 21:17: `dados/tse_bruto/votacao_secao/votacao_secao_2022_SP.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_SP.zip (900.9 MB, sha256 `36c417ab6af3fc0a…`)
- 2026-10-18 21:17: `dados/tse_bruto/votacao_secao/votacao_secao_2022_TO.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_TO.zip (16.8 MB, sha256 `b2dedc70f6921376…`)
- 2026-10-18 21:17: `dados/tse_bruto/votacao_secao/votacao_secao_2024_AC.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_AC.zip (5.6 MB, sha256 `3505fe23101505e1…`)
- 2026-10-18 21:17: `dados/tse_bruto/votacao_secao/votacao_secao_2024_AL.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_AL.zip (17.4 MB, sha256 `cf102015682676e3…`)
- 2026-10-18 21:17: `dados/tse_bruto/votacao_secao/votacao_secao_2024_AM.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_AM.zip (34.1 MB, sha256 `b1f8db5148c81c3d…`)
- 2026-10-18 21:17: `dados/tse_bruto/votacao_secao/votacao_secao_2024_AP.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_AP.zip (5.1 MB, sha256 `4c23d90e011ab450…`)
- 2026-10-18 21:21: `dados/tse_bruto/votacao_secao/votacao_secao_2024_BA.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_BA.zip (114.0 MB, sha256 `2c3d1ad1ecf37c01…`)
- 2026-10-18 21:21: `dados/tse_bruto/votacao_secao/votacao_secao_2024_CE.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_CE.zip (69.5 MB, sha256 `9d5c2b1e7cab3556…`)
- 2026-10-18 21:21: `dados/tse_bruto/votacao_secao/votacao_secao_2024_ES.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_ES.zip (31.9 MB, sha256 `32fca0a59d860708…`)
- 2026-10-18 21:23: `dados/tse_bruto/votacao_secao/votacao_secao_2024_GO.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_GO.zip (64.4 MB, sha256 `ce2cae527a10de2b…`)
- 2026-10-18 21:23: `dados/tse_bruto/votacao_secao/votacao_secao_2024_MA.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_MA.zip (48.9 MB, sha256 `727ad9b99feb8ca1…`)
- 2026-10-18 21:26: `dados/tse_bruto/votacao_secao/votacao_secao_2024_MG.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_MG.zip (201.4 MB, sha256 `b305cb4783deac6e…`)
- 2026-10-18 21:26: `dados/tse_bruto/votacao_secao/votacao_secao_2024_MS.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_MS.zip (23.3 MB, sha256 `1dfa19396cba24bc…`)
- 2026-10-18 21:26: `dados/tse_bruto/votacao_secao/votacao_secao_2024_MT.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_MT.zip (26.1 MB, sha256 `4d84497edbd8944c…`)
- 2026-10-18 21:26: `dados/tse_bruto/votacao_secao/votacao_secao_2024_PA.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_PA.zip (71.5 MB, sha256 `3a9a65d48a49c09b…`)
- 2026-10-18 21:26: `dados/tse_bruto/votacao_secao/votacao_secao_2024_PB.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_PB.zip (28.1 MB, sha256 `a2005be05e2ee36d…`)
- 2026-10-18 21:26: `dados/tse_bruto/votacao_secao/votacao_secao_2024_PE.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_PE.zip (66.7 MB, sha256 `a0644bdade0339f8…`)
- 2026-10-18 21:26: `dados/tse_bruto/votacao_secao/votacao_secao_2024_PI.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_PI.zip (23.3 MB, sha256 `e5eed87c495c4cb5…`)
- 2026-10-18 21:28: `dados/tse_bruto/votacao_secao/votacao_secao_2024_PR.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_PR.zip (110.1 MB, sha256 `737233f15259d9cc…`)
- 2026-10-18 21:28: `dados/tse_bruto/votacao_secao/votacao_secao_2024_RJ.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_RJ.zip (156.8 MB, sha256 `c956615e39ecc4ab…`)
- 2026-10-18 21:28: `dados/tse_bruto/votacao_secao/votacao_secao_2024_RN.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_RN.zip (21.6 MB, sha256 `9f986702c2059b17…`)
- 2026-10-18 21:28: `dados/tse_bruto/votacao_secao/votacao_secao_2024_RO.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_RO.zip (12.7 MB, sha256 `31fcada6606bd4e5…`)
- 2026-10-18 21:28: `dados/tse_bruto/votacao_secao/votacao_secao_2024_RR.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_RR.zip (4.1 MB, sha256 `3f2e5dd34af80b99…`)
- 2026-10-18 21:28: `dados/tse_bruto/votacao_secao/votacao_secao_2024_RS.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_RS.zip (96.1 MB, sha256 `42167998705f965f…`)
- 2026-10-18 21:28: `dados/tse_bruto/votacao_secao/votacao_secao_2024_SC.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_SC.zip (53.8 MB, sha256 `36cd7aa412d81ec3…`)
- 2026-10-18 21:28: `dados/tse_bruto/votacao_secao/votacao_secao_2024_SE.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_SE.zip (15.6 MB, sha256 `06a51a88f213f4e1…`)
- 2026-10-18 21:35: `dados/tse_bruto/votacao_secao/votacao_secao_2024_SP.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_SP.zip (475.8 MB, sha256 `3d7063c453ca4d2e…`)
- 2026-10-18 21:35: `dados/tse_bruto/votacao_secao/votacao_secao_2024_TO.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_TO.zip (10.2 MB, sha256 `9258920a27193be8…`)
- 2026-10-18 22:23: `dados/tse_bruto/eleitorado_locais_votacao/eleitorado_local_votacao_2022.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/eleitorado_locais_votacao/eleitorado_local_votacao_2022.zip (24.0 MB, sha256 `6dc19c1ddb746cc0…`)
- 2026-10-18 22:23: `dados/tse_bruto/eleitorado_locais_votacao/eleitorado_local_votacao_2024.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/eleitorado_locais_votacao/eleitorado_local_votacao_2024.zip (45.3 MB, sha256 `352ea0731f862b8a…`)
- 2026-10-18 22:29: `dados/tse_bruto/votacao_secao/votacao_secao_2022_BR.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_BR.zip (271.3 MB, sha256 `9353993de5cf0377…`)
