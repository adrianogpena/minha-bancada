# MG (ALMG) - pesquisa de endpoints equivalentes ao coletor do PR

## Aviso de método
- Teste ao vivo IMPOSSIVEL daqui: `dadosabertos.almg.gov.br` e `www.almg.gov.br` dão ConnectTimeout no curl e ECONNREFUSED (177.86.143.199:443) no WebFetch. Bate com `ENDPOINTS.md` (mg_site / mg_dadosabertos = ERRO desde 2026-10-24). Pode ser bloqueio de IP/ASN desta máquina; o CI (GitHub Actions) pode alcançar normalmente.
- Tudo abaixo vem de snapshots do Wayback Machine (2025/2026) da documentação oficial e das páginas do portal, salvos em `scratchpad/pesquisa/mg/`. Status, paginação real e volume NÃO foram medidos. Cada item marca o que foi confirmado em documento e o que falta testar de uma rede que alcance a ALMG.
- Limite da fonte (documentado): 2 requisições simultâneas, 1 s entre elas, bloqueio sem aviso (já respeitado por `PAUSA = 1.0`).

## O que o coletor MG já tem
`scripts/coletar_estadual_mg.py` + `dados/estaduais/MG/`: deputados (`em_exercicio` + `lista_telefonica`), verba indenizatória 2025-2026 (API `prestacao_contas/verbas_indenizatorias`, por nota), proposições 2023-2026 (`proposicoes/pesquisa/direcionada`, incremental `ord=3`), ligações (`identidades.ligar_nomes`). Foto = None.

## Tabela por item do PR

| Item do PR | Status MG | Resumo |
|---|---|---|
| deputados | JÁ TEM | (foto: ENCONTRADO, ver abaixo) |
| proposições | JÁ TEM | |
| ressarcimento (verba) dados | JÁ TEM | |
| regras/PDF do ressarcimento | ENCONTRADO | Deliberação da Mesa 2.446/2009 via legislação |
| normas legais | ENCONTRADO, sem autoria direta | API legislação |
| votação nominal por deputado | NÃO PUBLICA em API (portal: não confirmado) | |
| presença em plenário | NÃO PUBLICA em API | |
| diárias | NÃO PUBLICA (não achei seção) | |
| remuneração | PARCIAL (valor fixo + PDFs agregados) | |
| gabinete (servidores lotados) | NÃO PUBLICA | |
| pautas e atas (links) | ENCONTRADO | API plenário |
| contratos e atas de registro de preço | ENCONTRADO | API contratos + página ARP (PNCP) |

## Detalhe

### Foto do deputado (extra, hoje `foto: None`)
- Status: ENCONTRADO (padrão de URL na página do deputado, snapshot 2026).
- URL: `https://www.almg.gov.br/a-assembleia/deputados/legislatura-atual/fotos/{idDeputado}.jpg` (ex.: 26098). Página do deputado: `https://www.almg.gov.br/deputados/{slug}/{id}` (id = mesmo id da API).
- Método GET, sem login. Ligação por id. Esforço: baixo (montar URL; checar com HEAD no CI que responde 200; docstring diz que a API não traz URL, então é montada).
- Risco: padrão pode mudar; validar 200 antes de gravar.

