# GO (Alego): pesquisa de endpoints, 2026-10-31

Base: `https://transparencia.al.go.leg.br/api/transparencia` (Rails, JSON, sem login/captcha, header `Accept: application/json`). Amostras em `.../pesquisa/go/`.
Catálogo de dados abertos do próprio site (todo endpoint aceita `.json`/`.csv` e `todos=true`): extraído do JS `application.transparencia-*.js` (lista: diarias, remuneracoes, servidores-terceirizados, servidores-licenciados-e-afastados, dueofs, orcamentos, licitacoes/avisos|editais, contratos, convenios, outras-contratacoes, atas-de-registro-de-preco, expedientes, requerimentos, diarios, verbas_indenizatorias). Não há proposições nem presença no catálogo.

Já coleta (coletar_estadual_go.py): deputados, verbas, remuneração (só 2026; API vazia 2023-25), diárias, votação nominal (`votacoes.json?tipo=detalhes`) com matérias votadas (autor vem em `ementa_projeto`: "AUTOR - X\nASSUNTO - ..."), requerimentos 2023 (API só até 2023).

## Itens do PR

| Item | Status |
|---|---|
| Deputados, diárias, remuneração, verba, voto nominal | JÁ TEM |
| Contratos do órgão | ENCONTRADO (esforço baixo) |
| Atas de registro de preço | ENCONTRADO (baixo) |
| Normas legais (leis, decretos legislativos, resoluções) | ENCONTRADO sem autoria (baixo) |
| Regras do ressarcimento (CEAP) / diárias em PDF | ENCONTRADO (baixo) |
| Atas de sessão (links) | ENCONTRADO parcial (baixo) |
| Pautas | ENCONTRADO parcial: agenda HTML sem itens (baixo/médio) |
| Presença em plenário | NÃO PUBLICA por deputado (derivável do voto; ver abaixo) |
| Gabinete (servidores por deputado) | NÃO PUBLICA |
| Proposições (projetos de lei) | BLOQUEADO / só as votadas |

## Detalhes

### Contratos (ENCONTRADO)
- `GET /contratos-e-convenios/contratos?pagina=1&por_pagina=N&data_inicio=AAAA-MM-DD&data_fim=AAAA-MM-DD` (também `contrato_vigente`, `tipo_contrato_id`, `possui_aditivo`, `termo`). `.json?todos=true` devolve tudo. HTTP 200 JSON, headers `TotalLinhas: 710`, `totalEmpenhado`, `totalPago`. Tipos: `/contratos-e-convenios/tipo_contratos`; anos: `/anos_contratos`.
- Campos: `id, numero ("23/2025"), numero_processo, tipo_contrato, descricao, nome_favorecido, cpf_cnpj (mascarado), data_inicio, data_fim, valor_empenhado, valor_pago, url (PDF no saba.al.go.leg.br), aditivo[{url_aditivo, data_inicial, data_final, valor}], licitacao{identificador, url_edital}, historico_gestor_suplentes[], historico_fiscal_contratos[]`.
- Exemplo: `{"id":662,"nome_favorecido":"VÓLUS INSTITUIÇÃO DE PAGAMENTO LTDA","cpf_cnpj":"03.817.702/0001-50","numero":"23/2025","valor_pago":149950.45,"url":"https://saba.al.go.leg.br/v1/view/aquisicoes/public/.../contrato-alego-662"}`.
- Liga ao deputado: não (é do órgão; gestor/fiscal são servidores, não deputados). Id estável: `id` da fonte.
- Riscos: `data_inicio` e `data_fim` vêm invertidas em alguns registros (id 662: início 2027, fim 2026); validar. CNPJ vem mascarado com pontuação: normalizar com `fornecedores.documento`. A primeira chamada sem `por_pagina` deu timeout uma vez; repetir com `por_pagina`. Volume pequeno (710 contratos, ~1 MB), sem necessidade de incremental.
- Também: `/contratos-e-convenios/convenios`, `/outras-contratacoes` (dispensas, inexigibilidades), `/fiscais_de_contratos`.

