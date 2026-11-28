# Futuras implementações

Ideias levantadas e ainda não feitas, em ordem de complexidade. O que já foi implantado está no `CHANGELOG.md`.

Ao implementar um endpoint novo, registre-o no `ENDPOINTS.md` e o conjunto no `CHANGELOG.md`.
Revisado em 2026-11-28 contra o `CHANGELOG.md`: o que já estava feito saiu e os números foram refeitos.

Fora do escopo por ser sensível: cruzar sócio de fornecedor com político ou parente.

**Resumo**

Status de cada pacote (também repetido sob cada título; ao concluir um pacote, tire-o do arquivo e refaça os números):
- **Disponível:** dá para implementar agora, com fonte e acesso que já funcionam.
- **Parcial:** parte disponível e parte bloqueada ou dependente; a linha de status diz qual é qual.
- **Bloqueado:** depende de acesso, fonte ou decisão que ainda não existe (WAF, rede, fonte não levantada).

| Nº | Pacote | Status |
|---|---|---|
| 1.1 | Restos de pacotes feitos | Disponível |
| 1.2 | Glossário e "O que isso significou" nas demais páginas | Disponível |
| 2.1 | Emendas e Portal da Transparência | Disponível |
| 2.2 | Ministros de Estado: o que fica para depois | Parcial |
| 2.3 | Ministérios em números | Disponível |
| 2.4 | Atuação de cada ministro | Parcial |
| 3.1 | Assembleias e Câmaras Municipais | Parcial |
| 3.2 | Ministros dos tribunais superiores | Bloqueado |
| 3.3 | Assembleia do Paraná: o que falta | Parcial |
| 3.4 | Levar às outras Assembleias o que o PR coleta | Parcial |
| 3.5 | Dados coletados que o site ainda não mostra | Disponível |

## Nível 1: acabamentos

### 1.1 Restos de pacotes feitos

**Status: Disponível.**

- **Comissão x tema:** a tabela foi feita à mão em 2026-11-28 (`scripts/comissoes_temas.json`, do art. 32 do RICD, com a alínea de cada tema; registrada no `site/mapa-dados.html`). Falta usá-la: "projetos na área da comissão que ele integra" na ficha do deputado. Subcomissões e grupos de trabalho herdam da comissão de origem (sigla entre parênteses no nome); comissões especiais, externas e CPIs não têm tema.
- **Fidelidade em blocos:** `dados/blocos_historico.json` guarda, desde 2026-11-28, a composição de cada bloco quando ela muda; o histórico anterior não existe na API. Falta usar o histórico em `partidos_do_bloco` (escolher a composição vigente na data de cada votação) e rótulos que não constam em `/blocos` seguem sem fidelidade. A presença em reuniões de comissão continua sem total para comparar (a frequência de comissão só sai em PDF no portal da Câmara).
- **Perfil dos eleitos:** as Câmaras Municipais seguem com os vereadores eleitos de 2024 (suplentes que assumiram não entram; não há lista de quem está em exercício; levantamento dos Tribunais de Contas em `docs/levantamento_vereadores_tce.md` (2ª rodada, 2026-11-28): só TCE-PE e TCE-PB publicam lista de vereadores, sem partido; 12 UFs verificadas sem lista e 13 UFs não verificadas; o SAPL cobre ~1.145 Câmaras). Em PE e PB o núcleo já traz o mandato em exercício (`nucleo/mandatos.json`, fontes `vereador_pe` e `vereador_pb`, incluindo suplentes); falta fazer `perfil_casas` (`gerar_politicos.py`, chave `municipal`) partir desses mandatos em vez dos eleitos de 2024: os suplentes não têm candidatura de 2024 (sem partido, idade, instrução), então o perfil precisa de regra para quem não tem registro no TSE, e os partidos de PE/PB vêm só do TSE.

### 1.2 Glossário e "O que isso significou" nas demais páginas

**Status: Disponível** (o item da fonte do CEAPS espera uma página oficial; os termos novos precisam da aprovação do usuário).

Falta:
- Fonte do CEAPS: o link aponta a raiz do Portal da Transparência do Senado, sem página oficial que defina a cota; trocar quando achar.
- `assembleia.js` (`situacao` e modalidade das contratações) e `estadual.js` (ementa das normas): só valores crus da fonte, sem
  glossário (um "?" por linha repetiria o botão em listas de 20 itens).