### Normas legais (leis, resoluções, decretos)
- Status: ENCONTRADO (conteúdo), autoria NÃO vem.
- URL: `GET https://dadosabertos.almg.gov.br/api/v2/legislacao/mineira/pesquisa/direcionada` (v1 equivalente documentado: `/ws/legislacao/mineira/pesquisa/direcionada`; v1 foi descontinuada em 05/06/2025, usar `/api/v2/`).
- Parâmetros: `tp` (tamanho), `p` (página), `grupo`, `tipo` (sigla: LEI, DEC, RAL, DLB...), `num`, `comp`, `ano`, `ini`/`fim` (AAAAMMDD, filtro por período = leitura incremental possível), `ass`, `th`, `ord` (0 data desc), `resumido=true` (omite o HTML do texto, recomendado). `formato=json`.
- Campos: `numDoc, norma, tipo, numero, complemento, ano, data (AAAAMMDD), origem (LEGISLATIVO/EXECUTIVO), fonte (publicação no Diário), ementa, tema, resumo, assuntoGeral, texto (HTML)`. Exemplo: `{"norma":"LEI 11725 1994","tipo":"LEI","numero":"11725","ano":"1994","data":"19941230","origem":"LEGISLATIVO","ementa":"CRIA UNIDADES ..."}`.
- Autoria: só `origem` (Legislativo/Executivo). Para ligar a deputado seria preciso cruzar com a proposição que originou a norma (lei de iniciativa parlamentar) pelo tipo/número/ano; não confirmei se a API de proposições traz o link norma resultante. Alternativa: CSV "Legislação mineira" e CSV "Proposições" em `https://dadosabertos.almg.gov.br/documentacao/arquivos` (CSV desde 1947 e 1959; joins por CodigoProposicao no CSV de tramitação) - testar se o CSV de proposições tem coluna da norma gerada.
- Esforço: médio (coleta baixa; ligação à autoria média/alta). Risco: autoria indireta; sem ligação confiável, gravar normas sem deputado seria pouco útil.

### Pautas e atas de plenário (links)
- Status: ENCONTRADO.
- Pesquisa: `GET /api/v2/plenario/reunioes/pesquisa?tp=&p=&tipoReun=&expr=&ini=&fim=` (parâmetros de data conforme ajuda v1.2: data inicial/final, tipo e expressão; confirmar nomes exatos no Swagger de uma rede com acesso). Tipos: `GET /api/v2/plenario/reunioes/tipos` (1 Ordinária, 3 Extraordinária, 4 Especial, 5 Solene, 6 Preparatória).
- Registro: `GET /api/v2/plenario/reunioes/{ano}/{mes}/{dia}/{HH:MM}` -> `idReuniao`, `horaInicioReuniao`, `horaTerminoReuniao`, `tipoReuniao`, `tipoQuorum`, `reuniaoDesconvocada`, `links.uriPauta` (`/ImportedFiles/WEB-Plenario/OrdemDoDia/O<AAAAMMDDHHMM>...htm`), `links.uriResultado` (`/ImportedFiles/WEB-Plenario/Resultado/R...htm`) = pauta e ata/resultado em HTML no domínio `www.almg.gov.br`.
- NOVO (histórico de versões, 19/02/2025, v2.1): `GET /api/v2/plenario/reunioes/detalhes/{ano}/{mes}/{dia}/{hora}` "detalhes de reunião de Plenário (pauta, edital, resultados)". É o candidato a trazer resultado por item (e quem sabe votação nominal). NÃO consegui ler o schema; primeira coisa a testar.
- Ligação ao deputado: reunião não é por deputado; só links. Serve como "pautas e atas" geral (como no PR).
- Agenda alternativa: `GET /api/v2/agenda/...` (itens por período, inclui Reunião de Plenário).
- Esforço: baixo a médio. Risco: HTML antigo sem padrão; volume de reuniões por ano é pequeno (centenas).

### Votação nominal por deputado
- Status: NÃO PUBLICA em API (confirmado na doc: serviços são agenda, comissões, contratos, deputados, legislaturas, legislação, localidades, mídias, plenário, pronunciamentos, proposições, representação partidária, tags, verbas indenizatórias; nenhum com voto por deputado). A doc oficial do processo diz que a votação é nominal por painel eletrônico, então o dado existe, mas não achei onde sai por deputado.
- A testar (de rede com acesso): (1) schema de `/plenario/reunioes/detalhes/...` (campo de resultado/votação); (2) o HTML `uriResultado` de reuniões recentes (se lista "Sim/Não" com nomes); (3) tramitação da proposição (`proposicoes/{...}` com ações de votação) - o texto das ações costuma dizer "aprovado em 1º turno", sem nomes.
- Esforço: alto e incerto. Sem resultado nominal estruturado, o PR não tem equivalente; marcar "não coletado" no docstring.