### Atas de registro de preço (ENCONTRADO)
- `GET /contratos-e-convenios/atas-de-registro-de-preco?pagina=1&por_pagina=N&ano=&mes=&carona=&termo=`. JSON, header `TotalLinhas`.
- Campos: `id, numero (" 09/2026"), ano, mes, objeto, orgao, carona, fornecedor{nome}, pedidos[], historico_gestor_suplentes[], url_ata (PDF), licitacao{identificador, url_edital}`. Sem CNPJ do fornecedor (só nome: usar `nome_chave`).
- Esforço baixo; mesmos riscos de pontuação (`numero` com espaço).

### Normas legais (ENCONTRADO, sem autoria)
- `GET /legislacoes?tipo=<id>&ano=AAAA` (ids em `/legislacoes/tipos`: Resoluções 0, Decretos Legislativos 10, Atos da Mesa 7, Decretos Administrativos 8, Atos Normativos Consolidados 9, Condecorações 6). Sem filtro devolve ~1 MB com todos os tipos agrupados (`{"legislacoes":[{"tipo":..,"leis":[...]}], "ultima_legislacao":{...}}`). `ano` e `tipo` filtram (tipo=0&ano=2026: 21 resoluções, 20 KB): serve de leitura incremental barata.
- Campos: `id, descricao ("DECRETO LEGISLATIVO N° 690, DE 2 DE SETEMBRO DE 2026. Aprova ..."), tipo, data_diario, created_at, ultima_atualizacao, get_arquivo_view_url (PDF), link_diario_oficial`.
- Não traz autor nem lista de deputado. Leis ordinárias estaduais não estão aqui (tipo "Estadual" só tem 2 links). Autoria só seria possível cruzando a descrição/nº com `ementa_projeto` das votações ("AUTOR - ..."), que é frágil. Recomendação: coletar como "normas do órgão" com link do PDF, sem ligar a deputado.
- Número e ano ficam só no texto da `descricao` (regex); ids da fonte `id` estáveis.

### Regras do ressarcimento / diárias (ENCONTRADO)
- Mesmo `/legislacoes` (tipo 9 e 0): Resolução 1.531/2015 (CEAP, cota para o exercício da atividade parlamentar; ids 21, 74) e Decretos Administrativos 3.017/3.018 de 2019 (diárias; ids 55, 56, 533, 555), cada um com `get_arquivo_view_url` PDF em saba.al.go.leg.br. Link fixo basta (constante no coletor ou busca por regex na descricao).
- Verba: `/verbas_indenizatorias/resumo-anual` exige `deputado_id` e `ano` (404 sem eles); `/verbas_indenizatorias/exibir/<id>` é o detalhe que o coletor atual já usa.

### Atas de sessão (ENCONTRADO parcial)
- `GET /atas_plenarias` (sem params): 3 linhas `{"ano":2022,"pdf":"/documentos/atas/2022.pdf","planilha":"/documentos/atas/2022.xlsx"}`, `2023 até 10/09/2023` (pdf+xlsx), e "a partir de 10/09/2023" apontando para `https://alegodigital.al.go.leg.br/spl/sessoes.aspx` (bloqueado, ver abaixo). Só links; dá para guardar os dois PDF/XLSX históricos. Base dos pdf: `https://transparencia.al.go.leg.br` (não testei o download).
- `/diarios?ano=&mes=&todos=true`: Diário da Assembleia por dia (`titulo "Edição nº 14.914", url PDF, houve_publicacao`), JSON, útil como fonte das normas por data.
- `/expedientes?ano=2026&pagina=1` (TotalLinhas 220): expedientes lidos nas sessões (assunto, destinatário, `sessao_plenaria{ano,mes,numero}`), sem deputado.
- `/sessoes-plenarias/datas-do-ano` só tem datas até 2023-10-05; `/sessoes-plenarias` e `/sessoes-plenarias/<data>` dão 404/500. Não servem.

### Pautas (ENCONTRADO parcial)
- Portal: `GET https://portal.al.go.leg.br/agenda?data=AAAA-MM-DD` (HTML, 100 KB, `li id=<evento>`; título, horário, local, "Presidente da Comissão", "Em pauta: Reunião ordinária."). Cobre futuro próximo (a home lista 3 a 5 dias adiante); histórico não testado.
- A pauta com itens (pauta prévia) está em `alegodigital.al.go.leg.br/spl/sessoes.aspx`, BLOQUEADO (abaixo). Pauta de votação já indireta: `votacoes.json?tipo=resumo&ano=&mes=` dá cada item votado por sessão (`pauta_id, numero_processo_projeto "PROCESSO 18677/2026 - 1ª DV - RESOLUÇÃO", ementa_projeto com AUTOR, resultado_votacao, tipo_votacao NOMINAL|SIMBOLICA, total_presentes, total_votos_sim|nao|abstencao`); 454 linhas em 2026-09. Esse `resumo` traz também as votações SIMBÓLICAS (8 em set/2026) que o `detalhes` não tem. Tipos aceitos: `detalhes`, `resumo` (`presenca`, `presencas`, `sessoes` dão 400 "Tipo inválido").
- Esforço: baixo para `resumo` (mesmo endpoint já usado, ano ou ano+mes, JSON), médio para agenda HTML.