- Linhas da tabela de emendas (tipo da emenda): sem "?" pelo mesmo motivo; o tipo Pix é explicado no parágrafo acima da tabela.
- Termos de cargo e verba ainda fora: decreto legislativo, resolução (norma), ementa.
- Etapas e linha do tempo nas proposições das Assembleias: falta padronizar a situação por UF.

## Nível 2: raspagem ou chave de API

### 2.1 Emendas e Portal da Transparência

**Status: Disponível** (chave no Actions; a API do Transferegov não pede chave).

Falta, com a chave `PORTAL_TRANSPARENCIA_CHAVE` já no Actions:
- 747 autores de emenda ficaram sem ligação (`semLigacao.emendas`; vale ver quantos são bancada, comissão ou nome repetido).
- Regravar a amostra de contrato (`tests/fixtures/contratos/portal_transparencia_emendas.json`, hoje reconstruída dos itens coletados) com a
  resposta crua da API (`PORTAL_TRANSPARENCIA_CHAVE=... python scripts/coletar_emendas.py --amostra`).
- Emendas Pix com o favorecido e o plano de ação do Transferegov. A coleta existe (`coletar_transferegov_especiais.py`, dados em
  `dados/transferegov/`; API `https://api-publica.transferegov.gestao.gov.br/especiais`, sem chave; o host antigo foi desativado). O plano de
  ação liga à emenda do Portal pelo código de 12 dígitos (`numero_emenda_parlamentar_plano_acao` = `codigoEmenda`), sem comparar nomes.
  Falta: `gerar_emendas` juntar isso às emendas Pix da ficha (executor, objeto e situação do plano por emenda; registrar a ligação em
  `site/mapa-dados.html`), conferir quantos planos não casam com emenda do Portal, e pagamentos e favorecidos finais
  (`/gestao-financeira-subtransacoes-especiais`, `/relatorios-gestao-documento-liquidacao-especiais`,
  `/ordens-pagamentos-ordens-bancarias-especiais`, `/empenhos-especiais`).
- Viagens a serviço e cargos do Executivo federal (ver 2.2).

### 2.2 Ministros de Estado: o que fica para depois

**Status: Parcial.** Disponível: salário, viagens e cartão (API do Portal da Transparência), resposta a requerimento do Senado, posse do ministro do Empreendedorismo, exposições de motivos. Bloqueado: tudo que depende do DOU (nomeação, atos, decretos, ministros anteriores; busca com HTTP 502 e INLABS em manutenção).

Já existem o coletor da lista do Planalto, requerimentos de informação, convocações e licenças, a ligação às
pessoas, as páginas `ministerios.html` e `ministro.html` e os eventos no histórico. Limites atuais: o Planalto não
publica a data da posse (o início vem da Wikipédia, anotada à mão em `scripts/ministros_posse.json` com o presidente que nomeou; sem ela, da licença do parlamentar ou do dia em que a coleta viu o nome) e a
resposta a requerimento do Senado não é coletada. Levantado em 2026-10-29 e ainda não refeito:

| Ideia | Fonte | Situação em 2026-10-29 | O que daria no site |
|---|---|---|---|
| Data de nomeação e exoneração, interinos | DOU: busca `www.in.gov.br/consulta/-/buscar/dou` (HTML com JSON embutido) ou INLABS (`inlabs.in.gov.br`, exige cadastro) | busca devolveu HTTP 502 duas vezes; INLABS em "Manutenção Programada" | "No cargo desde/até" exatos e link para o decreto |
| Portarias, instruções normativas e resoluções assinadas | DOU (mesmas fontes) | não medido | aba "Atos" e eventos no histórico diário; filtrar só atos normativos, o volume é grande |
| Exposições de motivos de MPs e PLs do Executivo | texto do documento (Câmara `inteiroTeor`, Planalto) | a assinatura não vem em campo da API, só no texto | ligar as propostas de `dados/executivo.json` ao ministro que assinou, não só à Presidência |
| Decretos presidenciais referendados | DOU / Planalto (legislação) | não medido | lista de decretos com a assinatura do ministro |
| Salário, viagens a serviço, cartão corporativo, jetons de conselhos de estatais | API do Portal da Transparência (chave do 2.1) | não medido | abas de gastos e histórico de viagens; os dados chegam com semanas de atraso |
| Agenda de compromissos | e-Agendas (CGU) | não medido | só reuniões com empresas e entidades privadas; a agenda inteira vira ruído |
| Votos em conselhos (CMN, CNPE, Conama) | atas de cada conselho | não medido | costuma sair só a decisão, sem o voto de cada membro |
| Posse do ministro do Empreendedorismo (Paulo Henrique Rodrigues Pereira) | a definir (Wikipédia desatualizada: ainda mostra Tadeu Alencar) | sem data de posse; hoje vale o dia em que o Planalto passou a listá-lo | completar `scripts/ministros_posse.json` com data e `fonte` |
| Ministros anteriores (antes da primeira coleta) | DOU | depende da busca do DOU | histórico de cada pasta em `ministerios.html` |
| Resposta a requerimento do Senado | API do Senado | não coletada | fechar o ciclo pedido-resposta também para RQS |