### Presença em plenário
- Status: NÃO PUBLICA em API. Reportagem (EM, out/2026) cita "Atividade parlamentar -> frequência em plenário e comissões" no portal, mas a página do deputado (snapshot 2026) não tem aba de presença, e não achei URL.
- A testar: `detalhes` (item acima) e o HTML de resultado, que costuma trazer lista de presentes/ausentes por sessão. Se existir, seria HTML parseado por regex, ligação por nome.
- Esforço: alto e incerto.

### Diárias
- Status: NÃO PUBLICA. Menu de transparência (snapshot 2026): assembleia em números, contratos, licitações, remuneração e custeio, verba indenizatória, despesa com pessoal (estrutura de cargos, folha, despesa trimestral), execução orçamentária (por elemento/grupo, pagamentos a pessoas físicas e jurídicas, receitas), gestão fiscal. Nenhuma seção de diárias/viagens.
- Possível substituto: "Pagamentos a pessoas físicas e jurídicas" (`/transparencia/prestacao-de-contas/execucao-orcamentaria/pagamentos-a-pessoas-fisicas-e-juridicas/`) pode incluir diárias pagas por favorecido, mas não confirmei e não liga a deputado por id. Testar.

### Remuneração
- Status: PARCIAL, sem valor por deputado (a ALMG não publica salário nominal; matéria do Terra e o docstring do coletor concordam).
- Valor fixo: `https://www.almg.gov.br/transparencia/prestacao-de-contas/deputados/remuneracao-dos-deputados-e-custeio/` -> subsídio mensal bruto R$ 34.774,64 (75% do deputado federal, Lei 24.266/2022), 13º proporcional, ajuda de custo no início/fim do mandato, auxílio-moradia até 25% do subsídio (reembolso, Deliberação da Mesa 2.701/2019), opção por salário mínimo (RAL 5.154/1994).
- Relatórios mensais "Remuneração e custeio da atividade parlamentar" em PDF (`https://mediaserver.almg.gov.br/acervo/<a>/<b>/<id>.pdf`, listados na página por ano, 2003-2025): ex. Out/2025 `https://mediaserver.almg.gov.br/acervo/470/905/2470905.pdf`. Não abri o PDF; conteúdo (se por deputado) a verificar.
- Folha de pagamento (`.../despesa-com-pessoal/folha-de-pagamento/`): PDF mensal agregado da ALMG (jan-mar/2026 listados, 2013-2026), não ligado a deputado.
- Esforço: baixo para valor fixo + links dos PDFs (como "regras"); médio se o PDF mensal tiver tabela por deputado (pdf parse).

### Gabinete (servidores lotados)
- Status: NÃO PUBLICA em formato aproveitável. Nada na API; sem seção de servidores por gabinete no menu de transparência; a página do deputado só traz endereço/telefone do gabinete. Notícia do Terra (c. 2023) diz que a ALMG publica remuneração por matrícula, sem nome; decisão judicial de 2021 mandava trocar por nome. Não confirmei o estado atual.
- A testar: página "Consulta de servidores" (se existir no portal, nome provável sob `/transparencia/prestacao-de-contas/despesa-com-pessoal/`) com filtro por lotação "Gabinete do Deputado X", e captcha (o portal usa reCAPTCHA v3 nos formulários).

### Contratos e atas de registro de preço do órgão
- Contratos: ENCONTRADO, API JSON.
  - `GET /api/v2/prestacao_contas/contratos/indexados?formato=json` (todos os contratos/convênios, agrupados por inicial do fornecedor), `.../contratos/{id}` (registro), `.../contratos/pesquisa/direcionada` (v1.1), `.../contratos/fornecedores/...`. Doc de 2025 diz ainda "NOVA API para dados de contratações" na v2.0 (nome do endpoint não confirmado).
  - Campos: `seqDocumentoContrato, codigoFornecedor, nomeFornecedor, numCNPJ, tipoDocumentoContrato, codDocumentoContrato, anoDocumentoContrato, descObjetoDocumento, valorInicialContrato (string "6399,8"), tipoValor, dataAssinaturaContrato, dataInicioVigencia, dataTerminoVigencia, dataPublicacaoContrato, descModalidadePedido, numProcessoLicitatorio, codDotacaoOrcamentaria`. Página do portal: 418 contratos (snapshot), detalhe em `/transparencia/licitacoes-e-contratos/contratos-e-convenios/contrato/?contrato=<seq>&fornecedor=<cod>`.
  - Id estável: `seqDocumentoContrato` (fonte) -> `ids.gerar_id("ctr_", "mg", seq)`. CNPJ: `fornecedores.documento`. Valor: `valor_br`. Datas já ISO.
  - Esforço: baixo. Lista inteira em 1 GET, sem paginação (confirmar tamanho). Só vigentes ("ativos"): histórico se perde, então gravar acumulando por seq (como `vistas`).
