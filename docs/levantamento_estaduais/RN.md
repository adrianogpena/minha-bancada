# RN (ALRN) - pesquisa de endpoints equivalentes ao PR

Já coletado em scripts/coletar_estadual_rn.py: deputados, proposições (PL/PEC etc. por iniciativa, desde 2023), presença em plenário, votação nominal.
Hosts:
- L = https://api-transparencialegislativa.al.rn.leg.br/elegis-api-transp-legislativa (aberta, sem login)
- T = https://api-transparencia.al.rn.leg.br (parte aberta, parte exige Bearer)
- PNCP = https://pncp.gov.br/api/consulta/v1 (aberta, federal)

Os endpoints abaixo saíram do JS dos portais (transparencia.al.rn.leg.br e transparencialegislativa.al.rn.leg.br) e foram testados com curl. Nenhum token foi usado.

## Resumo

| Item PR | Status | Fonte |
|---|---|---|
| Deputados, proposições, presença, votação | JÁ TEM | L |
| Pautas | ENCONTRADO | L `processo?reuniao=<id>&faseReuniao=1\|2` |
| Atas | ENCONTRADO (parcial) | `api-legisvideos.al.rn.leg.br/video/ata/<hash>` |
| Normas legais (autoria) | ENCONTRADO (parcial) | L `processo?tipoPropositura=...` + `publicacao[].linkDOE` |
| Contratos do órgão | ENCONTRADO | PNCP `/contratos` |
| Atas de registro de preço | ENCONTRADO | PNCP `/atas` |
| Diárias | ENCONTRADO, mas só servidores, quase vazio | T `/diarias` |
| Gabinete (servidores lotados) | BLOQUEADO | servicos-dgt.al.rn.leg.br (token) |
| Remuneração | BLOQUEADO | idem |
| Verba / regras do ressarcimento | BLOQUEADO (dados) | T `/verbas/*` 401 |

## Pautas - ENCONTRADO (esforço baixo)
- GET L/reuniao?pagina=0&tamanhoPagina=200&situacao=R&tipoOrdenacao=DESC&dataInicio=AAAA-MM-DD&dataFim=AAAA-MM-DD (o coletor atual já lista reuniões; `tipoReuniao` filtra plenária).
- GET L/processo?reuniao=<idReuniao>&faseReuniao=1 (pauta do dia / ordem do dia) ou =2 (expediente). Retorna a lista de processos com `id, propositura{tipo,numero,ano}, ementa, iniciativa{parlamentar.id}, emenda, publicacao`. Testado com reunião 3048 (15 KB). Sem paginação aparente (tem `total`).
- Liga ao deputado por `iniciativa.parlamentar.id` (id do /parlamentar, o mesmo do coletor).
- Link de fonte: `https://transparencialegislativa.al.rn.leg.br/evento-legislativo/<idReuniao>`.
- Risco: uma requisição por reunião; fazer só para reuniões novas (incremental pela data da reunião).

## Atas - ENCONTRADO parcial (esforço médio)
- O front monta o link `https://api-legisvideos.al.rn.leg.br/video/ata/<hash>` quando existe, com `<hash>` vindo de `L/legis-videos/reuniao/<id>` (`dados[0].hash`, `dados[0].ata`).
- Testado: a reunião 3048 (28/10/2026) devolveu `{"dados":[],"total":0}`; ou seja, a ata só existe para parte das reuniões (as que têm vídeo/ata publicados). Não testei uma reunião com ata, o formato do PDF e a cobertura por ano ficam por verificar.
- Alternativa: Diário Oficial Eletrônico https://dle.al.rn.leg.br (links `abrearquivo/<GUID>` aparecem em `processo.publicacao[].linkDOE`).

## Normas legais - ENCONTRADO parcial (esforço médio)
- GET L/processo?pagina=0&tamanhoPagina=200&tipoPropositura=<id>&dataInicio=AAAA-MM-DD&dataFinal=AAAA-MM-DD. Filtros que funcionam: `tipoPropositura`, `dataInicio`, `dataFinal`, `iniciativa`; `situacao` aceita o parâmetro mas devolveu 0 para todos os ids testados (13, 26, 27, 30, 127, 128): não usar.
- Ids de tipo (`L/entidade-base/tipo-propositura`): 1 PL (3851), 2 PLC, 6 PDL (6), 8 PROJETO DE RESOLUÇÃO (348), 7 PEC, 22 resolução de título honorífico, 3 Ato da Mesa (4), 13 Ato do Presidente (3).
- O coletor atual só pega projetos e propostas. Para "norma" há apenas indícios no registro: `numeroExterno`/`anoExterno` (preenchido em 333 de 800 PLs de 2023+ amostrados, ex.: PL 436/2026 com numeroExterno "51"; não confirmei se é número da lei estadual ou do ofício do Executivo) e `publicacao[].linkDOE` (DOE com o texto). `informacaoLei` veio vazio em todos os 800.
- Detalhe: `L/processo/<id>/tramitacao` lista `situacaoProcesso` (ex.: "Lei Sancionada" id 27, "Lei Promulgada" 26, "Decreto Legislativo Promulgado" 127, "Resolução promulgada" 128) com `origem.data` e `linkDOE`. Um PL virado em lei só se confirma lendo a tramitação (1 requisição por processo aprovado).
- Alternativa externa: iframe https://iframe.leisestaduais.com.br/rn (não testado).
- Risco: sem número oficial da lei confiável no cadastro, decreto do Executivo não está aqui (autoria de decreto do governador não é da Assembleia).

