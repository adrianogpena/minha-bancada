# Transparência Internacional (ITGP): o que podemos adicionar

O Índice de Transparência e Governança Pública (ITGP) da Transparência Internacional - Brasil avalia **se** cada governo publica certas informações. Ele não fornece os dados em si. Este arquivo lista o que o índice mede e, para cada tema, uma **fonte independente** (sem usar o site do ITGP nem os portais que ele consulta) que o projeto poderia coletar. Apurado em 2026-10-23.

Regra do projeto: o ITGP **não** é fonte de dado. Ele serve só de roteiro dos temas.

## Produtos do índice

| Ente | Avaliação | Indicadores (nota metodológica) |
|---|---|---|
| Governos estaduais (27) | 2025 | ~100, em 10 grupos: Legal (L), Plataformas (PL), Agenda e integridade (AG), Transparência fiscal (TFO), Obras (OBR), Transformação digital (TDC), Participação (PA), Dados abertos (D) |
| Capitais (25) | 2024 | ~90: Legal, Plataformas, Agenda (AG), Obras, Transparência fiscal (TFO), Participação (CEP), Saúde (TAD), Governança (TG), Clima e defesa civil (CP) |
| Assembleias Legislativas | 2024/25 | ~60: Legal, Plataformas, Governança, Transparência legislativa (TL), Administrativa (TA), Comunicação, Participação, Digital |
| Outros municípios | em andamento | mesma base das capitais |

Os grupos "Legal", "Plataformas", "Participação" e "Transformação digital" medem só a existência de normas, portais e canais. Não há dado aberto equivalente fora dos sites do próprio governo.

## Fontes independentes testadas (2026-10-23)

| Fonte | Situação | Cobre | Observação |
|---|---|---|---|
| SICONFI (Tesouro) `apidatalake.tesouro.gov.br/ords/siconfi/tt/` | ✅ sem chave | Estados e capitais: receitas e despesas (`rreo`), despesa com pessoal e gestão fiscal (`rgf`), lista de entes (`entes`) | Estado: `id_ente` = código da UF (SP = 35). Capital: código IBGE do município (São Paulo = 3550308). Paginado (`limit`, `offset`). Itens do ITGP: TFO receitas, despesas, dívida, relatórios fiscais |
| PNCP, licitações `pncp.gov.br/api/consulta/v1/contratacoes/publicacao` | ✅ sem chave | Licitações por `uf`; exige `codigoModalidadeContratacao` | Campo `emendaParlamentar`. Consulta por `cnpj` de capital em janeiro/2025 voltou 204 (sem dados no período testado) |
| PNCP, contratos `.../v1/contratos` | ✅ sem chave | Contratos por `cnpjOrgao` | Não filtra por UF. São Paulo (município) retornou 4 registros em jan/2025. Para o estado inteiro, é preciso a lista de CNPJs dos órgãos |
| CEIS e CNEP (CGU), sanções e leniência | ✅ download em lote, sem chave | Empresas sancionadas, com órgão sancionador e UF | `portaldatransparencia.gov.br/download-de-dados/ceis/AAAAMMDD` redireciona ao ZIP da CGU. Só o dia mais recente existe (20261022 = 200; dias anteriores = 403). A API de consulta exige chave |
| Transferegov (emendas e repasses) | ⛔ Cloudflare bloqueia `curl` | Convênios e transferências especiais por UF | Talvez acessível por Playwright, como em outros coletores |
| ObrasGov (obras com recurso federal) | ⛔ Cloudflare bloqueia `curl` | Obras por UF | Mesma situação do Transferegov |
| dados.gov.br (CKAN) | 🔑 token (401) | Catálogo de bases | Só serve para descobrir bases |
| IBGE: ESTADIC e MUNIC (normas, ouvidoria, LGPD) | ❔ API de metadados não respondeu; SIDRA responde mas sem a tabela localizada | Existência de normas e estruturas no estado e no município | Pode estar só como arquivos no FTP do IBGE. Não testado |
| Querido Diário (Diários Oficiais municipais) | ❔ sem conexão no teste | Publicações dos Diários das capitais | Repetir o teste antes de decidir |

## O que vale adicionar (ordem sugerida)

1. **Finanças do estado e da capital (SICONFI)**: receita, despesa e pessoal do governo estadual e da prefeitura da capital, na ficha do governador e do prefeito. Fonte oficial, sem chave, mesmo formato para estado e município. Já há uma ideia parecida (despesa das Câmaras e Assembleias) em `FUTURAS_IMPLEMENTACOES.md`.
2. **Sanções (CEIS/CNEP)**: cruzar empresas sancionadas com contratos do estado e da capital. Depende do item 4.
3. **Licitações do estado (PNCP)**: por UF, com valor e objeto. Mostra o que o governo comprou, com link para o PNCP.
4. **Contratos de órgãos conhecidos (PNCP)**: exige montar a lista de CNPJs por estado e capital.
5. **Emendas e obras (Transferegov, ObrasGov)**: só depois de provar acesso por navegador automatizado.

## Fora de alcance

- Normas (LAI, LGPD, nepotismo, conflito de interesses), portais, canais, agendas, participação e inovação digital: sem fonte aberta nacional. Só verificáveis nos sites de cada governo.
- Notas e rankings do ITGP: não usar, por decisão do projeto.

## Antes de implementar qualquer item

- Registrar o endpoint em `ENDPOINTS.md` e a coleta no `CHANGELOG.md`.
- Mostrar a fonte com link ao lado do dado (regra "Fontes dos dados" do projeto).
- Cada dado de político precisa de vínculo claro (governador, prefeito, secretário). Dado só do ente (estado ou município) vai na ficha do cargo, não do político.
