# RS (ALRS) - pesquisa de endpoints equivalentes ao PR

Resultado geral: o site da Assembleia (www.al.rs.gov.br, ww2.al.rs.gov.br) NAO respondeu a partir desta maquina em nenhuma tentativa
(curl: timeout de conexao em 15-21 s; WebFetch: ECONNREFUSED 45.179.62.33:443; al.rs.gov.br sem DNS; dados.al.rs.gov.br sem DNS).
Mesmo sintoma ja registrado em ENDPOINTS.md (rs_dados_diarias ReadTimeout) e no docstring do coletor ("www.al.rs.gov.br nao respondeu").
WebSearch nao retornou nenhuma pagina da ALRS. Portanto nenhum endpoint da ALRS foi TESTADO; os itens abaixo marcados BLOQUEADO
precisam ser repetidos de outra rede (ex.: runner do GitHub Actions ou conexao residencial) antes de qualquer implementacao.
Nao ha API aberta conhecida da ALRS (nada em dados.rs.gov.br; ver abaixo).

## O que o coletor atual ja faz
scripts/coletar_estadual_rs.py (130 linhas): deputados (TSE 2022, sem fonte da Casa) e diarias (CSV/ZIP CKAN dados.rs.gov.br).
dados/estaduais/RS/: deputados.json, diarias_2023..2026.json, ligacoes.json.

## Por item

| Item | Status | Notas |
|---|---|---|
| deputados | JA TEM (via TSE) | Lista oficial da Casa (foto, partido, gabinete) esta so no site da ALRS: BLOQUEADO |
| diarias | JA TEM | CKAN `diarias-do-estado`, ZIP por ano, filtro Orgao=ASSEMBLEIA. Ligacao por nome (`ligar_nomes`), sem id do deputado. Diarias de assessores ficam fora. |
| proposicoes | BLOQUEADO | Esperado: pesquisa de proposicoes no site da ALRS (HTML/ASP, sem API conhecida). Nao verificado. |
| normas legais (leis/decretos/resolucoes com autoria) | BLOQUEADO | Esperado: base "Legislacao" da ALRS (HTML). Nao verificado. Alternativa nao-ALRS: nenhuma encontrada em dados.rs.gov.br. |
| votacao nominal por deputado | BLOQUEADO | Nao verificado se publicada em formato estruturado. |
| presenca em plenario | BLOQUEADO | Nao verificado. |
| remuneracao | BLOQUEADO | Portal transparencia.rs.gov.br cobre o Executivo; folha da ALRS fica no portal da propria Casa. Nao verificado. |
| gabinete (servidores lotados) | BLOQUEADO | Idem; lotacao por deputado so seria possivel no portal da Casa. Nao verificado. |
| pautas e atas | BLOQUEADO | Nao verificado. |
| contratos / atas de registro de preco do orgao | NAO PUBLICA (no portal estadual) | Ver abaixo. Contratos da propria ALRS: BLOQUEADO (site da Casa). |
| regras/PDF do ressarcimento (verba) | BLOQUEADO | Nao verificado. |

## Testado de verdade (dados.rs.gov.br e transparencia.rs.gov.br, acessiveis)

### CKAN dados.rs.gov.br
- `GET https://dados.rs.gov.br/api/3/action/organization_list` -> 200 JSON: cage, detranrs, fepam, ftsp, jucisrs, sicdhas, ses, secretaria-da-seguranca-publica, secretaria-de-estado-de-educacao..., sop, spgg-dee. Nenhuma organizacao da Assembleia (Legislativo).
- `package_search?q=assembleia` e `q=legislativa` -> count 0.
- `package_list` (~300 pacotes, maioria `dee-*`, crime, despesas): nada legislativo. Pacotes uteis do Executivo: `diarias-do-estado` (ja usado), `contratos-do-estado`, `despesas-do-estado-*`.

### contratos-do-estado (CKAN)
- Recursos ZIP/CSV: contratos-de-fornecimento-de-bens, -locacoes, -obras, -servicos (+ layouts PDF).
- Baixado `contratos-de-servicos.zip` (3,5 MB, 31.982 linhas, delimitador `;`, latin-1). Colunas: NumeroContrato, NumeroProcesso, Objeto, Cod_Orgao, Orgao, Cod_UO, UO, Contratada, DataInicioVigenciaContrato, DataFimVigenciaContrato, ValorContrato, ...
- Orgaos presentes: secretarias, fundacoes, DAER, Defensoria etc. Nenhum orgao com ASSEMBLEIA/LEGISLATIV no arquivo de servicos (Poder Legislativo nao esta no SIAFE/CAGE do Executivo). Provavel que os outros 3 recursos sigam o mesmo escopo; so o de servicos foi baixado.
- Conclusao: NAO PUBLICA contratos da ALRS aqui. Nao liga a deputado (contratada = empresa).

### transparencia.rs.gov.br
- `/relatorios/externo/diarias-assembleia/dados/` -> 200 HTML, Power BI embutido (app.powerbi.com/view?r=eyJrIjoi...), sem dado na pagina; a propria pagina remete a LAI (https://ouvidoriageral.rs.gov.br/inicial) para dados estruturados. Mesmos dados do CSV de diarias.
- Home `/` -> 200 HTML (SPA, poucos links em HTML estatico).

## Recomendacao
1. Repetir os testes do site da ALRS de uma rede que alcance 45.179.62.33 (ou via job do Actions com curl diagnostico) antes de decidir. Se o bloqueio for geografico/IP, o Actions provavelmente tambem falha (o job de diarias ja tem ReadTimeout em dados.rs.gov.br).
2. Enquanto isso, nada novo e viavel so com fontes acessiveis: unica cobertura adicional possivel e estender diarias (ja feito). Esforco para qualquer item novo: ALTO (provavel scraping HTML sem API, host instavel).
3. Risco: host lento/instavel (timeouts recorrentes), sem filtro de data conhecido, ligacao ao deputado provavelmente so por nome.