- Atas de registro de preço: ENCONTRADO como página HTML (sem API achada).
  - `https://www.almg.gov.br/transparencia/contratos/ARP/` (22 atas no snapshot), filtros objeto/ano (2021-2026)/situação/ordenação; cada ata com link `https://pncp.gov.br/app/atas/17516113000147/{ano}/{seq}/1` (CNPJ da ALMG 17.516.113/0001-47), vigência e objeto.
  - Alternativa melhor: API pública do PNCP (consulta de atas por órgão `cnpj=17516113000147`) - não testada; é fonte oficial federal e estável. Esforço: médio (HTML) ou baixo-médio (PNCP, endpoint a registrar em `ENDPOINTS.md`).
  - Risco: o scraping do formulário da ALMG pode exigir parâmetros `pesquisou=true&...`; ligação a deputado não se aplica (dado do órgão).

### Regras/PDF do ressarcimento (verba)
- Status: ENCONTRADO.
- `https://www.almg.gov.br/transparencia/prestacao-de-contas/deputados/verba-indenizatoria/` cita a Deliberação da Mesa 2.446/2009 (limite mensal e regras). Texto via API legislação: `GET /api/v2/legislacao/mineira/DLB/2446/2009?resumido=false` (v1 doc: `/ws/legislacao/mineira/{tipo}/{num}/{ano}`) ou link do portal `/atividade-parlamentar/leis/legislacao-mineira/lei/?tipo=DLB&num=2446&ano=2009`. Detalhe por deputado: `.../verba-indenizatoria/detalhe.html?id={idDeputado}` (já usado como `VERBA_PAGINA`).
- Esforço: baixo (gravar links, como "regras" do PR).

## Outros achados úteis
- Pronunciamentos: `GET /api/v2/pronunciamentos/...` (por deputado, texto/vídeo). Não está na lista do PR, mas existe e liga ao deputado por id.
- Comissões: `/api/v2/deputados/{id}/comissoes` ("Lista de participações em comissões da legislatura atual para um deputado"; o docstring atual diz "não coletado").
- Diário do Legislativo (nova API v2.0, 2025) e CSVs abertos (legislação 1947+, proposições 1959+, tramitação, deputados desde a 8ª legislatura, verbas): `https://dadosabertos.almg.gov.br/documentacao/arquivos`.
- Swagger oficial (nome exato de parâmetros/rotas v2): `https://dadosabertos.almg.gov.br/api/ajuda/swagger/view/lastest` (não obtive).

## Próximos passos sugeridos (quando houver rede com acesso)
1. Baixar o swagger e `GET plenario/reunioes/detalhes/2026/<m>/<d>/<hora>` + um `uriResultado` recente: decide votação nominal e presença.
2. `GET prestacao_contas/contratos/indexados?formato=json` e `legislacao/mineira/pesquisa/direcionada?tipo=LEI&ini=20260101&resumido=true&formato=json`: confirmar status, tamanho e se contratos de anos encerrados aparecem.
3. Abrir um PDF de "Remuneração e custeio" e a página de "Pagamentos a pessoas físicas e jurídicas" para ver se há diárias/valores por deputado.
4. Quick wins sem dúvida: foto por URL, links das regras (DLB 2446/2009), links de pauta/resultado de plenário, contratos.