Descartado: Wikidata (consulta SPARQL de 2026-10-29 trouxe 6 ministros sem data de saída, parte já fora do cargo).

### 2.3 Ministérios em números

**Status: Disponível** (orçamento e contratos pela chave do Portal; pedidos por assunto já têm dados). Os `vinculados` das 28 pastas ficam bloqueados: o Planalto bloqueia a coleta do decreto de estrutura.

**Restos da descrição de cada pasta:**
- `vinculados` só existe em 10 pastas, copiados da página de vinculadas do ministério em gov.br. As outras 28 não têm página
  utilizável (Minas e Energia e Justiça têm, mas incompleta). A fonte seria o decreto de estrutura de cada pasta, que o
  Planalto bloqueia para coleta automática; conferir à mão ou de outro ambiente.
- Alterações legais posteriores à Lei 14.816/2024 não foram conferidas pasta a pasta. Reforma ministerial deixa o texto velho:
  revisar `scripts/ministerios_descricao.json` (e `revisadoEm`) junto com cada mudança em `ministerios.PASTAS`.

Números de cada ministério em `ministerios.html?pasta=...`:

| Ideia | Fonte | Situação em 2026-10-30 | O que daria no site |
|---|---|---|---|
| Orçamento: dotação, empenhado e pago por ministério | Portal da Transparência (chave do 2.1) ou SIOP | não medido | "A pasta tem R$ X bi este ano e pagou Y%", com série por ano |
| Servidores da pasta | Painel Estatístico de Pessoal | não medido | quantos servidores e quanto custam |
| Contratos e convênios | Portal da Transparência | não medido | maiores fornecedores da pasta, ligados a `nucleo/fornecedores` |
| Pedidos do Congresso por assunto | já em `ministerio/<pasta>.json` | dados existem | "sobre o que mais perguntam a esta pasta" |

Exige ligar o código de órgão do orçamento à chave de `PASTAS` (tabela versionada, não por nome) e, para valores,
normalizar como o resto do projeto (`valor_br`, ids por `ids.gerar_id`).

### 2.4 Atuação de cada ministro

**Status: Parcial.** Disponível: resumo do mandato de quem veio do Legislativo (dados já coletados). Dependem do 2.2 (DOU bloqueado): atos assinados; agenda e votos em conselhos têm fonte não medida.

O que o cargo comporta vem da descrição da pasta. A atuação da pessoa, além do que já existe (pedidos durante o mandato, tempo no
cargo, licença do parlamentar):

| Ideia | Fonte | Situação em 2026-10-30 | O que daria no site |
|---|---|---|---|
| Projetos, votos e licenças de quem veio do Legislativo | dados da Câmara e do Senado já coletados | dados existem | resumo do mandato anterior na página do ministro |
| Agenda de compromissos | e-Agendas (CGU) | ver 2.2 | só reuniões com entidades privadas |
| Atos assinados (portarias, instruções normativas) | DOU | ver 2.2 | aba "Atos" |
| Votos em conselhos | atas | ver 2.2 | ver 2.2 |

## Nível 3: fontes grandes, sem padrão ou cruzamentos sensíveis

### 3.1 Assembleias e Câmaras Municipais

**Status: Parcial.** Disponível, mas grande: salário exato por Casa (cada portal é diferente). Decidido não fazer por ora: Querido Diário. Bloqueado: autoria das Assembleias (autor principal e partido dos coautores dependem de ordem de assinatura que a fonte não garante).

Sem padrão nacional; cada Casa publica do seu jeito.

