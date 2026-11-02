# MT (ALMT) - pesquisa de endpoints equivalentes ao coletor do PR

Data: 2026-10-31. Amostras em scratchpad/pesquisa/mt/.

Base única que responde: portal Elotech `https://almt.eloweb.net/portaltransparencia-api/api` (sem login, sem captcha; cabeçalhos `Accept: application/json`, `entidade: 1`, `exercicio: <ano>`; paginação Spring `page`/`size`, `size=500` aceito; resposta `{content, totalElements, last}`).
O site institucional `www.al.mt.gov.br` (201.71.136.x) dá timeout em curl (IPv4, UA de navegador, http/https) e em WebFetch. Não foi possível testar nada dele. Pode responder só de certos IPs (não testado a partir do runner do GitHub Actions).
`storage.al.mt.gov.br/api/v1/download/default/<id>` responde 200 (PDF), mas sem listagem; os ids só são conhecidos pelas páginas do site.

## Resumo por item

| Item do PR | Status | Esforço |
|---|---|---|
| deputados | JÁ TEM | - |
| remuneração | JÁ TEM | - |
| diárias | JÁ TEM | - |
| gabinete (servidores lotados) | ENCONTRADO | baixo |
| contratos do órgão | ENCONTRADO | baixo/médio |
| atas de registro de preço | ENCONTRADO (mesmo endpoint) | baixo |
| regras de diárias (PDF/tabela) | ENCONTRADO (links) | baixo |
| ressarcimento/verba (dados) | NÃO PUBLICA | - |
| ressarcimento/verba (regras PDF) | NÃO PUBLICA no portal; BLOQUEADO no site | - |
| proposições | BLOQUEADO (site fora do alcance) | alto |
| normas legais com autoria | BLOQUEADO | alto |
| votação nominal | BLOQUEADO / provável NÃO PUBLICA | - |
| presença em plenário | BLOQUEADO / provável NÃO PUBLICA | - |
| pautas (ordem do dia) e atas | BLOQUEADO (URLs conhecidas por busca) | médio |

## Gabinete (servidores lotados) - ENCONTRADO
- URL: `GET {API}/servidores?entidade=1&exercicio=<ano>&lotacao=GAB&page=N&size=500` (mesmo endpoint já usado em `buscar_servidores`, que passa `cargo=DEPUTADO`).
- Filtro `lotacao=` é por substring: `lotacao=GAB` devolve 2005 registros em 2026 (de 4123 no total) e 1930 em 2023; `lotacao=DILMAR` devolve 66 (assessores de um gabinete). `codigoLotacao=` e `situacao=` NÃO filtram (ignorados; total volta 4123). Filtrar por situação no código.
- Campos: `matricula`, `nome`, `descricaoCargo` (ex.: ASSESSOR PARLAMENTAR, ASSESSOR DE IMPRENSA DE GABINETE), `codigoLotacao` (ex.: 006733001), `descricaoLotacao` ("GAB DEP DILMAR DAL BOSCO"), `descricaoClasse`, `faixa` (AP-2), `situacao` (ATIVO/EXONERADO), `dataAdmissao`, `dataDemissao`, `horasSemanais`, `remuneracao` (valor da listagem).
- Exemplo: `{"matricula":50063,"nome":"ABIQUEILA PIRES FRANÇA","descricaoCargo":"ASSESSOR PARLAMENTAR","descricaoLotacao":"GAB DEP DILMAR DAL BOSCO","faixa":"AP-2","situacao":"ATIVO","dataAdmissao":"2026-03-02","remuneracao":3971.0}`
- Liga ao deputado só por texto da lotação ("GAB DEP <nome parlamentar>"): reusar `nome_do_gabinete` + `identidades.ligar_nomes` (estratégia em `ESTRATEGIAS`), ou pelo `codigoLotacao` comparado com o do próprio deputado em `/servidores` (o deputado tem `descricaoLotacao` do gabinete; conferir se `codigoLotacao` coincide, não testado). Lotações que não são de deputado ("GAB PRESIDENCIA", "UNIDADE ...") ficam de fora ou vão para o órgão.
- Salário individual por mês: `/servidores/{matrícula}` (`dadosFinanceiros`), uma chamada por servidor; com 2000 servidores é pesado: usar só `remuneracao` da listagem, ou detalhe escalonado.
- Cobertura: 2023-2026 (exercício vai no cabeçalho). Volume: 5 páginas/ano. Sem filtro de data; releitura diária completa é barata (5 req).
- Esforço: baixo. Risco: nome de gabinete com apelido/aspas (já tratado em `nome_do_gabinete`); servidor aparece em mais de um ano (id estável = matrícula).
- Também existe `GET {API}/ajuda-custo?...` (lista de assessores com cargo, 10650 registros, sem valores): sem utilidade.

