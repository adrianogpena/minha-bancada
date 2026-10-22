# Levantamento de dados que faltam

Estados cujas Assembleias Legislativas ainda não coletamos. Cada tópico guarda o que já foi apurado e o próximo passo, para uma nova sessão continuar sem refazer a pesquisa. Ideias de funcionalidade ficam em `FUTURAS_IMPLEMENTACOES.md`.

**Já coletados** (SAPL, `scripts/coletar_estaduais.py`, dicionário `ASSEMBLEIAS`): AC, AL, AM, PB, PI, RO, TO.
**Faltam:** AP, BA, CE, DF, ES, GO, MA, MG, MS, MT, PA, PE, PR, RJ, RN, RR, RS, SC, SE, SP.

Para cada estado, apurar: lista de deputados, proposições (autoria), votações nominais, presença, cota/verba e remuneração. Antes de escrever coletor, conferir se a Assembleia usa SAPL (`https://sapl.al.<uf>.leg.br/api/parlamentares/legislatura/?page_size=1`); se usar, basta incluir o host em `ASSEMBLEIAS`. Registrar endpoint novo em `ENDPOINTS.md` e o conjunto no `CHANGELOG.md`.

## PR: Paraná (apurado em 2026-10-22)

Portal: `https://transparencia.assembleia.pr.leg.br/` (acessível por `curl` com User-Agent de navegador, sem bloqueio). Não usa SAPL.

### O que existe

| Dado | Onde | Acesso |
|---|---|---|
| Proposições (autoria, tramitação, situação) | API `http://webservices.assembleia.pr.leg.br/api/public`: `GET /proposicao/campos`, `POST /proposicao/filtrar` (filtro `descricaoTipoProposicao`, ex.: `INDICAÇÃO`), `GET /proposicao/{código}` | JSON aberto, documentada em `/servicos/dados-abertos` |
| Normas legais | Mesma API: `GET /norma-legal/campos`, `POST /norma-legal/filtrar`, `GET /norma-legal/{código}` | JSON aberto |
| Verbas de ressarcimento (cota parlamentar), 2020 até hoje | App `https://consultas.assembleia.pr.leg.br/#/ressarcimento`; API `https://consultas.assembleia.pr.leg.br/api/public/ressarcimento/meses/{ano}` e `/ressarcimentos/{ano}/{mês}` | **Exige token reCAPTCHA** (sem token: HTTP 400 `invalid-recaptcha`). Não contornar |
| Presença em plenário | `/plenario/presenca-em-plenario` (filtros ano 2011–2026, mês, data) | A descobrir: endpoint que a página chama |
| Controle de votações | `/plenario/controle-de-votacao` (por sessão ou por projeto de lei; ano 2011–2026) | A descobrir: endpoint que a página chama |
| Atividade por parlamentar | `/plenario/atividade-por-parlamentar` (filtros parlamentar, legislatura, tipo, situação) | A descobrir; talvez saia da API de proposições (autoria) |
| Parlamentares | `/pessoal/parlamentares` | Lista carregada por script (HTML vazio): a descobrir |
| Remuneração de servidores | `/pessoal/remuneracao-dos-servidores` | A descobrir |
| Diárias de viagem | `/receitas-e-despesas/diarias-de-viagem` | PDF (ex.: `storage2.assembleia.pr.leg.br/file/public-media/transparencia/diarias/pdfs/diarias1.pdf`) |
| Passagens aéreas, cartões, despesas | `/receitas-e-despesas/passagens-aereas`, `/cartoes`, `/despesas/consultas` | A descobrir |
| Relatório de atividades parlamentares | `/plenario/relatorio-de-atividades-parlamentares` | A descobrir |

A API de dados abertos tem só as 6 rotas acima: não há rota de deputados, votos ou gastos.

### Próximos passos

