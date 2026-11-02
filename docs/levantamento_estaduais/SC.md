# SC (ALESC): pesquisa de endpoints equivalentes ao coletor do PR

Testado em 2026-10-31, curl sem login nem captcha, 1 req/s. Amostras em `scratchpad/pesquisa/sc/`.
Hosts: `https://transparencia.alesc.sc.gov.br` (T), `https://portalelegis.alesc.sc.gov.br` (E), `https://leis.alesc.sc.gov.br` (L). Todos HTML renderizado no servidor (sem JSON). Nome de deputado sempre por texto, nunca id; ligar via `identidades.ligar_nomes` (ESTRATEGIAS).

Já coletado hoje: deputados, remuneração (contracheque HTMX), gabinetes-parlamentares CSV (verba), diárias CSV, presença em sessões plenárias.

## Itens do PR

| Item | Status |
|---|---|
| Deputados, remuneração, diárias, presença, verba (CSV) | JÁ TEM |
| Proposições | ENCONTRADO (docstring atual diz "sem exportação"; a listagem filtra por data) |
| Normas legais com autoria | ENCONTRADO parcial |
| Votação nominal por deputado | NÃO ENCONTRADO |
| Gabinete (servidores lotados) | ENCONTRADO |
| Pautas e atas (links) | ENCONTRADO |
| Contratos e atas de registro de preço | ENCONTRADO |
| Regras/PDF do ressarcimento (verba) | ENCONTRADO (HTML, não PDF) |
| Extra: pagamentos/empenhos do órgão | ENCONTRADO (CSV, fora da lista do PR) |

## Proposições: ENCONTRADO (esforço médio)
- GET `E/proposicoes/processo-legislativo?ano=2026&inicio=2026-10-25&fim=2026-10-31&arquivados=1` (200, text/html). Parâmetros do form: `search, numeroPropositura, iniciativa, ano, inicio, fim, arquivados, tipoPropositura, materiaLegislativa, regimeTramitacao`. `inicio/fim` filtram a data de abertura: serve de leitura incremental (a semana testada deu "Exibindo 1 - 6 de 6").
- Cada item: número (`PL./0667/2026`), ementa, Entrada (dd/mm/aaaa), Autoria (texto: "Deputado Jerry Comper", "Governador do Estado", "Comissão de ..."), link `/proposicoes/<codigo 5 chars>`. Código de 5 caracteres é o id da fonte (base do `ids.gerar_id`).
- Sem filtro são 3515 páginas. Cobertura: 2023 em diante (a página avisa que anteriores exigem contato). Requerimentos, moções, indicações e pedidos de informação ficam em `E/proposicoes/atividade-parlamentar` (mesmo tipo de form, não testado a fundo).
- Detalhe: `/proposicoes/<cod>` (+ `/tramitacoes`, `/documentos`, `/reunioes`, `/emendas`, `/comissoes-tramitar`) com tramitação datada e "Transformado em PL./0658/2026".
- Riscos: HTML com encoding misto; autoria só por nome (coautoria em lista `<ul>`); paginação do e-Legis não medida (tamanho de página).

## Normas legais: ENCONTRADO parcial (esforço alto)
- `L/legislativo` (Next.js, busca por palavra, "busca avançada" por ano/número/tipo) e `L/ato-normativo/legislativo/<id>` (texto completo em HTML; a Constituição tem 450 KB). Sem listagem estática nem exportação; o formulário é renderizado no cliente (a chamada interna não foi identificada). `L/sumario` e `L/consolidacao` existem.
- Autoria da lei fica no texto/procedência, não em campo. Alternativa mais barata: a proposição em E que virou lei ("Transformado em Projeto de Lei", depois publicação) já traz autoria. Recomendado derivar a lei da proposição e usar L só como link.

## Votação nominal: NÃO ENCONTRADO
- `E/sessoes-plenarias/<cod>/ordem-do-dia` (200) lista por processo: número, resultado (Aprovado) e tipo ("Votação simbólica"), Autoria e ementa. Nas 19 sessões amostradas (2026) todos os 136 itens eram "Votação simbólica"; nenhum nominal e nenhum voto por deputado. A UI tem um modal "Extrato de votação" (classe `btn-extrato-votacao`, HTMX), mas não apareceu o link nessas sessões.
- Há notícia de que PLCs são votados nominalmente na ALESC (2021), então pode existir o extrato só nesses casos. Para confirmar: varrer `ordem-do-dia` das sessões com PLC e achar o `hx-get` do extrato. Não feito (varredura pesada).
- Útil mesmo assim: resultado e tipo de votação por proposição (sem voto individual). Esforço baixo-médio.

