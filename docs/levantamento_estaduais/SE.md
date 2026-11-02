# SE (Alese) - pesquisa de endpoints (2026-10-31)

Estado atual: `scripts/coletar_estadual_se.py` coleta só deputados (carrossel de https://al.se.leg.br/, id do Alese Legis + nome + partido + foto; nomeCivil via TSE). `dados/estaduais/SE/` tem só `deputados.json`.

Padrão do portal (https://al.se.leg.br, WordPress + Elementor + Download Manager "wpdm"):
- Cada página de transparência tem abas Ano > Mês, cada mês com um botão `Download`.
- Contornar JS: `GET https://al.se.leg.br/wp-json/wp/v2/pages?slug=<slug>` (JSON, 200, sem auth) traz `content.rendered` com `data-downloadurl="https://al.se.leg.br/download/<slug-do-item>/?wpdmdl=<ID>&refresh=<token>"`. Esse link (com `?wpdmdl=<ID>`) devolve direto `application/pdf` (200, sem captcha/login). A URL `/download/<slug>/` sem `wpdmdl` devolve HTML.
- Ordem das abas = meses de Janeiro a Dezembro; o `<h2>` anterior dá o ano. O mês de cada PDF vem da posição da aba (e do cabeçalho do PDF).
- `wp-json/wp/v2/pages` devolve 500 KB a 1,3 MB por página: 1 requisição por tipo por coleta basta. Campo `modified` da página serve de gatilho incremental (só reler PDFs se mudou; e só os meses recentes).
- Todos os PDFs são texto (pdftotext -layout funciona), sem OCR. Encoding: ler como UTF-8.
- Alese Legis (https://aleselegis.al.se.leg.br, IP 177.39.233.7) recusa/expira conexão nas portas 80 e 443 (curl e WebFetch, 3 tentativas em 2 egressos: ECONNREFUSED/timeout). Todo item que depende dele está BLOQUEADO.

## Itens da lista do PR

### deputados
JÁ TEM (carrossel da home). Sem e-mail/nome civil.

### proposições
BLOQUEADO. Só existe no Alese Legis (fora do ar para nós). Sem SAPL (`sapl.al.se.leg.br` não resolve). Nada equivalente em al.se.leg.br. Reavaliar quando o host voltar: tentar `spl/` (ASP.NET, páginas `parlamentar.aspx?id=`, `comissoes.aspx`, `mesas.aspx`, `dl/default.aspx` e `/legislacao`, links vistos na home). Esforço: alto (HTML ASP.NET com ViewState, não testado).

### normas legais (leis/decretos/resoluções com autoria)
BLOQUEADO. `https://al.se.leg.br/legislacao/` só aponta para `https://aleselegis.al.se.leg.br/legislacao` e `/legislacao-consolidada` (mesmo host fora do ar). Esforço: alto, risco: não verificável.

### votação nominal por deputado
BLOQUEADO / NÃO PUBLICA em outro lugar achado. Só poderia estar no Alese Legis. Não há dados abertos de votação em al.se.leg.br.

### presença em plenário
BLOQUEADO / NÃO PUBLICA fora do Alese Legis.

### pautas
NÃO PUBLICA em al.se.leg.br (nenhuma página de pauta no menu). Possível no Alese Legis (bloqueado). `/atas-das-sessoes-legislativas/` na verdade é um iframe para `https://webmail.al.se.leg.br` (página quebrada, não são atas).

### atas
NÃO PUBLICA (a página de atas é o webmail, ver acima). `/audios-das-sessoes-legislativas/` existe (áudios, 1,2 KB de conteúdo, não verificado o formato). Possível no Alese Legis (bloqueado).

### diárias
ENCONTRADO (PDF mensal).
- Página: `GET https://al.se.leg.br/wp-json/wp/v2/pages?slug=diarias` (equivale a https://al.se.leg.br/portal-da-transparencia/despesas/diarias/). 112 PDFs (anos 2015?-2026, até Jan-Mai/2026 na data; página `modified` 2026-04-06; ou seja, publicação com atraso de meses).
- PDF: ex. `https://al.se.leg.br/download/diarias-109/?wpdmdl=186478` (Jan/2026, 100 KB). Colunas: CPF mascarado (`047***964**`), Beneficiário, Cargo, Motivo da Viagem, Destino, Saída, Retorno, Pernoite, Referência (mês/ano), Valor.
- Liga ao deputado só por nome (Beneficiário). Cargo "DEPUTADO" identifica deputados, mas o layout do pdftotext quebra linhas (motivo e valores em linhas distintas, colunas desalinhadas): precisa de `pdftotext -bbox`/pdfplumber por coordenadas ou `-layout` com heurística. Inclui também servidores (filtrar por cargo = DEPUTADO).
- Esforço: médio/alto (parsing de PDF). Riscos: atraso na publicação, layout muda, nome sem acento.
- Também há `passagens` (slug `passagens`, 113 PDFs, ~80 KB/mês, ex. `passagens-112`): passagens aéreas, não pedido no PR mas equivalente a custo do mandato. Não baixado em detalhe.

### remuneração (subsídio)
ENCONTRADO (PDF mensal).
- `GET https://al.se.leg.br/wp-json/wp/v2/pages?slug=subsidio-e-remuneracoes` (https://al.se.leg.br/portal-da-transparencia/recursos-humanos/subsidio-e-remuneracoes/). 116 PDFs, 2,5 MB por mês, `modified` 2026-04-24. Ex. Jan/2026: `https://al.se.leg.br/download/subsidios-e-remunera/?wpdmdl=184481`.
- Título "DETALHAMENTO DA FOLHA DE PAGAMENTO - Referente a: JANEIRO/2026". Colunas: Mat., Nome, Admissão, Cargo, Lotação, Salário/Subsídio, Outras verbas, Função, 13º, Férias, Abono, Auxílios, Total de Rendimentos, Retroativo, Descontos (PREV, IRRF), Líquido.
- Exemplo: `012746 ADAILTON MARTINS DE OLIVEIRA FILHO 01/02/2019 Deputado GABINETE DO DEPUTADO ADAILTON MARTINS 34.774,64 10.432,39 ... 46.407,03 ... 34.709,90`.
- Deputado = Cargo "Deputado". Liga por nome (nome civil completo, que casa com TSE `nomeCivil`) e matrícula. Linhas quebram em 2 (nome longo, lotação). Sem CPF.
- Esforço: médio (pdfplumber/pdftotext -layout com regex de matrícula de 6 dígitos). Riscos: PDF grande (2,5 MB x meses), publicação com atraso; incremental por mês (anos encerrados não baixar de novo).

### gabinete (servidores lotados no gabinete)
ENCONTRADO, no mesmo PDF de remuneração: coluna `Lotação` = `GABINETE DO DEPUTADO <NOME>` (ex. `GABINETE DO DEPUTADO NETO BATALHA`, cargo `COM - AUXILIAR DE GABINETE PARLAMENTAR`, remuneração e admissão). Mesma fonte/URL da remuneração; uma só leitura serve aos dois itens. Ligação do gabinete ao deputado por nome no texto da lotação (usar `identidades.ligar_nomes`, UF com regra própria: lotação tem prefixo e às vezes apelido/sobrenome). Esforço: médio (adicional pequeno sobre remuneração). Servidor nominal exposto no PDF (nome completo, sem CPF); mesmo critério do PR.
- Complemento: tabela salarial `https://al.se.leg.br/portal-da-transparencia/recursos-humanos/tabela-salarial/` (2 PDFs: Comissionados e Deputados; Efetivos), útil só para teto de cargos.

### contratos e atas de registro de preço
ENCONTRADO (lista de PDFs, sem dados estruturados).
- `GET https://al.se.leg.br/wp-json/wp/v2/pages?slug=contratos` (https://al.se.leg.br/portal-da-transparencia/contratos/), 1,35 MB, 830 itens com `<h3><a href='.../download/<slug>/'>título</a>`, 827 com link `wpdmdl`. Anos 2017 a 2026, `modified` 2026-07-13. Título carrega tipo, número, ano e fornecedor: `Contrato n 013 2024 LABOR TERCEIRIZACAO`, `1 Aditivo ao Contrato n 001 2025 POSTO PRESIDENTE`, `Termo de Ajuste de Contas ...`, `1 Aditivo Ata Registro de Precos n 01 2024 Alldoc` (atas de registro de preço aparecem como "Ata Registro de Precos").
- Amostra: PDF do termo aditivo 066/2024 (1,5 MB, texto "TERMO ADITIVO CONTRATUAL... GRÁFICA JORNAL DA CIDADE LTDA."). Sem CNPJ/valor/vigência estruturados no título: valor e CNPJ só dentro do PDF (parsing por regex, irregular).
- Mínimo viável: gravar por item título, link de download e ano (id estável por `ctr_` com fonte `se` + slug da URL, que é o id na fonte). Não baixar os PDFs.
- Páginas relacionadas: `/portal-da-transparencia/licitacoes-e-contratos/andamentos-de-processos-licitatorios/` (e `-2/`), `/portal-da-transparencia/plano-de-contratacoes-anual/`, `/portal-da-transparencia/contratos-do-corona-virus/` (não inspecionadas).
- Esforço: baixo (lista) / alto (campos dos PDFs). Risco: título livre, erros de digitação.

### regras/PDF do ressarcimento (verba)
ENCONTRADO, e melhor que o do PR: o PDF traz os valores por deputado (verba indenizatória, "Relatório de Ressarcimento").
- `GET https://al.se.leg.br/wp-json/wp/v2/pages?slug=ressarcimento-dos-deputados` (https://al.se.leg.br/portal-da-transparencia/despesas/ressarcimento-dos-deputados/), 600 KB, 124 PDFs, anos 2016-2026, `modified` recente. Ex. `https://al.se.leg.br/download/ressarcimento-dos-deputados-120/?wpdmdl=186576` (Pagamento 01/2026, 4 páginas, 44 KB).
- Texto (pdftotext -layout, parseável com regex):
```
Mês/Ano de Pagamento: 01/2026     Competência: 12/2025
Deputado: Adailton Martins
 1  Art. 4º I - Contratação de assessoria e consultoria            R$ 27.210,00
 2  Art. 4º II - Combustíveis, lubrificantes, peças e manutenção de veículos  R$ 4.174,63
 3  Art. 4º VI - Locação de veículos automotores                   R$ 13.000,00
                                                    Total:  R$ 44.384,63
```
- Campos: mês de pagamento, competência, deputado (nome parlamentar, liga por nome), inciso do art. 4º (rótulo da fonte para `categorias.py`, precisa de regras novas em REGRAS: assessoria/consultoria, combustíveis, locação de veículos, locação de imóvel/escritório etc.), valor, total. Não há fornecedor, CNPJ, data de nota nem documento: só total por categoria e mês (nível de detalhe menor que a Câmara).
- Regras da verba: "Art. 4º" aponta para ato normativo da Alese; texto do ato não localizado (provavelmente em Alese Legis, bloqueado).
- Esforço: baixo/médio. Incremental: reler só meses recentes (competência atrasa 1 mês; anos encerrados cacheados).

## Fora da lista do PR (achados)
- Empenhos e pagamentos: `slug=empenhos-e-pagamentos`, um PDF por ANO (10 arquivos, 2018-2026; 2026 ~370 KB). Custos gerais da Alese, não por deputado.
- Emendas parlamentares: página `/portal-da-transparencia/emendas-parlamentares` aponta para Power BI do Executivo (não testado, fora do escopo).
- WordPress REST de notícias: `https://al.se.leg.br/wp-json/wp/v2/posts` (23.585 posts; ex. 2026-10-30). Sem uso direto no PR.

## Prioridade sugerida
1. Ressarcimento (baixo/médio, valor alto)
2. Remuneração + gabinete (médio, uma leitura serve às duas)
3. Contratos/atas RP (baixo só com lista)
4. Diárias (médio/alto, layout irregular)
5. Proposições, normas, votação, presença, pautas, atas: bloqueados até Alese Legis voltar (retestar a cada coleta; `comum.avisar` já cobre fonte fora do ar).

Pausa usada: >=1 s entre requisições; ~35 requisições no total; amostras baixadas só no scratchpad `pesquisa/`.
