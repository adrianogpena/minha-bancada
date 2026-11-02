# MS (ALEMS) - pesquisa de endpoints equivalentes ao coletor do PR

Testado em 2026-10-31 com curl, UA Mozilla, pausa de 2 s. Nada gravado no repo.
Portais: `transparencia2.al.ms.gov.br` (novo, JSON/CSV, sem captcha), `www.transparencia.al.ms.gov.br/pages/index.php/gerdocumento/<id>` (antigo, árvore de pastas com PDFs), `al.ms.gov.br` (site institucional, HTML), `sgpl.consulta.al.ms.gov.br` (proposições, PoW), `diariooficial.al.ms.gov.br`.

## Resumo

| Item PR | Status MS |
|---|---|
| deputados | JÁ TEM (TSE) |
| proposições | BLOQUEADO (SGPL com captcha PoW); parcial por HTML (pauta) |
| normas legais com autoria | NÃO PUBLICA em dado aberto (só PDFs/Diário) |
| votação nominal | BLOQUEADO / não localizada fora do SGPL |
| presença em plenário | NÃO PUBLICA (não encontrada) |
| diárias | JÁ TEM |
| remuneração | ENCONTRADO (PDF mensal, texto extraível) |
| gabinete | ENCONTRADO PARCIAL (servidores sem lotação no deputado) |
| pautas e atas | ENCONTRADO (pauta/ordem do dia em HTML; atas em PDF) |
| contratos e atas RP | ENCONTRADO (árvore de PDFs) |
| regras da verba | ENCONTRADO parcial (PDFs em pastas) |
| CEAP | JÁ TEM |

## Já coletado
- CEAP CSV: `https://transparencia2.al.ms.gov.br/ceap/notas/exportar-csv?ano=AAAA` (2012+, aqui 2023+).
- Diárias CSV: `https://transparencia2.al.ms.gov.br/consulta-diarias/exportar-csv?ano=AAAA` (2021-2026 "Não houve despesa").
- Deputados: TSE 2022.

## Proposições / votação nominal - BLOQUEADO
- UI: `https://sgpl.consulta.al.ms.gov.br/sgpl-publico/#/busca-proposicoes` (AngularJS; `main.js` 324 KB).
- API REST encontrada no JS público, base `https://sgpl.consulta.al.ms.gov.br/sgpl/sgpl-api/public/`: `proposicoes/`, `proposicao/:id`, `proposicao/:id/modeloDocumento`, `tipoProposicao`, `assunto/todos`, `atividade/filtro`, `proponente/autoria`, `proponente/autoriaComLegislatura`, `localidade?idEstado=12`, `parametrosSistema`, `captcha/challenge`.
- Teste: `GET .../public/tipoProposicao` sem token -> 403 "Invalid CAPTCHA solution". `GET .../public/captcha/challenge` -> 200 `{"challengeId":"...","prefix":"...","complexity":16,"algorithm":"SHA-256"}`: é proof-of-work (o navegador resolve sozinho, "Validando acesso..."), não captcha visual.
- NÃO resolvi o desafio (é controle de acesso contra automação; contornar fica para decisão do dono). Se for aceito resolver PoW (complexity 16 = ~65 mil hashes, trivial), a API teria proposições com autoria (`proponente/autoria`) por id, mas não verifiquei campos, paginação nem votação (votação nominal não aparece nas rotas listadas; só `proposicao-linha-tempo-processo`).
- Risco: alto (burla de proteção anti-bot, pode mudar, host pode bloquear IP do Actions). Esforço: alto.
- Alternativa pública sem captcha (parcial, só o que está em pauta agora, sem histórico):
  - `https://al.ms.gov.br/Pauta` (HTML, 200, 41 KB): "Projeto de Lei nº 151/2026 Processo nº 289/2026 Deputado ANTONIO VAZ - ementa", com prazo de emendas. Autoria por nome (liga via `identidades.ligar_nomes`), tipo, número, processo, ementa.
  - `https://al.ms.gov.br/Ordemdodia` (HTML, 37 KB): sessão do dia, fase (1ª/2ª discussão), projeto, autor, ementa, pareceres.
  - Só um instantâneo; para histórico precisaria guardar a cada coleta diária. Esforço: baixo-médio. Risco: HTML mudar; autor pode ser "PODER EXECUTIVO" ou comissão.