- Salário exato de deputados estaduais e vereadores: portal de transparência de cada Casa.
- **Querido Diário** (Open Knowledge Brasil): testado em 2026-10-29, **não implementar por ora**. A API mudou para
  `https://api.queridodiario.org.br` (o domínio antigo redireciona; a rota `/gazettes` responde 405 sem seguir o redirect) e
  oscila (HTTP 520 e timeout em tentativas seguidas). Só 510 dos 5.570 municípios têm diário coletado (`level` 3, ~9%);
  o resto é `level` 0 ou 1, sem texto pesquisável. A busca por texto (`/gazettes?querystring="subsídio dos vereadores"&territory_ids=...`)
  acha a resolução certa (Campinas: R$ 10.070,86 para 2021-2024, resolução 977/2020), mas o valor vem solto em trecho de PDF,
  sem campo estruturado: extrair exigiria regex por trecho e conferência por cidade, e erro aqui vira dado errado sobre
  político. Só valeria para as capitais e cidades grandes cobertas, com link do PDF como fonte. Se for feito, registrar
  o host no `ENDPOINTS.md`.
- Autoria das Assembleias: falta o autor principal e o partido dos coautores: as fontes não garantem a ordem de assinatura e o
  partido só chega pelo TSE depois da geração das fichas; o Senado também ainda não tem partido dos coautores e total.

### 3.2 Ministros dos tribunais superiores

**Status: Bloqueado** (sites oficiais com WAF; fontes de votos e decisões ainda não levantadas).

A composição atual dos seis tribunais vem da Wikipédia, porque os sites oficiais bloqueiam coleta automática. Falta:
- Fonte oficial da lista, se algum tribunal liberar: o bloqueio é por WAF e pode passar de outra rede ou do Actions.
- Ministros anteriores (antes da primeira coleta) e substitutos do TCU (auditores).
- Votos em julgamentos, decisões monocráticas e pedidos de vista (equivalente às abas de votações e propostas); fontes de cada tribunal ainda não levantadas.

### 3.3 Assembleia do Paraná: o que falta

**Status: Parcial.** Disponível: leitura incremental das proposições, ligar pauta à proposição, valores do gabinete, contrato ao fornecedor, ato de ressarcimento. Bloqueado: monitor de ressarcimento, passagens, cartões e estoque (a Assembleia não publica por deputado), dispensas (403), RREO e gestão fiscal (reCAPTCHA).

Os coletores do PR cobrem só 2026 (o `PRIMEIRO_ANO` de 2023 do coletor continua para o que já existe); 2023 a 2025 ficam como carga futura,
com a cobertura dos ZIPs de voto nominal medida em 2026-10-31 (2023: 90% das sessões, 2024: 86%, 2025: 89%, 2026: 83%).
Os 46 endpoints do portal estão no `ENDPOINTS.md` (`pr_t_*`, `pr_storage_*`, `pr_webservices_*`). Em 2026-10-31 três seguem com
erro, sem ser falha do site: `pr_t_presenca_mensal` (404 em todo mês testado) e `pr_t_rreo` e `pr_t_gestao_fiscal` (403: exigem reCAPTCHA).

Restos dos pacotes já feitos:
- **Proposições pelo webservice:** só a proteção contra lista vazia; sem leitura incremental (`POST /proposicao/filtrar` com `dataInicial`).
  `GET /proposicao/{código}` está quebrado no servidor (erro Oracle `ORA-00942`, com HTTP 200 e `sucesso:false`), então os trâmites não vêm;
  o testador acusa "OK" por isso. Revisar a cada trimestre.
- **Pautas e atas:** só links na votação; falta ligar o item da pauta à proposição pelo número e ano ("na pauta desta semana"). Arquivos em PDF, sem partes estruturadas.
- **Gabinete:** servidores por símbolo e nome, sem valores (o salário vem de `/api/remuneracao/{matrícula}`). Decisão: mostrar o nome só se
  a lotação ligar ao deputado de forma única por `ligar_nomes`; o "Mapa dos dados" segue sem nomes de pessoas.
- **Monitorar o que vem vazio:** `/api/ressarcimento`, `/api/passagens`, `/api/cartoes`, `/api/estoque` seguem sem dados por deputado
  (medido em 2026-10-31). O coletor chama `avisar_publicados` e avisa quando qualquer um passar a trazer dados; aí levantar o formato,
  gravar amostra em `tests/fixtures/contratos/` e coletar. O ressarcimento pode vir só em PDF.
- **Despesas do órgão:** falta ligar o contrato ao fornecedor (só traz nome, sem CNPJ); dispensas (403 em `/api/dispensas`, achar o caminho da página);
  licitações (`tipo` obrigatório); obras; ordem cronológica; SIAFIC (vazio); receitas (HTML). O ato de ressarcimento da atividade parlamentar
  (`/api/atos-normativos`) vale ler primeiro: explica o que a verba cobre.