### Presença em plenário (NÃO PUBLICA por deputado)
- Nenhum endpoint de presença. Só `total_presentes` (inteiro) por item em `votacoes.json?tipo=resumo` e o fato de o deputado ter voto em `detalhes`. Derivar "presente na sessão" = tem voto nominal na sessão: subestima (quem estava mas não votou) e deve ser rotulado como "votou em N de M votações nominais", não como presença oficial. A presença oficial pode estar no alegodigital (SPL), inacessível.

### Gabinete (NÃO PUBLICA por deputado)
- `/remuneracoes?ano=&mes=&categoria=<id>&status_pessoa=Ativo&pagina=` (TotalLinhas 7224, 10 por página; `.json?todos=true`). Categorias: 8 Cargos em Comissão, 9 Função Gratificada de Secretário Parlamentar (vazia em 2026-08), 6 Estagiários em Gabinete, 7 Deputados. Campo `lotacao` vem apenas como "Gabinete Parlamentar" (genérico, sem nome/ id do deputado) ou comissão/setor. Não dá para ligar servidor a deputado. Pode-se publicar no máximo "quantidade de servidores em Gabinete Parlamentar" agregada (não por deputado): sem valor.
- `/despesas-com-pessoal/servidores-terceirizados` (empresa, CNPJ, contrato, nome, função; sem deputado) e `/servidores-licenciados-e-afastados`: do órgão.

### Proposições (BLOQUEADO / parcial)
- `/processos/busca-avancada?pagina=1` responde 200 mas sempre `{"processos":[],"total_count":0}` com os parâmetros que tentei (`ano`, `ano_processo`, `tipo_processo`); nomes dos filtros não aparecem no JS do transparência (o app do "Opine Cidadão" usa; JS não carregado). `/processos/busca-simples` dá 500 com `termo`, `q`, `busca`. `/processos/<numero>` 404 "Proposição não existe". `/processos/recentes` devolve só 3 grupos de 6 a 16 itens (`autores[], a_favor, contra, assunto, numero "2023001806", situacao, data_autuacao, data_publicacao`), sem paginação útil.
- A consulta legislativa oficial é `https://alegodigital.al.go.leg.br` (SPL, ASP.NET; perfil do deputado liga para `spl/parlamentar.aspx?id=87`). Todas as conexões a esse host dão `Recv failure: Connection was reset` (curl normal, TLS1.2/HTTP1.1 e WebFetch), possível bloqueio de rede/WAF ou só aceita certos IPs. Não testei TLS inseguro. Pendente: tentar no runner do GitHub Actions (IP diferente) antes de descartar.
- O que já existe como substituto: as proposições VOTADAS, com autor no texto da ementa ("AUTOR - PAULO CÉZAR"), por `detalhes`/`resumo`. Autor vem como nome (liga por `ligar_nomes`), cobrindo só o que chegou a voto em plenário, não projetos apresentados.
- Requerimentos: `/requerimentos?ano=` só tem até 2023 (`/requerimentos/anos`), 2025 vazio (TotalLinhas 0): confirma a nota do coletor.

## Recomendação de ordem
1. `votacoes.json?tipo=resumo` (simbólicas + total_presentes + `numero_processo_projeto`): baixo.
2. Contratos + atas de registro de preço (dois GETs paginados, ~1 MB): baixo.
3. Normas (`/legislacoes?ano=`) + links CEAP/diárias: baixo, sem autoria.
4. Testar alegodigital a partir do Actions para proposições/presença/pauta/atas.
Itens sem fonte pública: gabinete por deputado, presença oficial.

## Ritmo
Todas as chamadas acima: 1 a 2 s de pausa, ~35 requisições no total. A API devolve 403 sob rajada (o coletor já tem `PAUSA_403`).