## Normas legais (leis/decretos/resoluções com autoria) - NÃO PUBLICA como dado
- `https://al.ms.gov.br/upload/Pdf/LeiseResolu%E7%F5esdeConcess%F5esdaALEMS.pdf` (PDF de concessões) e Diário Oficial.
- Diário Oficial: `GET https://diariooficial.al.ms.gov.br/DiarioOficial/DiarioList?retNum=&retDT=DD/MM/AAAA` -> JSON (200) `[{"id":30332,"dtPub":"29/10/2026","numDiario":"Diário Oficial Eletrônico nº 3175","linkURL":"/DiarioOficial/DownloadPdf?q=..."}]`. Sem filtro ano; sem param retorna os 10 mais recentes; `retDT` filtra um dia; `retNum` filtra número. Só PDF da edição inteira, sem autoria estruturada. Esforço de extrair normas: alto (parse de PDF). Útil só como link de fonte.
- Resposta em UTF-8 com `Content-Type` correto.

## Presença em plenário - NÃO PUBLICA
Nenhuma página de presença/frequência em transparencia2, gerdocumento ou al.ms.gov.br. Notas taquigráficas e atas (PDF) trazem presentes só em texto livre.

## Remuneração - ENCONTRADO (PDF)
- Árvore: `http://www.transparencia.al.ms.gov.br/pages/index.php/gerdocumento/1201` (pasta com anos 2020..2026: ids 1202, 1302, 1538, 1835, 2599, 4049, 5167 = 2026) -> cada ano lista meses com `https://www.transparencia.al.ms.gov.br/uploads/<hash>.pdf`.
- Exemplo 2026 (pasta 5167): Setembro `uploads/0971a140a253946b7edbb77d3bec3fd5.pdf` (43 KB, application/pdf). `pdftotext -layout`: "Relatório Demonstrativo de Pagamento - Referência: Setembro/2026 - Deputado Estadual"; por deputado: nome + matrícula, eventos (SUBSÍDIO 34.774,64, verbas, PLANO DE ASSIST., IMPOSTO DE RENDA...), Sub Total crédito/débito/líquido (38.708,07). Layout em colunas empilhadas (rótulos quebrados) - parse frágil.
- Liga por nome (`ligar_nomes`). Não tem filtro de data; cobertura 2020+; poucos PDFs (12/ano).
- Servidores (para comparação): `https://transparencia2.al.ms.gov.br/consulta-servidores/data?page=N&perPage=50&sort=nome&dir=asc` (JSON; ver Gabinete). Tabelas de salário por exercício também em PDFs gerdocumento (1994 = servidores).
- Esforço: médio. Risco: layout do PDF, IDs de pasta mudam (a pasta do ano novo só aparece depois), HTTP sem TLS no link da home (https responde 200).

## Gabinete - PARCIAL
- `GET https://transparencia2.al.ms.gov.br/consulta-servidores/data?page=1&perPage=50&sort=nome&dir=asc&q=<texto>` -> JSON 200: `{"rows":[{"matricula":"8664","nome":"ABEL NUNES PROENCA JUNIOR","cargo":"ASSESSOR DE GABINETE PARLAMENTAR XI","simbolo":"PLAP.06.11","nome_destaques":[]}],"total":1195,"page":1,"perPage":50}`. perPage fica em 50 (pediu 500, voltou 50): 24 páginas para tudo, com pausa de 1-2 s. Sem token. Resposta com bytes em Latin-1/CP1252 (acentos aparecem como ? ao ler como UTF-8: decodificar com cuidado).
- Campos: matrícula, nome, cargo, símbolo. NÃO traz lotação/gabinete nem deputado: dá para listar quem tem cargo "ASSESSOR DE GABINETE PARLAMENTAR" (e salário por símbolo), mas não ligar ao deputado. Para ligar ao deputado teria de achar a lotação em outra fonte (não achei; cargos "PLAP.*" não identificam deputado).
- Decisão: coletar a lista como "servidores da Casa" com cargo, sem ligar a deputado, só serve a contagens gerais. Esforço: baixo para lista, inviável para gabinete por deputado. Atualizada até a data mostrada na página (29/10/2026).