**Antes de cada pacote** (regras do projeto): endpoint já está no `ENDPOINTS.md`; amostra real em `tests/fixtures/contratos/`
(`CONTRATOS` do coletor) e teste offline em `tests/test_coletar_estadual_pr.py`; ligação em `identidades.py`; entrada no
`CHANGELOG.md` e no `site/mapa-dados.html`; fonte com link ao lado de cada dado. Medir uma coleta do zero e uma com cache e
anotar no `CHANGELOG.md`; o job do PR já tem prazo próprio.

### 3.4 Levar às outras Assembleias o que o coletor do PR coleta

**Status: Parcial.** Disponível: as pendências dos estados já feitos (PA, RN, SP, RJ, SE, MS, BA); MT só de uma rede que responda. Bloqueado: ES, MG e RS (sem acesso); MG, MT e RJ respondem do Actions e podem ser testados por lá.

Objetivo: deixar os coletores próprios parecidos com o do PR (proposições, normas com autoria, voto nominal, presença, diárias,
remuneração, gabinete, pautas e atas, contratos e atas de registro de preço do órgão, regras da verba). **Fora do escopo: os 7 estados
do SAPL genérico** (AC AL AM PB PI RO TO), a pedido do usuário. Relatório completo por estado (URL, método, parâmetros, campos, amostra,
esforço, risco) em `docs/levantamento_estaduais/<UF>.md`. BA CE GO MS MT PA PE RJ RN RR SC SE SP já têm o que a fonte publica
(detalhes no `CHANGELOG.md`); sobram as pendências abaixo.

**Antes de implementar um estado:** reler o relatório da UF, refazer o teste do endpoint (a pesquisa foi uma passada só, em
2026-10-31), registrar o host no `ENDPOINTS.md`, gravar amostra em `tests/fixtures/contratos/` e seguir as regras de
"Coletores de Assembleias estaduais" e "Dados sem duplicação" do `CLAUDE.md` (incremental, prazo, teste offline, ligação por
`identidades.ligar_nomes` com entrada em `ESTRATEGIAS`, `CHANGELOG.md`, `site/mapa-dados.html`).

**Pendências dos estados já feitos:**
- PA: **proposições** (paginação do pager DevExpress não resolvida; usar janela de datas ou inspecionar no DevTools); remuneração 2026 só de janeiro a maio
  (conferir se o Actions completou) e tempo do zero não medido; anexos de contratos (URL não achada). `dados/estaduais/PA/` não tem `materias_<ano>.json`.
- RN: coleta do zero 18 min; gabinete, remuneração, verba e regras exigem token do site (não usado).
- SP: coleta do zero ~30 min, acima dos 25 min do job `sp` (a primeira no Actions fecha na segunda execução); gabinete parado em 2023.
- RJ: só as normas de 2023 e 2024 foram coletadas ao vivo (parciais); proposições, pautas, atas e órgão só testados em amostra; resoluções de 2025 e 2026 batem o teto de 1000 linhas (divisão por deputado não exercitada ao vivo).
- SE: diárias e folha de 2023-2024 fora; Alese Legis segue recusando conexão.
- MS: hosts em `ENDPOINTS.md` como "não testado" (rodar `scripts/testar_endpoints.py`).
- BA: atas de registro de preço fora.
- MT: coletor escrito sem teste ao vivo (HTTP 451 na rede de desenvolvimento); regravar as amostras com `python scripts/contrato_apis.py --gravar estadual_mt_gabinete` (e os outros) de uma rede que responda.

**Estados sem acesso** (testar do Actions ou de outra rede; `coletar_estadual_es.py`, `_mg.py` e `_rs.py` não têm nada de órgão, pautas, gabinete ou normas):