## Gabinete (servidores lotados): ENCONTRADO (esforço baixo-médio)
- GET `T/servidores?setor_id=<id>&limit=100` (200). `setor_id` do deputado vem do `<select name="setor_id">` (ex.: 2076 = "GAB DEP ALEX BRASIL"; há ~50 opções "GAB DEP <nome>"). Outros filtros: `vinculo`, `modalidade`.
- Colunas: Nome, Vínculo (Comissionado, Deputado...), Lotação, Regime ("Interno / Biométrico", "Externo / Relatório"). Links `/servidores/contracheque/<id>` (remuneração, mesmo HTMX do coletor) e `/servidores/atividade-externa/<id>` (relatório de atividade externa). Paginação `&page=2` (13 contracheques na 1ª página de 100? o filtro retornou ~13 linhas por página ao testar; medir `limit` efetivo).
- Ligação gabinete -> deputado: pelo texto "GAB DEP X" (nome de urna), via `ligar_nomes`. Sem histórico por mês (lista atual); remuneração mensal por servidor vem do contracheque.

## Pautas e atas (links): ENCONTRADO (esforço baixo)
- Sessões: `E/sessoes-plenarias` (paginado `?page=N`, ~64 páginas), cada uma `E/sessoes-plenarias/<cod>/{expediente,ordem-do-dia,comunicado,presenca,ata,pronunciamentos}`. O coletor já lê a lista e `presenca`; `ordem-do-dia` é a pauta votada, `ata` mostra "Nenhuma ata disponível" quando não há.
- Atas: `E/sessoes-plenarias/atas` (lista por ano; áudio em `hx-get /sessoes-plenarias/atas/audio/2026/Ordinária/084_ORDINARIA_2026`).
- Comissões: `E/comissoes-permanentes/agenda?data=aaaa-mm-dd` (pauta por dia), `/comissoes-permanentes/atas?page=N`, `/comissoes-permanentes/presenca`.
- Diário oficial (PDF por edição): `https://www.alesc.sc.gov.br/diario-da-assembleia`.

## Contratos e atas de registro de preço do órgão: ENCONTRADO (esforço baixo-médio)
- GET `T/contratos?page=N&limit=20` (200, HTML em cards, 66 páginas ~1300 contratos). Filtros: `ano_vigencia, tipo_contrato_id, modalidade_id, numero_contrato, objeto, contratada, cpf_cnpj, valor_min, valor_max`. Modalidade inclui "Ata de Registro de Preço". Sem filtro de data de assinatura, mas `ano_vigencia` permite reler só o ano corrente.
- Card: tipo, situação (Vigente), "Nº 273/2026", contratada, "CNPJ: 62.348.936/0001-65", objeto. Detalhe `T/contratos/<id>` (ex.: 4783); PDF `T/contratos/download/<id>` (application/pdf, 200). Id numérico da fonte serve para `ctr_`.
- CNPJ já vem com máscara: normalizar com `fornecedores.documento`. Também `T/licitacoes` e `T/plano-contratacoes` (não testados em detalhe).

## Regras/PDF do ressarcimento (verba): ENCONTRADO (esforço baixo)
- Regras em HTML, não PDF: `L/alesc/regulamentacao-interna#gabinetes-parlamentares` (lista de resoluções, cada uma em `L/ato-normativo/legislativo/<id>`, com link do Diário em PDF `https://www.alesc.sc.gov.br/diarios/pdf/4627dia.pdf#page=8`). `T/gabinetes-parlamentares` aponta ainda `http://leis.alesc.sc.gov.br/html/resolucao/2009/008_2009.html` e `.../Resolucao/2006/001_2006.html`. Diárias: `T/diarias/regulamentacao` (200).
- Basta guardar os links (como o PR faz com o PDF).

## Extra: pagamentos/empenhos do órgão (CSV)
- GET `T/pagamentos/csv/<ano>` (200, `text/csv`, `alesc_pagamentos_2026.csv`, 2,9 MB, 2011 a 2026; página `T/pagamentos/dados-abertos`). Colunas: `CPF/CNPJ;CREDOR;EMPENHO_NUMERO;...;EMPENHO_NATUREZA;SUBELEMENTO;...;LIQUIDACAO_*;PAGAMENTO_*;PAGAMENTO_VALOR_PAGO`, valores "15.213,00", datas ISO. Mesma família do CSV de gabinetes já coletado. Também `T/despesas/dados-abertos`, `T/receitas/dados-abertos`. Útil para fornecedores do órgão; esforço baixo.

## Resumo de prioridades
1. Baixo: contratos, links de regras/atas, pagamentos CSV, pautas (`ordem-do-dia`).
2. Médio: proposições (incremental por `inicio/fim`), gabinete (`setor_id`).
3. Alto/incerto: normas legais com autoria (derivar das proposições), votação nominal (não confirmada).
Ritmo: sem sinal de bloqueio; manter pausa de 1 s e `CONEXOES_POR_HOST` baixo. Atualizar docstring do coletor (diz "proposições sem exportação").