## Pautas e atas - ENCONTRADO
- Pauta/Ordem do Dia: ver acima (HTML, `https://al.ms.gov.br/Pauta`, `/Ordemdodia`, `/ReuniaoCCJR`); agenda: `https://al.ms.gov.br/Calendars/List`.
- Atas e notas taquigráficas (PDFs): `gerdocumento/2040` (Atividade Legislativa: 2049 CCJR, 2050 Sessões Ordinárias, 2051 Seminários, 2052 Sessões Solenes, 2053 Reuniões, 2054 Frentes, 2055 Comissões, 2057 Audiências) -> `2050`: 2127 Notas Taquigráficas, 2128 ATA -> anos (2201 = 2021, 2202, 2203, 2761 = 2024...) -> PDFs por sessão.
- Link por sessão/data, sem deputado. Esforço: médio (percorrer pastas; só as do ano corrente por coleta). Há também `https://transparencia2.al.ms.gov.br/home/atividadelegislativa`.

## Contratos e atas de registro de preço - ENCONTRADO (PDF)
Árvore `gerdocumento/52` (licitações e contratos): 1230 Inexigibilidade, 1231 Dispensa, 1232 Pregão, 1233 Anteriores, 1234 Convite, 1235 Tomada de Preço, 1236 Concorrência, 1339 Sancionados, 1874 ATA REGISTRO DE PREÇO, 1997 Fiscais de Contratos, 5487 Regulamento. Cada pasta lista anos -> PDFs.
- Atas RP: 1874 -> 1887 "Adesão ata RP" -> anos (3790 = 2021 ... 4496 = 2025) -> "Atas de Adesão 2021" PDF.
- Fiscais de contratos: 1997 -> 2022..2026 (3602, 3603, 3604, 4499, 5329).
- Transferências/convênios: 2891 -> 2892, 2894, 2896. Obras: 2951.
- Só PDFs com título, sem fornecedor/valor estruturados. Serve como lista de links por tipo/ano (equivale ao "contratos e atas do órgão" do PR, mas sem metadados). Esforço: médio (crawl de ~3 níveis), risco: ids de pastas por ano novo; HTML antigo (Latin-1).

## Regras/PDF do ressarcimento (verba) - PARCIAL
- `https://transparencia2.al.ms.gov.br/pagina/ceap` (explicação em texto, sem PDF) e `gerdocumento/257` -> 274 Verba Indenizatória (2011, 2012...), 1200 "Cota parlamentar" (regras/atos); `gerdocumento/258/263` etc. Atos normativos: `gerdocumento/758` (Ato nº 001-CTJ Mesa Diretora, PDF `uploads/Ato_001_CTJ_MesaDiretora_phprn415S.pdf`).
- Dá para linkar as páginas/PDFs como fonte da regra. Esforço: baixo.

## Outros
- Quadro mensal de CEAP por deputado já vem do CSV; endpoint de totais: `https://transparencia2.al.ms.gov.br/ceap/data?ano=2026` (JSON, agrupado por deputado/ano/mês; filtro `fornecedor`) para conferência.
- Todos os endpoints do transparencia2 usam o componente `gridlist` (`/<rota>/data`, parâmetros `page`, `perPage<=50`, `sort`, `dir`, `q`); rotas conhecidas: `consulta-servidores`, `ceap`, `consulta-diarias`.
- Não encontrei portal de dados abertos (`dadosabertos.al.ms.gov.br` sem resposta).
- `ENDPOINTS.md` precisaria registrar: `diariooficial.al.ms.gov.br`, `al.ms.gov.br` (Pauta/Ordemdodia), `www.transparencia.al.ms.gov.br` e `consulta-servidores/data`, se forem coletados.

## Prioridade sugerida
1. Pauta/Ordem do dia (HTML, baixo) -> pautas + proposições em tramitação com autoria.
2. Remuneração dos deputados (PDF mensal, médio).
3. Contratos/atas RP/atas de sessão como links (médio).
4. Servidores (lista sem lotação, baixo, pouco valor).
5. Proposições completas/votação: só via SGPL, bloqueado por PoW; decidir à parte.