1. Abrir cada página da tabela marcada "A descobrir" no Firefox, com o DevTools (aba Rede) aberto, e anotar a URL, o método e os parâmetros que a página chama ao pesquisar (presença, votações, parlamentares, atividade por parlamentar, remuneração). Só com `curl` não aparece: os dados vêm por script.
2. Testar `POST /proposicao/filtrar` com amostra (um ano, um tipo) para ver se traz autor, data, situação e resultado, e se o autor tem identificador que liga ao deputado.
3. Verificar se o autor/parlamentar nos endpoints de presença e votações tem um código comum, para ligar ao deputado estadual (o TSE já traz os eleitos de 2022).
4. Ressarcimento: pedir a exportação pela Lei de Acesso à Informação (e-SIC da ALEP) ou verificar se há CSV/PDF mensal no portal; não automatizar contornando o reCAPTCHA.
5. Se os passos 1 a 3 derem endpoints estáveis: criar `scripts/coletar_pr.py` (cache em `dados/estaduais/PR/`), `contrato_apis.py` com amostras reais em `tests/fixtures/contratos/`, e registrar tudo em `ENDPOINTS.md` e `CHANGELOG.md`. Fonte com link na página do político (regra de fontes do projeto).

## Demais estados (nada apurado)

Para cada um: conferir SAPL (comando acima); se não for, achar o portal de transparência e a API/dados abertos da Assembleia e preencher a tabela como no PR.

### AP: Amapá

Apuração de 2026-10-22: **nada obtido**, site da Assembleia inacessível. Repetir as tentativas abaixo no futuro.

| URL tentada | Ferramenta | Resultado em 2026-10-22 |
|---|---|---|
| `http://www.al.ap.leg.br` | curl | DNS resolve (`132.255.49.19`), timeout de 20 s |
| `http://www.al.ap.leg.br` | WebFetch | `ECONNREFUSED 132.255.49.19:443` |
| `https://www.al.ap.leg.br`, `https://al.ap.leg.br`, `http://al.ap.leg.br` | curl | timeout |
| `https://www.al.ap.leg.br/pagina.php?pg=transparencia` | curl | timeout (URL de transparência chutada) |
| `https://sapl.al.ap.leg.br/api/parlamentares/legislatura/?page_size=1` | curl | host não resolve (não usa SAPL nesse endereço) |
| `https://transparencia.al.ap.leg.br` | curl | host não resolve |
| `https://web.archive.org/web/20241206213457/http://al.ap.leg.br/` | curl | HTTP 403 (existe cópia de 06/12/2024, curl é bloqueado) |
| mesma cópia do Wayback | WebFetch | bloqueado pela ferramenta ("unable to fetch from web.archive.org") |

Próximos passos: repetir as URLs acima; abrir a cópia do Wayback no Firefox (curl e WebFetch não passam); procurar o portal de transparência e dados abertos por busca; os dados dos deputados estaduais (nome, partido, votos) já vêm do TSE.
### BA: Bahia (apurado em 2026-10-22)

Portal da Assembleia: `https://www.al.ba.gov.br/` (acessível por `curl` com User-Agent de navegador). Não usa SAPL (`sapl.al.ba.leg.br` não resolve). O sistema legislativo é o NoPaper (`albalegis.nopapercloud.com.br`), **atrás de Cloudflare: HTTP 403 "Sorry, you have been blocked"**, inclusive a página de dados abertos e a API. Não contornar.

