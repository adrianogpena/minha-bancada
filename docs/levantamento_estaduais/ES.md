# ES (ALES) - pesquisa de endpoints equivalentes ao coletor do PR

Limite da pesquisa: TODOS os hosts da própria Assembleia (www.al.es.gov.br, www3.al.es.gov.br, 201.62.36.42/.46) dão timeout/ECONNREFUSED a partir desta máquina (curl e WebFetch, porta 443; DNS resolve). Provável bloqueio/geo/WAF. Nada do site da ALES pôde ser testado; o que se sabe dele vem só de busca na web (marcado "não verificado"). Já o portal do Estado (dados.es.gov.br, CKAN, S3) responde normalmente.

Já coletado (scripts/coletar_estadual_es.py; dados/estaduais/ES: deputados.json, verbas_2026.json, diarias_2026.json, ligacoes.json, parcial_2026.json): deputados (TSE), cota parlamentar e diárias dos deputados, ambos tirados do CSV "Despesas-<ano>.csv" do CKAN filtrado por UnidadeGestora = ALES.

## Por item

| Item | Status | Resumo |
|---|---|---|
| Deputados | JÁ TEM | via TSE 2022 (site da ALES inacessível) |
| Cota (verba) | JÁ TEM | Despesas-<ano>.csv, sem categoria/fornecedor |
| Diárias | JÁ TEM (parcial, ver abaixo) | só deputados |
| Proposições | BLOQUEADO (não verificado) | Observatório do Legislativo https://www3.al.es.gov.br/observatorio/ tem painéis "Legislação em vigor" (6.869 leis), "Proposições apresentadas", "Em tramitação" (1.688), "Votações em Plenário" e emendas à LDO. Dados "estruturados gerados diariamente" pela ALES (apresentação UNALE 2024), mas sem API/CSV documentado. Não testável daqui. |
| Normas legais | BLOQUEADO (não verificado) | painel "Legislação em vigor" do mesmo Observatório; há também https://www3.al.es.gov.br/ (ALES Digital). Alternativa externa: LexML (https://www.lexml.gov.br, busca por autoridade "Espírito Santo" + tipo lei estadual) - não testada, sem autoria por deputado garantida. |
| Votação nominal | BLOQUEADO (não verificado) | painel "Votações em Plenário" no Observatório; se publica voto por deputado é desconhecido. |
| Presença em plenário | BLOQUEADO / NÃO CONFIRMADO | nada encontrado em buscas. |
| Remuneração dos deputados/servidores da ALES | NÃO PUBLICA no portal do Estado | dataset CKAN `portal-da-transparencia-pessoal` (Remuneracoes-MM_AAAA.csv, ~90 MB/mês, `;`, UTF-8 com BOM): medido em 09/2026, 244 recursos, campo Orgao com ~60 órgãos do Executivo (SEDU, PMES, SESA...), nenhuma linha da ALES/TCE/TJ. Folha da ALES só no site dela (inacessível). |
| Gabinete (servidores lotados) | BLOQUEADO | mesma razão: folha da ALES não está no portal do Estado. Indício parcial: ver diárias de servidores abaixo. |
| Pautas e atas (links) | BLOQUEADO | só no site da ALES. |
| Contratos e atas de RP do órgão | NÃO PUBLICA no CKAN (proxy ENCONTRADO) | `portal-da-transparencia-contratos`: https://dados.es.gov.br/dataset/36f4bfc0-48f2-4cf9-a812-5249724da742 , Contratos-<ano>.csv (2026: 3,9 MB, 7.713 linhas, 35 órgãos). Campos: IdOrgao;NomeOrgao;NumeroProcesso;ModalidadeProcesso;NumeroEdital;NumeroDocumento;TipoDocumento;Fornecedor;CnpjFornecedor;Objeto;TipoAquisicao;Situacao;DataCelebracao;DataInicioVigencia;DataFimVigencia;ValorInicial;ValorFinal;eRegistroPreco;...;CnpjFormatado;Id. Mas NomeOrgao não contém ALES (nem Legislativo/TCE/TJ): só Executivo. Proxy: as linhas do Despesas-<ano>.csv com UnidadeGestora ALES e favorecido PJ (CpfCnpjNis, Favorecido, TipoLicitacao, Processo, HistoricoDocumento, valor pago) dão os pagamentos a fornecedores do órgão (sem número de contrato/ata). Esforço baixo (o CSV já é lido), mas é gasto por fornecedor, não contrato. |
| Regras/PDF do ressarcimento | BLOQUEADO | só no site da ALES. A norma já citada no coletor é o ATO 3879/2024 (texto não obtido). |

## Achado útil: diárias de servidores da ALES (ENCONTRADO, esforço baixo)
- Dataset `portal-da-transparencia-pessoal-diarias`: https://dados.es.gov.br/dataset/cf028a86-4eda-438d-86d8-892f0ccfc707 , Diarias-<ano>.csv (2026: 283 MB; 2025: 336 MB; desde 2009). GET sem auth, redireciona (302) para https://one.s3.es.gov.br/pr-ckan-store/resources/<id>/diarias-2026.csv (usar curl -L / Range funciona).
- Formato: CSV `;`, UTF-8 com BOM, vírgula decimal, datas dd/mm/aaaa. Campos: Ano;Data;ValorEmpenho;ValorLiquidado;ValorPago;...;CpfCnpjNis (mascarado ###.600.227-##);TipoFavorecido;CargoFuncao;Favorecido;IdFavorecido;HistoricoDocumento;Documento (OB/NE);...;UnidadeGestora;Orgao;...
- Em 3 MB iniciais de 2026 há 117 linhas da ALES. Exemplo: "PAGAMENTO DE DESPESA COM DUAS DIÁRIA E MEIA EM FAVOR DO SERVIDOR ... PARA CONDUZIR O VEICULO OFICIAL PARA REALIZAR AGENDA PARLAMENTAR DO DEPUTADO MARCELO SANTOS" (UnidadeGestora ASSEMBLEIA LEGISLATIVA).
- É o mesmo universo do Despesas-<ano>.csv que o coletor já lê (ElementoDespesa DIÁRIAS - CIVIL), então ganho só: `CargoFuncao` e diárias de servidores/motoristas citando o deputado no histórico (ligar por nome no texto, confiança baixa; seria método novo em identidades.ESTRATEGIAS, não no coletor). Não compensa baixar 283 MB a mais; melhor extrair no mesmo passe do Despesas.
- Sem filtro de data nem API de consulta (CKAN datastore não testado; recursos são CSV em S3). Mesmo ritmo da fonte já tratado pelo coletor (~0,65 MB/s por conexão).

## Riscos / próximos passos
1. Desbloquear o acesso ao site da ALES é a condição para quase tudo (proposições, normas, votações, presença, folha, gabinete, pautas, atas, contratos, ressarcimento). Tentar de runner do GitHub Actions (IP em datacenter pode ou não ser bloqueado; a doc do coletor já diz que `www.al.es.gov.br` não respondia) e de rede brasileira residencial antes de concluir "NÃO PUBLICA". Alto esforço de descoberta, depois médio de implementação.
2. Ao abrir o acesso, inspecionar com navegador os XHR do Observatório (https://www3.al.es.gov.br/observatorio/) - provavelmente painel BI (Power BI/Metabase?) ou ASP.NET; procurar endpoint JSON por trás dos painéis (não verificado).
3. Tudo o que veio do CKAN do Estado cobre só o Executivo + despesas por unidade gestora; não há remuneração nem contrato da ALES lá.
