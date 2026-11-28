# Levantamento: vereadores em exercício em dados abertos de Tribunais de Contas

Data: 2026-11-28. Versão parcial: só PE foi confirmado; as demais UFs ficaram "não verificado" (sites bloqueados, fora do ar ou sem documentação localizável). Somente leitura (web e curl); nada foi baixado além de amostras. "Não verificado" = não consegui abrir ou não achei documentação.

Objetivo: achar fonte oficial padronizada com vereadores em exercício (inclui suplentes que assumiram) por município, com nome, partido e data de posse/afastamento. Hoje o projeto só tem os eleitos de 2024 pelo TSE.

## Resultado principal verificado

**TCE-PE, API Dados Abertos (Sagres Pessoal), entidade `ListaServidores`**
- URL: `https://sistemas.tce.pe.gov.br/DadosAbertos/ListaServidores!json?NomeCargo=VEREADOR` (também `!xml`, `!html`). Sem chave, sem cadastro. HTTP 200, 4,9 MB, 8.859 linhas (limite da API: 100.000 por chamada).
- Campos: UnidadeJurisdicionadaTCE, NomeUJ (ex.: "Câmara Municipal de Afogados da Ingazeira"), HashCPFPessoa, CPFServidor mascarado (`***.212.314-**`), NomeServidor, Matricula, NomeCargo, NomeTipoVinculo (`Eletivo`), DataAdmissao, DataIngresso, DataAfastamento, TipoAtoPessoalIngresso/Afastamento, AnoRemessa, MesRemessa. Não tem partido.
- Amostra: `Abreu e Lima | MARIA SALOME DE ARAUJO | VEREADOR | Eletivo | 2017-01-01 | 2020-12-31`; `Afogados da Ingazeira | JOSE RAIMUNDO LIMA SANTOS | VEREADOR | Eletivo | 2021-01-01 | 2024-12-31`.
- Cobertura: Pernambuco (189 UJ distintas no resultado). Traz mandatos de vários períodos, com data de ingresso e afastamento, então dá para ver quem assumiu no meio do mandato (suplente) e quem saiu. Cargo vem sujo (125 grafias distintas, como `VEREADOR`, `VEREADOR(A)`, `0010001-Cam_VEREADOR(A) - NV-01`, `1C VEREADOR`): precisa de normalização. O filtro `NomeCargo=VEREADOR` é "contém" (todas as 8.859 linhas contêm o texto). Mandato em curso: o campo `DataAfastamento` simplesmente não aparece no JSON; 1.892 linhas têm ingresso em 2025 (legislatura 2025-2028), e ingressos fora de 01/01/2025 indicam suplentes que assumiram (a validar contra o TSE).
- Atualização: remessa mensal (AnoRemessa 2026, MesRemessa 10 nas amostras). Esforço: baixo. Risco: cargo sujo, ligação com pessoa só por nome e CPF mascarado (6 dígitos centrais), sem partido (partido vem do TSE).

## Tabela por UF (estado atual da verificação)

| UF | Fonte | URL | Formato | Campos | Cobertura | Esforço | Risco |
|---|---|---|---|---|---|---|---|
| PE | TCE-PE API Dados Abertos | ver acima | JSON/XML | nome, CPF mascarado, cargo, vínculo, ingresso, afastamento | PE, câmaras que remetem ao Sagres | baixo | cargo sujo, sem partido |
| RS | TCE-RS CKAN (`dados.tce.rs.gov.br`) | `https://dados.tce.rs.gov.br/api/3/action/package_search?q=vereador` | CKAN/JSON, CSV | `package_search` por "vereador" e "agente" devolveu 0 conjuntos; só há balancetes, despesas, contratos, licitações e "gastos-lrf-legislativo" | RS | n/a | sem lista de vereadores (HTTP 200 verificado) |
| SP (TCE) | Transparência TCE-SP | `https://transparencia.tce.sp.gov.br/api/json/municipios` (200, lista municípios) | JSON | API de despesas/receitas; "Mapa das Câmaras" traz custos das câmaras, não pessoas | 644 municípios (sem capital) | alto | não achei endpoint de vereadores (não verificado a fundo) |
| PB | TCE-PB Dados Abertos (Sagres) | `https://dados.tce.pb.gov.br/` | SPA (200) | endpoints não verificados (o app é JS; não consegui listar a API) | PB | não verificado | não verificado |
| CE | TCE-CE `api-dados-abertos.tce.ce.gov.br` | raiz responde página padrão do nginx (200); `/docs` e `/swagger.json` 404 | n/a | não verificado | CE | não verificado | sem documentação achada |
| SC | TCE-SC "apis dados abertos" | `https://www.tcesc.tc.br/apis-dados-abertos` | n/a | bloqueado (HTTP 403, Akamai) para curl e fetch | SC | não verificado | não verificado |
| MG | TCE-MG `dadosabertos.tce.mg.gov.br`; CAPMG (cadastro de agentes públicos) | portal não respondeu (timeout) | n/a | CAPMG citado em páginas do tribunal, sem API achada | MG | não verificado | não verificado |
| RJ | TCE-RJ `dados.tce.rj.gov.br` | host não resolve (DNS) | n/a | não verificado | RJ | não verificado | não verificado |
| ES | TCE-ES CidadES API | página de ajuda citada em busca (`tcees.tc.br/ajuda/?p=7775`) devolveu 404 | n/a | folha do CidadES tem vereadores (segundo página de ajuda), acesso por API não confirmado | ES | não verificado | não verificado |
| Demais UFs (AC, AL, AM, AP, BA, DF, GO, MA, MS, MT, PA, PI, PR, RN, RO, RR, SE, TO) | portais não confirmados | hosts testados por palpite (dados.tce.xx...) não existem ou não responderam | n/a | não verificado | n/a | não verificado | não verificado |

## Tribunais municipais

TCM-SP, TCM-RJ (TCMRio), TCM-BA, TCM-GO, TCM-PA: sites principais testados (TCM-SP 200, TCMRio 200, TCM-GO 200, TCM-PA 403, TCM-BA sem resposta). Nenhum portal de dados abertos com lista de vereadores foi localizado. Não verificado.

## Fontes nacionais

- TSE Dados Abertos (CKAN `dadosabertos.tse.jus.br`): responde, com resultados por município/zona e candidatos; não achei conjunto de suplentes que assumiram (convocação). Situação "SUPLENTE" existe em candidaturas, mas assunção de vaga não é publicada. Não verificado em profundidade.
- dados.gov.br: API pública exige token (HTTP 401 sem chave).
- TCU, CGU, Atricon, Radar da Transparência, SICONFI, Cidades Transparentes: não verificados nesta rodada.

## Recomendação (provisória)

1. Começar por PE (única fonte confirmada, sem chave, com ingresso/afastamento por vereador). Partido vem do cruzamento com TSE por nome e município.
2. Em seguida, confirmar a API do TCE-PB (Sagres), TCE-CE e TCE-ES; o Sagres/CidadES costuma ter módulo de pessoal que inclui agentes políticos, como em PE.
3. As demais UFs seguem sem fonte padronizada confirmada; considerar o SAPL/Interlegis e portais das câmaras como alternativa.