## Contratos e atas de registro de preço do órgão - ENCONTRADO
- Lista: `GET {API}/contratos?entidade=1&exercicio=<ano>&page=N&size=200`. Totais: 2023=100, 2024=91, 2025=104, 2026=129. Contrato e ata no mesmo endpoint, distinguidos por `descricaoTipoAto` ("Contrato" 83, "Registro de Preço" 46 em 2026); `tipoAto=2` filtra só atas (46).
- Campos: `contrato`, `numeroContrato`, `displayContrato` (202645/2026), `cnpjCpf` (só dígitos; validar com `fornecedores.documento`), `nome`, `inicioVigencia`, `terminoVigencia`, `valorContratado`, `valorAditivo`, `situacao` (Vigente...), `tipoContrato` ("2 - Compra"), `descricaoTipoLicitacao`, `displayLicitacao` (17/2025), `objeto`, `itens` (vazio na lista).
- Exemplo: `{"contrato":"214","numeroContrato":202645,"cnpjCpf":"50390402000118","nome":"SEVEN DIGITAL GRAFICA E EDITORA LTDA","inicioVigencia":"2026-07-15","terminoVigencia":"2027-07-15","valorContratado":316125.0,"descricaoTipoAto":"Registro de Preço","situacao":"Vigente","displayLicitacao":"17/2025"}`
- Arquivos (contrato/ata em PDF): `GET {API}/contratos/arquivos?entidade=1&exercicio=2026&contrato=214&tipoAto=2` -> `[{"idArquivo":93826,"dataPublicacao":"2026-07-20","nomeArquivo":"ATA DE REGISTRO DE PREÇO 45-2026 P.E 017.pdf"}]`; download: `GET {API}/files/arquivo/93826` (200, application/pdf, sem auth; precisa dos cabeçalhos entidade/exercicio). Montar só o link, não baixar PDF.
- Licitações relacionadas: `GET {API}/licitacoes?...` (campos `ataDeAdesao`, `valorMaximo`, `totalVencido`) e `GET {API}/contratos/licitacao?entidade&exercicioLicitacao&tipoLicitacao&numeroLicitacao`.
- Leitura incremental: `GET {API}/contratos/ultimas-atualizacoes` -> `[{"modulo":"10","ultimoAcesso":"2026-10-29T16:23:58"}]`: reler o ano corrente só se mudou. Sem filtro por data na lista. Anos encerrados: `comum.ano_encerrado`.
- Adesões de ARP concedidas pela ALMT: só PDFs na publicação (grupo 1013, ver abaixo), sem dado estruturado.
- Liga a pessoa? Não há deputado: dado do órgão (não de político), entra como `contratos_<ano>.json` do órgão, fornecedor por `fornecedores.documento`/`nome_chave`.
- Esforço: baixo (3-4 req/ano + arquivos por contrato, 1 req cada, ~130/ano: buscar só dos novos). Risco: `/contratos/arquivos` é uma chamada por contrato.