| Dado | Onde | Acesso |
|---|---|---|
| Deputados em exercício (63, nome + partido) | `/deputados/deputados-estaduais`; ficha em `/deputados/deputado-estadual/{id}` (id = 910629 etc.) | HTML estático. Ficha tem nascimento, formação, mandatos, filiações, atividade parlamentar. Também `/deputados/todos-deputados`, `/ex-deputados-estaduais`, `/contatos-deputados` |
| Verba indenizatória (cota) por deputado | `/transparencia/verbas-idenizatorias` (filtro deputado, mês/ano, categoria); detalhe `/transparencia/verbas-idenizatorias/{id}/` | HTML estático: lançamento (nº, mês/ano, deputado, categoria, valor) e detalhe com nota/recibo, CNPJ/CPF, fornecedor, valor, glosa e PDF da NF em `/fserver/...`. Paginação/filtro a descobrir |
| Proposições (autoria, ementa, data, tramitação) | `/atividade-legislativa-nova/proposicoes`; detalhe `/atividade-legislativa-nova/proposicao/REQ-10650-2025` | HTML estático: "Autor: DEPUTADO ...", origem, data de entrada, regime, ementa, tramitação. Lista por ano em `/atividade-legislativa/proposicoes-por-ano` |
| Emendas parlamentares estaduais (por deputado, 2020 até hoje) | CKAN `https://dados.ba.gov.br/` dataset `emendas-parlamentares`, ZIP `.../emendasparlamentares.zip` (2,5 MB) | **CSV aberto**, atualizado diariamente. `VW_PAINEL_EMENDAS_PARLAMENTARES_DESPESAS.csv` tem ano, órgão, ação, `Deputado`, `Nome do Deputado`, valores orçado/empenhado/liquidado/pago; `..._PAGAMENTOS.csv` tem credor, data, valor e objeto; ligação por `num_codigo`. Dataset `transferencias-especiais` análogo. API CKAN `/api/3/action/package_search` responde |
| Presença/frequência | `albalegis.nopapercloud.com.br/spl/sessoes.aspx` | **Bloqueado (Cloudflare 403)** |
| Votações nominais | Sem seção própria; `/transparencia/ativ-legislat`, `/atividade-legislativa-nova/ordem-do-dia`, `/sessoes-plenarias` | A descobrir se trazem voto por deputado (no NoPaper, provavelmente bloqueado) |
| API de dados abertos (comissões, parlamentares, proposições, trâmites, autores) | `albalegis.nopapercloud.com.br/dados-abertos.aspx` (descrita em `/transparencia/avisos2`) | **Bloqueada (Cloudflare 403)** para curl; testar no Firefox e ver se o bloqueio é só do curl |
| Remuneração, diárias, estagiários | `https://portalrh.alba.ba.gov.br/transparencia` (+ `/diarias`, `/estagiarios`) | HTTP 200; conteúdo a descobrir |
| Liderança/blocos | `albalegis.nopapercloud.com.br/spl/liderancas.aspx` | Provavelmente bloqueado |

`https://www.transparencia.ba.gov.br/` é o portal do **Poder Executivo**: não tem dados da Assembleia/deputados. Só serve para emendas (via CKAN acima), pagamentos, despesas e servidores do estado. Links `/EmendasParlamentares/...` e `/ServidorPessoal/RemuneracaoServidores` dão 404 (caminhos citados na home não existem como escritos; usar o CKAN).

Próximos passos:
1. Abrir `albalegis.nopapercloud.com.br/dados-abertos.aspx` no Firefox: se abrir, anotar os endpoints REST (parlamentares, proposições, trâmites, autores) e se o Cloudflare bloqueia também o acesso programático; se bloquear, pedir liberação/exportação à ALBA (e-SIC/e-Ouv) em vez de contornar.
2. Scraping das páginas HTML do `al.ba.gov.br` (deputados, verbas, proposições): conferir `robots.txt`, paginação e parâmetros de filtro da verba indenizatória (aba Rede do Firefox).
3. Emendas: baixar o ZIP do CKAN, ligar `Nome do Deputado` ao deputado do TSE (nomes com espaços extras) e registrar em `ENDPOINTS.md`/`CHANGELOG.md`.
4. Votos e presença: sem fonte aberta confirmada; verificar se `ordem-do-dia`/`sessoes-plenarias` trazem votação nominal.
5. Verificar `portalrh.alba.ba.gov.br` (remuneração por deputado/gabinete).
### CE: Ceará
### DF: Distrito Federal (Câmara Legislativa)
### ES: Espírito Santo
### GO: Goiás
### MA: Maranhão
### MG: Minas Gerais
### MS: Mato Grosso do Sul
### MT: Mato Grosso
### PA: Pará
### PE: Pernambuco
### RJ: Rio de Janeiro
### RN: Rio Grande do Norte
### RR: Roraima
### RS: Rio Grande do Sul
### SC: Santa Catarina
### SE: Sergipe
### SP: São Paulo
