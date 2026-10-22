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
### BA: Bahia
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