## Pautas/atas, regras de diárias e documentos - ENCONTRADO (só links)
- Publicações por grupo: `GET {API}/publicacoes?entidade=1&exercicio=<ano>` (178 KB) devolve árvore de grupos (`id`, `valor`) com arquivos (`nomeArquivo`, `dataArquivo`, `idArquivo`), download `GET {API}/files/arquivo/{idArquivo}`.
- Útil: grupo 1084 "Legislações de Diárias" (Resolução Administrativa nº 006.2025.MD.ALMT.pdf, idArquivo 92472, e "Tabela Diárias Atualizada.xlsx", 92658, 2026-05-13) = regras das diárias; grupos 1128/1050 "Resoluções Administrativas"; 1013 "Adesões de ARP concedidas pela ALMT"; 1095 "PORTARIAS"; 1164 "Arquivos de Nomeações".
- Não há grupo de verba indenizatória/cota/ressarcimento, de pauta, de ata de sessão nem de votação (conferido por nome em todos os 60 grupos).
- Esforço: baixo (um JSON, só links). Risco: estrutura de grupos muda; ler por `valor`, não por id.

## Ressarcimento / verba indenizatória - NÃO PUBLICA
- `GET {API}/servidores/verbas/{evento}/{mês}` e `GET {API}/reembolsos?...` (2023-2026) respondem lista vazia; `/emendas-parlamentares` também. A rota `/cotas-parlamentares` do portal não chama API de dados.
- Base legal indireta: Lei 9.626/2011 e consulta TCE-MT 21/2023 (resposta: o Legislativo pode criar a verba por ato normativo); o regulamento atual da ALMT não foi achado (busca web) nem está no portal.
- Para regras em PDF resta o site (`www.al.mt.gov.br/storage/webdisco/...`), bloqueado aqui.

## Proposições, normas legais, votação nominal, presença, pautas e atas - BLOQUEADO
- Tudo está em `www.al.mt.gov.br` (timeout de conexão em todas as tentativas, ENDPOINTS.md já registra `mt_site` com ConnectTimeout). Páginas conhecidas por busca (não testadas):
  - Proposições em tramitação: `https://www.al.mt.gov.br/proposicao` (lista com tipo, número/ano, autor "Dep. X", protocolo e processo); detalhe `https://www.al.mt.gov.br/proposicao/cpdoc/<id>/visualizar` (ex.: 165590, 156343, 122548); comissões: `/proposicao/comissao-parlamentar` e `/proposicao/comissao-parlamentar/cpdoc/<id>/visualizar`. HTML renderizado (parece ser servidor); autor por nome do deputado (ligar via `identidades.ligar_nomes`).
  - Ordem do dia: `https://www.al.mt.gov.br/parlamento/ordem-do-dia` (lista de sessões com PDF); PDFs em `https://storage.al.mt.gov.br/api/v1/download/default/<id>` (ex.: 868716 = ordem do dia de 25/02/2026, PDF de 3 páginas, 275 KB, baixou 200 daqui).
  - Agenda: `https://www.al.mt.gov.br/parlamento/agenda/assembleia`.
  - Leis (ex.: "Lei nº 13.232/2026"): aparecem no texto da tramitação; não há página de normas localizada.
  - Votação nominal e presença por deputado: nenhuma página localizada nas buscas (só notícias com resultado agregado); provável NÃO PUBLICA estruturado.
- SAPL: `https://sapl.al.mt.leg.br/api/` responde 200, mas é instância abandonada (só legislatura 18ª 2015-2018, 25 parlamentares antigos, 0 matérias, 0 registros de votação, 2 normas de 2015, 5 sessões). Não usar.
- Próximo passo para destravar: testar `www.al.mt.gov.br` a partir do runner do GitHub Actions (um job de teste com `curl -m 30`) ou de outra rede; se responder, medir paginação de `/proposicao` e se há filtro de data.
- Esforço se destravar: alto (HTML, sem API documentada). Risco: bloqueio por IP, estrutura HTML.

## Já coletado (referência)
deputados (`/servidores?cargo=DEPUTADO`), remuneração (`/servidores/{matrícula}`), diárias (`/diarias`, filtro `dataInicial`/`dataFinal` já permite incremental por período).
