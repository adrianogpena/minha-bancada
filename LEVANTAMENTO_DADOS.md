# Levantamento de dados que faltam

Só o que ainda falta coletar das Assembleias Legislativas (apurado até 2026-10-22). O que já existe está no `CHANGELOG.md`, em `ENDPOINTS.md` e nos coletores `scripts/coletar_estaduais.py` (SAPL: AC, AL, AM, PB, PI, RO, TO) e `scripts/coletar_estadual_<uf>.py` (BA, CE, ES, GO, MG, MS, MT, PA, PE, PR, RJ, RN, RR, RS, SC, SE, SP). Ideias de funcionalidade ficam em `FUTURAS_IMPLEMENTACOES.md`.

Antes de escrever coletor, conferir se a Assembleia usa SAPL (`https://sapl.al.<uf>.leg.br/api/parlamentares/legislatura/?page_size=1`); se usar, basta incluir o host em `ASSEMBLEIAS`. Registrar endpoint novo em `ENDPOINTS.md` e o conjunto no `CHANGELOG.md`. Fonte com link na página do político.

## Estados sem coletor (sites sem resposta desta rede)

Em todos: testar de outra rede/navegador, abrir no Firefox com a aba Rede e achar de onde saem os dados (CSV/JSON/API). Os eleitos (nome, partido, votos) já vêm do TSE.

- **AP** (`scripts/coletar_estadual_ap.py`): `www.al.ap.leg.br` dá timeout; `sapl.al.ap.leg.br` e `transparencia.al.ap.leg.br` não resolvem; Wayback (cópia de 2024-12-06) dá 403 no curl e WebFetch. Abrir a cópia do Wayback no Firefox e procurar o portal por busca.
- **DF** (`scripts/coletar_estadual_df.py`): `www.cl.df.gov.br` (portal em `/web/portal-transparencia`) dá timeout, inclusive no navegador; `sapl.cl.df.gov.br` não resolve.
- **MA** (`scripts/coletar_estadual_ma.py`): `sistemas.al.ma.leg.br/transparencia/index.html` e `www.al.ma.leg.br/sitealema/` com a porta 443 sem resposta. Baixar o banco do ITGP (`https://comunidade.transparenciainternacional.org.br/itgp-legislativo-estadual-banco-de-dados`) para saber o que a ALEMA publica.

## Estados com coletor: o que ficou de fora

| UF | Falta | Observação |
|---|---|---|
| BA | votações, presença, API de dados abertos, remuneração dos deputados | NoPaper (`albalegis.nopapercloud.com.br`) bloqueia com Cloudflare 403, inclusive no Firefox: pedir exportação à ALBA (e-SIC) em vez de contornar. Remuneração só em PDF; diárias não listam deputado |
| CE | emendas, presença | Emendas: só quadro consolidado da LOA, sem arquivo. Presença não existe no portal |
| ES | folha, presença, proposições, votações, fornecedor da cota | Só a despesa do portal do Estado (CKAN `dados.es.gov.br`): cota e diárias pagas, sem categoria, fornecedor ou destino. `www.al.es.gov.br` dá timeout; segundo o ITGP a ALES publica proposições, salário nominal, viagens e presença (não votações nominais). Ligação com o TSE: 26 de 30 favorecidos da cota de 2026; ficam de fora os suplentes em exercício (Allan Ferreira, Antonio Carlos Machado, Marcos Madureira), que não estão entre os eleitos do TSE, e Lucinio Castelo de Assunção ("Assumçao" no TSE) |
| GO | projetos de lei, presença | Investigar `alegodigital.al.go.leg.br/spl/` e `portal.al.go.leg.br/deputados`; `processos/busca-simples` não testado; emendas não existem na fonte |
| MG | ficha completa, comissões, tramitação, salário, presença, votações | Salário, presença e votações não existem na API (Swagger conferido). |
| MS | remuneração, proposições/votações, presença, diárias | Remuneração só em PDF mensal (`gerdocumento/1201/<ano>`); SGPL (`sgpl.consulta.al.ms.gov.br`) bloqueado por captcha; diárias 2021-2026 sem despesa |
| MT | verba, cota, emendas, presença, votações, proposições | `/verbas`, `/cotas-parlamentares` e `/emendas-parlamentares` da API Elotech vazios; `www.al.mt.gov.br` (presença, votações, proposições) segue sem responder |
| PA | emendas, estrutura remuneratória, projetos, votações | Emendas no portal do Estado; estrutura remuneratória em PDF; projetos e votações fora do menu de transparência. Ligação com o TSE: 37 de 41 |
| PE | presença, votações nominais | `legis.alepe.pe.gov.br` só tem login; não são públicas. Remuneração só por cargo, não por pessoa |
| PR | ressarcimento, votações nominais, passagens, cartões | Ressarcimento bloqueado por reCAPTCHA (não contornar; pedir exportação via e-SIC da ALEP); votações só em PDF por sessão; passagens e cartões não trazem o deputado; autor das proposições só por nome |
| RJ | diárias, viagens, folha, benefícios, projetos, votações, verba/DOCIGP, presença | Diárias, viagens, folha e benefícios só em PDF; `/134` só painéis; DOCIGP sem fonte aberta achada |
| RN | cotas (CEAP) | API `api-transparencia.al.rn.leg.br` exige token Bearer embutido no JS: aguarda decisão do usuário |
| RR | remuneração por deputado, emendas | Emendas com link vazio; `sapl.al.rr.leg.br` existe mas dá 403; verba em ODT/PDF só de set/2025 em diante |
| RS | proposições, votações, presença, verba por deputado, folha | `www.al.rs.gov.br` não responde; tentar `al.rs.gov.br` pelo Firefox e ver se a folha estadual do CKAN (`dados.rs.gov.br`) traz deputados |
| SC | proposições, votações | Só no e-Legis (portalelegis), sem exportação. Ligação com o TSE: 37 de 41 |
| SE | verba, diárias, remuneração, emendas, proposições, votações, presença | Só PDF mensal (WordPress Download Manager); emendas em Power BI; Alese Legis (`aleselegis.al.se.leg.br`) não responde |
| SP | requerimentos, indicações, moções (79 mil documentos), votações nominais, diárias, emendas | Votações só em PDF por sessão; diárias e emendas sem fonte |

Os estados SAPL (AC, AL, AM, PB, PI, RO, TO) não têm pendência registrada aqui.
