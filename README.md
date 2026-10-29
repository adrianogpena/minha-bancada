<p align="center">
  <img src="docs/logo/logo.svg" alt="Minha Bancada" width="380">
</p>

Site estático com todos os políticos com mandato no Brasil, de vereador a presidente, e os eleitos de 2026. Para deputados federais, mostra também como votam, o que propõem e quanto gastam. Os dados vêm do [TSE](https://dadosabertos.tse.jus.br), da [Câmara](https://dadosabertos.camara.leg.br) e do [Senado](https://legis.senado.leg.br/dadosabertos) e são atualizados sozinhos todo dia.

**Site: https://adrianogpena.github.io/minha-bancada/**

**Custo: zero.** Tudo roda no GitHub: o GitHub Actions coleta os dados e o GitHub Pages hospeda o site.

## Como funciona

```
API da Câmara ──> scripts/coletar.py ──> dados/        (cache bruto; o histórico de votações fica no git)
                                         │
                  scripts/gerar.py  <────┘
                         │
                         └──> site/dados/  ──> GitHub Pages
```

O arquivo `.github/workflows/atualizar.yml` roda as duas etapas todo dia de madrugada (07:47 UTC, 04:47 em Brasília) e publica o resultado. Depois de salvar os dados do dia, na ordem:

1. `scripts/historico.py` registra tudo o que mudou, com fontes, em `dados/historico/` (página **Histórico** do site). O dia do histórico é o dia em que a coleta rodou, em Brasília (a coleta de 27/10 grava `2026-10-27.json`), e o arquivo guarda `coletaAnterior` e `coletaEm`, a hora em que cada execução começou de fato;
2. `scripts/feeds.py` atualiza os feeds RSS;
3. o site é publicado;
4. os e-mails saem (resumo ao dono e avisos aos assinantes). E-mail e RSS trazem só um resumo e o link para a página do dia no Histórico.

## Colocar no ar (uns 10 minutos)

1. Crie uma conta no [GitHub](https://github.com), se ainda não tiver.
2. Crie um repositório **público** chamado `minha-bancada` (ou o nome que preferir). Repositório público é o que deixa o Actions gratuito e ilimitado.
3. Envie os arquivos deste projeto para o repositório. O jeito mais simples, no computador:
   ```bash
   cd minha-bancada
   git init -b master
   git add .
   git commit -m "Primeira versão"
   git remote add origin https://github.com/SEU_USUARIO/minha-bancada.git
   git push -u origin master
   ```
   Se preferir pelo site do GitHub ("Add file" > "Upload files"), confira depois se a pasta `.github/workflows` subiu. Ela começa com ponto e alguns sistemas a escondem. Se não subiu, crie o arquivo pelo botão "Add file" > "Create new file", digitando o caminho `.github/workflows/atualizar.yml`, e cole o conteúdo.
4. No repositório, vá em **Settings > Pages** e, em "Source", escolha **GitHub Actions**.
5. Vá em **Settings > Actions > General** e confirme que "Workflow permissions" está em **Read and write permissions**.
6. Vá na aba **Actions**, abra "Atualizar dados e publicar site" e clique em **Run workflow**. A primeira coleta leva uns 15 a 30 minutos (são mais de 500 deputados).
7. Pronto: o site fica em `https://SEU_USUARIO.github.io/minha-bancada/`.

## Rodar no seu computador

Precisa de Python 3.10 ou mais novo.

```bash
pip install -r requirements.txt
python scripts/coletar.py --limite 20 --dias 30   # amostra rápida: 20 deputados, 30 dias
python scripts/coletar_tse.py --anos 2024           # eleitos municipais (baixa ~100 MB)
python scripts/gerar.py
python -m http.server 8000 -d site                # abra http://localhost:8000
```

### Testes

Os testes não acessam a internet: as respostas das APIs (Câmara, Senado, TSE, SAPL das Assembleias e Câmaras, SPLegis, Scriptcase e SUAP) são simuladas com o formato real de cada uma, e verificam a leitura, a normalização e o tratamento de falhas. Rodam em poucos segundos:

```bash
pip install -r requirements-dev.txt
python -m pytest                       # scripts de coleta/geração + sanidade dos arquivos em dados/
node --test tests/js/app.test.js       # módulos de site/assets/js
node --test tests/e2e/fumaca.test.js   # abre cada página no Chromium sobre dados mínimos (precisa de `npm i --no-save playwright`)
```

### Contrato das APIs externas

`tests/fixtures/contratos/` guarda respostas **reais** (reduzidas) da Câmara, Senado, TSE, SAPL e SPLegis, e os testes
rodam os coletores contra elas. O workflow `Contrato das APIs externas` (`.github/workflows/contratos.yml`) roda toda
segunda-feira, consulta as APIs de novo e compara com as amostras: se sumir ou mudar de tipo um campo que o código usa,
a execução falha e abre uma issue. Campos novos, respostas vazias e fontes fora do ar viram só avisos no resumo da execução.

```bash
python scripts/contrato_apis.py --verificar            # confere agora (usa a internet)
python scripts/contrato_apis.py --gravar [nome ...]    # regrava as amostras depois de ajustar um coletor
python scripts/contrato_apis.py --listar
```

Sem `--limite` a coleta pega todos os deputados em exercício. `--dias` só vale na primeira coleta; depois o script continua de onde parou.

## Estrutura

| Caminho | O que é |
|---|---|
| `scripts/coletar.py` | Baixa deputados, proposições, despesas e votações do Plenário (com o voto de cada um). |
| `scripts/coletar_tse.py` | Baixa do TSE os eleitos de 2022, 2024 e 2026, com bens declarados. Anos encerrados são baixados uma vez só. |
| `scripts/baixar_tse.py` | Baixa arquivos extras do TSE (prestação de contas, votos por seção, perfil do eleitorado…) para `dados/tse_bruto/` e registra no CHANGELOG. |
| `CHANGELOG.md` | De onde vem cada dado, quando entrou e como foi baixado. |
| `scripts/coletar_contas.py` | Resume a prestação de contas de campanha dos eleitos, incluindo os doadores originários por trás dos repasses de partido (rodar localmente, depois de `baixar_tse.py prestacao_contas`). |
| `scripts/coletar_disputa.py`, `scripts/coletar_secoes.py` | Resumem comparecimento/vagas e onde cada eleito foi votado (locais com coordenadas e votos por município, para o mapa), a partir dos arquivos baixados por `baixar_tse.py`. |
| `scripts/coletar_eleitorado.py` | Resume o perfil do eleitorado (total, gênero, faixa etária, escolaridade) de cada município e estado, a partir do arquivo baixado por `baixar_tse.py perfil_eleitorado`. |
| `scripts/coletar_partidos.py` | Resume os votos de legenda e nominais de cada partido (e federação) nos cargos proporcionais, a partir do arquivo baixado por `baixar_tse.py votacao_partido_munzona`. |
| `scripts/coletar_coligacoes.py` | Resume coligações, federações e a situação da legenda do partido de cada eleito, a partir do arquivo baixado por `baixar_tse.py consulta_coligacao` (rodar depois de `coletar_tse.py`). |
| `scripts/resumo_email.py` | Resumo do que mudou na execução diária, enviado por e-mail ao dono do projeto. |
| `scripts/assinaturas.py`, `scripts/gerar_chaves.py`, `assinaturas/` | Aviso por e-mail opcional do Fique informado, com o e-mail criptografado no navegador (só o robô diário tem a chave). Passo a passo em `assinaturas/LEIAME.md`. |
| `scripts/historico.py` | Histórico diário: compara os dados da coleta com os da anterior (pelo git; o arquivo leva a data do dia anterior à coleta, em Brasília) e grava em `dados/historico/AAAA-MM-DD.json` todos os detalhes, por local e por político, com a fonte de cada item. A página `site/historico.html` lê esses arquivos. Cada item recebe uma relevância (3 marco, 2 projeto de verdade, 1 o resto); o excesso de baixa relevância por local vira um evento "lote"; o dia traz a cobertura de todos os locais acompanhados, com ou sem novidade. A página mostra tudo por padrão e filtra por importância. Também refaz dias passados: `python scripts/historico.py --dias 7`. |
| `scripts/feeds.py` | Feeds RSS da página Fique informado (um por local e por político acompanhável), em `site/feeds/`, a partir do histórico git. Sem cadastro de leitores. |
| `scripts/gerar_municipios_ibge.py`, `scripts/simplificar_df.py` | Refazem `dados/municipios_ibge.json` (código TSE → IBGE) e `site/geo/df_ras.json` (regiões administrativas do DF) a partir das fontes oficiais. Rodar só se mudarem. |
| `scripts/identidades.py` | Núcleo de identidades: id próprio de pessoa e de partido ligando TSE, Câmara, Senado e Assembleias (`site/dados/nucleo/`), com o método e a confiança de cada ligação. Chamado pelo `gerar.py`. Também é o único lugar que liga nomes de registros das Assembleias ao deputado (`ligar_nomes`; correções manuais em `scripts/ligacoes_manuais.json`). |
| `scripts/ids.py` | `gerar_id(prefixo, fonte, id_original)`: único gerador dos ids do núcleo (pessoa, mandato, candidatura, disputa, fornecedor sem CNPJ), estável entre execuções. |
| `scripts/categorias.py` | Lista fixa de categorias de despesa e as regras que mapeiam o rótulo de cada fonte (Câmara, Senado, Assembleias). Usada pelo `gerar.py` e pelo `gerar_estaduais.py`. |
| `scripts/fornecedores.py` | Núcleo de fornecedores: normaliza CNPJ/CPF e nome e gera o ranking nacional das cotas e verbas (Câmara, Senado e Assembleias) em `site/dados/fornecedores.json` e `site/dados/nucleo/fornecedores.json`. Chamado pelo `gerar.py`. |
| `scripts/doadores.py` | Cruza o CNPJ das empresas doadoras de campanha (`dados/tse/contas/`) com os fornecedores das cotas e verbas; a ligação (método e confiança) entra em `nucleo/ligacoes.json` e o resultado, com as fontes, em `site/dados/doadores_fornecedores.json`. Chamado pelo `gerar.py`. |
| `scripts/coletar_receita.py` | Só local: lê os ZIPs mensais do CNPJ aberto da Receita (`dados/receita_bruto/`, fora do git) e guarda abertura, situação, atividade e sócios das empresas fornecedoras em `dados/receita/`. |
| `scripts/empresas.py` | Junta esses dados com a data da primeira nota de cada fornecedor em `site/dados/nucleo/empresas.json` (só os fornecedores que o site mostra). Chamado pelo `gerar.py`. |
| `scripts/mandatos.py` | Núcleo de mandatos: cargo, local, período, partido na eleição e hoje, condição (titular ou suplente) e se a pessoa está em exercício, em `site/dados/nucleo/mandatos.json`. Chamado pelo `gerar.py`. |
| `scripts/candidaturas.py` | Núcleo de candidaturas e disputas: liga cada eleito do TSE à pessoa, ao partido, às contas de campanha e à disputa (comparecimento, votos por partido e coligações), em `site/dados/nucleo/candidaturas/` e `disputas/`. Chamado pelo `gerar.py`. |
| `scripts/gerar.py` | Monta os JSONs enxutos que o site lê. Não acessa a internet. |
| `scripts/gerar_politicos.py` | Junta TSE, Câmara e Senado no índice de todos os políticos (chamado pelo `gerar.py`). |
| `dados/proposicoes_detalhe.json` | Situação atual de cada projeto (aprovado, arquivado, em tramitação), da API da Câmara. Cada execução consulta até 4000 projetos (`DETALHES_POR_EXECUCAO`), então o cache se completa em alguns dias. |
| `dados/senado_votacoes/` | Votações nominais do Plenário do Senado, com o voto de cada senador (endpoint `/votacao`). |
| `dados/senado_recursos.json` | Recursos e benefícios de cada senador no ano (gastos fora da cota, auxílio-moradia, imóvel funcional, pessoal) e escritórios de apoio, da API administrativa do Senado. Fora do git. |
| `dados/senado_aposentados.json` | Ex-senadores aposentados (IPC e PSSC): tipo, início e valor mensal, da API administrativa do Senado. Fora do git. |
| `dados/senado_ceaps.json` | Gastos da cota (CEAPS) do ano corrente, de todos os senadores, da API administrativa do Senado. Fica fora do git: é baixado de novo a cada execução. |
| `dados/senado_materias.json` | Situação atual dos projetos de senadores, do endpoint `/processo` do Senado (uma consulta por senador, refeita a cada execução). |
| `dados/votacoes/` | Histórico de votações, um arquivo por ano. Vai crescendo a cada execução. |
| `scripts/coletar_prefeituras.py` | Baixa o que os prefeitos de capitais enviaram às Câmaras Municipais que usam o SAPL (Rio Branco, Boa Vista, Natal e João Pessoa), incluindo vetos. As outras capitais mostram só o link oficial da Câmara. |
| `scripts/coletar_prefeitura_sp.py` | O mesmo para São Paulo, que não usa SAPL: lê o webservice do SPLegis. Nova capital com sistema próprio entra em `OUTRAS`, em `coletar_prefeituras.py`, com um coletor assim. |
| `scripts/coletar_estaduais.py` | Deputados estaduais das Assembleias que usam o SAPL (AC, AL, AM, PB, PI, RO, TO) e, por descoberta, de cada módulo `scripts/coletar_estadual_<uf>.py` (BA, CE, ES, GO, MG, MS, MT, PA, PE, PR, RJ, RN, RR, RS, SC, SE e SP), com fonte própria por UF. Grava em `dados/estaduais/<UF>/`; o que cada UF coleta e o que ficou de fora está em `LEVANTAMENTO_DADOS.md`. AP, DF e MA ainda não têm coletor. |
| `scripts/estaduais_comum.py`, `scripts/gerar_estaduais.py` | Funções comuns dos coletores estaduais (sessão HTTP, cache, avisos, ligação de nomes) e a montagem dos JSONs dos deputados estaduais para o site (verba, remuneração, presença, diárias, emendas, projetos e votações, cada um com `fonte`). |
| `scripts/coletar_prefeitura_ba.py` | O mesmo para Salvador: consulta de proposições da Câmara (grade Scriptcase), filtrada pelo autor "Executivo Municipal"; o link de cada projeto é o PDF do texto integral. |
| `scripts/coletar_prefeitura_go.py` | O mesmo para Goiânia: consulta pública de processos do SUAP da Câmara, filtrada pelo interessado "Prefeito de Goiânia"; o link de cada projeto é a página pública do processo. Usa o certificado intermediário de `scripts/certs/`, que o servidor não envia. |
| `dados/municipais/` | Cache dessas coletas, um arquivo por ano e capital. |
| `scripts/coletar_ministros.py` | Ministros de Estado: lista atual do Planalto, requerimentos de informação e de convocação a ministro na Câmara (arquivo anual, com envio, prazo e resposta lidos da tramitação) e no Senado, e licenças de deputados e senadores para ser ministro. Grava em `dados/ministros/`. |
| `dados/tse/` | Eleitos de cada eleição, um arquivo por estado. |
| `dados/proposicoes/`, `dados/proposicoes_cadastro/` | Ids das proposições de cada deputado e, uma vez só por proposição, tipo, número e ementa (por ano). A API só aceita 3 meses por consulta, então a primeira coleta é longa e as seguintes buscam só o período novo. |
| `site/` | O site: HTML, CSS e módulos ES em `assets/js/` (entrada `assets/app.js`), sem framework nem etapa de build. |
| `.github/workflows/atualizar.yml` | Agenda diária (e manual): coletas em jobs paralelos, depois gera o site, salva o histórico e publica. |
| `.github/workflows/republicar.yml` | Mudança de código: gera o site com os dados da última coleta e publica, sem coletar nem gravar histórico. |

## Endpoints desativados

Histórico de endpoints que o projeto usava e que saíram do ar (o Senado marcou a desativação completa de todos em 2026-02-01,
embora alguns ainda respondessem em outubro de 2026). Já não são usados no código.

| Endpoint | Para que servia aqui | Desativado | Substituto adotado | Migração |
|---|---|---|---|---|
| `legis.senado.leg.br/dadosabertos/plenario/votacao/nominal/{ano}` | Votações nominais do Plenário do Senado | 2026-02-01 (descontinuado em 2025-03-18) | `/votacao?dataInicio=&dataFim=` | 2026-10-21 |
| `legis.senado.leg.br/dadosabertos/senador/{codigo}/autorias` | Matérias de autoria de cada senador | 2026-02-01 (descontinuado em 2025-03-18) | `/processo?codigoParlamentarAutor=` | 2026-10-21 |
| `legis.senado.leg.br/dadosabertos/materia/{codigo}` | Situação atual de cada matéria do Senado | 2026-02-01 (descontinuado em 2025-03-18) | `/processo` (a situação já vem na lista de autorias) | 2026-10-21 |

Observações da migração: a resposta antiga de `/materia/{codigo}` já não trazia a situação (`DescricaoSituacao`), então a
situação dos projetos do Senado ficou vazia até a migração. O "autor principal" passou a ser o primeiro autor listado no
processo, porque o endpoint novo não tem o indicador antigo. O Senado também publica rótulos de voto que o coletor antigo
classificava mal (por exemplo "Presente – Não registrou voto", que virava voto contra); agora vão para "sem voto registrado"
e os arquivos já salvos são reclassificados a partir do rótulo original.

Para saber se algum endpoint em uso foi marcado como descontinuado, rode `python scripts/contrato_apis.py --verificar`
(o aviso aparece como "endpoint descontinuado").

## Limites gratuitos para acompanhar

- **GitHub Pages:** site de até 1 GB e cerca de 100 GB de tráfego por mês. Com milhares de visitas por dia ainda sobra bastante. Se um dia passar disso, o Cloudflare Pages é gratuito e não tem limite de tráfego; é só apontar para a pasta `site/`.
- **GitHub Actions:** gratuito sem limite em repositório público. Cada execução dura poucos minutos depois da primeira.
- **Agendamento:** o GitHub pausa tarefas agendadas em repositórios sem atividade por 60 dias. Os commits diários do robô costumam contar como atividade, mas se a atualização parar, reative na aba Actions.

## Próximos passos possíveis

- Coletores para as Assembleias que faltam (AP, DF, MA) e câmaras municipais que publicam dados abertos.
- Votações nas comissões, além do Plenário.
- Doações e gastos de campanha (TSE).
- Seguir políticos: lista salva no navegador de cada pessoa.
- Busca por tema nas ementas das proposições.

## Aviso

Projeto independente, sem vínculo com a Câmara dos Deputados ou com partidos. Os dados são exibidos como publicados pela fonte oficial, que prevalece em caso de divergência.