## Contratos e atas de registro de preço do órgão - ENCONTRADO (esforço baixo)
O próprio portal T exige token para `/ata-registro-preco/*` (401), mas o PNCP publica o mesmo (a ALRN é órgão 08.493.371/0001-64).
- GET PNCP/contratos?dataInicial=AAAAMMDD&dataFinal=AAAAMMDD&cnpjOrgao=08493371000164&pagina=1&tamanhoPagina=50. Janela máxima 365 dias (422 acima disso): consultar ano a ano. 2026: 116 contratos (12 páginas de 10). Campos: `numeroControlePNCP, numeroContratoEmpenho, anoContrato, sequencialContrato, objetoContrato, valorInicial, valorGlobal, dataAssinatura, dataVigenciaInicio/Fim, niFornecedor, nomeRazaoSocialFornecedor, tipoContrato{nome}, processo, dataAtualizacao`.
- GET PNCP/atas?dataInicial=...&dataFinal=...&cnpj=08493371000164&pagina=1&tamanhoPagina=50. 2026: 200 atas. Campos: `numeroControlePNCPAta, numeroAtaRegistroPreco, anoAta, dataAssinatura, vigenciaInicio/Fim, cancelado, objetoContratacao, dataAtualizacao`.
- Incremental: `dataAtualizacao`/`dataAtualizacaoGlobal` por registro; os endpoints `/contratos/atualizacao` e `/atas/atualizacao` existem na API PNCP (não testados) para ler só alterados. Alternativa simples: reler só o ano corrente a cada dia.
- Fornecedor por CNPJ/CPF: reaproveitar `fornecedores.documento`/`nome_chave`. Link de fonte: `https://pncp.gov.br/app/contratos/08493371000164/<ano>/<sequencial>`.
- Registrar o host pncp.gov.br em ENDPOINTS.md (pode já existir se outro coletor usar PNCP; conferir).
- Risco: PNCP cobre contratos publicados a partir de 2021 (Lei 14.133); janela de 365 dias; ritmo da API federal (poucas requisições, pausa).
- Convênios (extra, não pedido): T `/convenios` aberto, 49 registros, campos `nrConvenio, nomeConveniado, vlrConvenio, dtAssinatura, nomeGestor`.

## Diárias - ENCONTRADO, valor baixo (esforço baixo)
- GET T/diarias?codUnidade=101&competencia=MM-AAAA (sem token). Sem parâmetros devolve as 30 últimas. Filtros desconhecidos dão 400. Exportações `/diarias/csv|json|xlsx` exigem token (401).
- Campos: `nomeBeneficiario, cpfBeneficiario` (não gravar), `cargo, justificativa, dataInicioViagem, dataFimViagem, localViagem, valorDiaria, quantidadeDiarias, valorTotal, dataCadastro`.
- Problema: são diárias de servidores (cargos como "Assessor Consultivo", "Analista Legislativo"); não vi deputado em nenhuma amostra. 2025-01, 2025-06, 2024-03 e 2023-01 vieram vazios; 2026-03 tem 1 registro de teste ("TESTE 23/03/2026"). O front esconde registros anteriores a 2025-08. Não serve para o contrato de diárias de deputado; no máximo diárias de servidores sem ligação a deputado.
- `T/diarias/atualizacao` (aberto) mostra a última carga por entidade (Diarias, Convenios, Empenhos...).

## Gabinete e remuneração - BLOQUEADO
- Páginas "Remunerações de Servidores" (`/servidores-pagamentos`) e "Estrutura remuneratória" usam https://servicos-dgt.al.rn.leg.br/consulta-servidor-api/api/auth/token + `/api/consulta/`. Exige autenticação por token. O token do site (`tokenBearer` no JS) é de um login embutido, expirado em 2024; não usei. Sem token não há lista de servidores por gabinete nem remuneração.
- Os deputados aparecem no L/parlamentar sem vínculo a servidores. Alternativa não testada: portal do TCE-RN (http://portal.tce.rn.gov.br/) ou dados abertos do Estado; pouco provável ter lotação por gabinete.
- Recomendação: pedir à ALRN (LAI) uma chave de leitura, ou marcar como não publicado.

## Verba / ressarcimento (cota) - BLOQUEADO
- T/verbas/meses/anos, /verbas/meses/<ano>, /verbas/deputados, /verbas/despesas/ (+csv/json/xlsx) e /mandato/legislaturas: todos 401 sem token (testado).
- Regras/PDF do ressarcimento: não localizei PDF público; a página https://transparencia.al.rn.leg.br/verbas é SPA e só mostra os dados do endpoint acima. Possível ato da Mesa/resolução nas tipologias L: 3 Ato da Mesa (4 registros, 2018+), sem texto de regras encontrado.
- Já está documentado no docstring do coletor ("exige token embutido no código do site").

## Extras úteis no L (não pedidos)
- L/comissao (16 KB: comissões com sigla, finalidade, vigência); L/bancada (blocos/bancadas); L/comissao-cargo?comissao=<id> e bancada-cargo?bancada=<id> (membros e cargos, útil para "cargo em comissão" do deputado).
- L/processo/<id>/documentos e L/documento/<id>/conteudo (PDF do documento; só os marcados `publico`).
- T/terceirizados (4300 registros, aberto): terceirizados por contrato; sem relação com deputado.

## Ordem sugerida
1. Contratos e atas via PNCP (baixo, valor alto).
2. Pautas por reunião (baixo).
3. Comissões/cargos (baixo).
4. Atas via legisvideos e normas via PL + tramitação (médio).
5. Diárias só se aceitarem servidores; gabinete, remuneração e verba aguardam token oficial.