| UF | O que já coleta | Encontrado (esforço) | Bloqueado, parcial ou não publica |
|---|---|---|---|
| ES | deputados, diárias, ligações, verbas, parcial | Diárias: CKAN do Estado `portal-da-transparencia-pessoal-diarias`, `Diarias-<ano>.csv` (283 MB em 2026), 117 linhas da ALES nos primeiros 3 MB; diárias de servidores e motoristas, o histórico cita o deputado (ligação por nome no texto, confiança baixa); ganho só o campo `CargoFuncao`. Contratos do órgão: só pelos pagamentos a fornecedores com UnidadeGestora = ALES no `Despesas-<ano>.csv` (sem número de contrato) | Tudo no site da ALES (proposições, normas, voto, presença, folha, gabinete, pautas, atas, contratos, regras) bloqueado por rede. O Observatório do Legislativo (`www3.al.es.gov.br/observatorio/`) tem painéis de leis, proposições e votações em plenário, sem API ou CSV confirmados (inspecionar os XHR). CKAN de pessoal e de contratos do Estado não incluem a ALES |
| MG | deputados, ligações, proposições, verbas | (Wayback, sem medir) **Pautas e atas**: API de plenário traz `uriPauta` e `uriResultado`; endpoint novo `plenario/reunioes/detalhes/...` (v2.1, 2025), não lido. **Contratos**: `prestacao_contas/contratos/indexados` (JSON, só vigentes). **Atas de registro de preço**: HTML `/transparencia/contratos/ARP/` com links para o PNCP. **Normas**: `legislacao/mineira/pesquisa/direcionada` com filtro de data, sem autoria. **Regras da verba**: Deliberação da Mesa 2.446/2009 pela API de legislação. **Foto**: `www.almg.gov.br/a-assembleia/deputados/legislatura-atual/fotos/{id}.jpg` (hoje o coletor grava `foto: None`) | Voto nominal e presença: não estão em nenhuma API; podem estar no resultado de plenário ou em `detalhes` (testar). Remuneração: só o subsídio fixo de R$ 34.774,64 e PDFs mensais agregados. Diárias e gabinete: não aparecem na transparência |
| RS | deputados (via TSE), diárias (CKAN) | Nada novo achado. Contratos do Estado no CKAN não têm a Assembleia | `www.al.rs.gov.br` e `ww2` com timeout ou ECONNREFUSED (45.179.62.33:443); `al.rs.gov.br` e `dados.al.rs.gov.br` não resolvem; CKAN `dados.rs.gov.br` sem pacote legislativo; painel de diárias em Power BI (a página manda pedir pela LAI). Repetir de outra rede |

**Observações transversais**
- Contratos e atas do órgão (quando existem) não trazem CNPJ na maioria (BA, PE, GO, RR, SE, MS): só em SP, e via PNCP em RN. O vínculo a `nucleo/fornecedores` fica para depois, como no PR.
- O job manual `.github/workflows/testar-hosts.yml` testa do Actions os hosts das Assembleias sem coletor. **Resultado de 2026-11-13** (run 43412347819): respondem do Actions **MG** (página da verba indenizatória 200; `dadosabertos.almg.gov.br/api/v2` 404 na raiz, testar uma rota), **MT** (`www.al.mt.gov.br` 200; `almt.eloweb.net/servidores` 404, a rota mudou ou exige parâmetro) e **RJ** (`alerjln1` 200). **RR** segue 403 no SAPL. Sem resposta (timeout) também do Actions: AP, DF, MA, ES, RS e SE (Alese Legis); GO alegodigital falha no TLS (curl 35); `sapl.al.ap.leg.br` e `sapl.cl.df.gov.br` não resolvem no DNS. Próximos possíveis: MG, MT e RJ pelo Actions; os outros dependem de outra rede ou de pedido à Casa.

### 3.5 Dados coletados que o site ainda não mostra

**Status: Disponível** (pautas e atas, licitações de RR e PA, PDFs de SE, MS, RR e RJ); só os contratos de MT estão bloqueados (HTTP 451).

A página `assembleia.html?uf=XX` já mostra contratos, atas, maiores fornecedores, regras da verba e as leis do PA. Falta:

| Dado | Onde está | UFs | O que daria no site |
|---|---|---|---|
| Pautas e atas de sessão e de comissão | `dados/estaduais/<UF>/pautas_<ano>.json` | PR, PA, RN, SP, RJ, MS, MT | na página da Assembleia, "na pauta desta semana" na proposição e link da ata na sessão |
| Licitações e contratações diretas | `dados/estaduais/RR/licitacoes_<ano>.json`, licitações do PA | RR, PA | lista junto dos contratos do órgão |
| Contratos só com título e link de PDF | `orgao/<UF>.json` (`fornecedores` vazio) | SE (367 itens), MS (87), RR, RJ | ler fornecedor e valor dos PDFs (hoje ficam como link) |
| Contratos de MT | sem `site/dados/orgao/MT.json` (coleta falhou com HTTP 451; ver 3.4) | MT | os contratos na página da Assembleia |

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
