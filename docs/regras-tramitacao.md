# Regras de tramitação das proposições

Base de conhecimento (só procedimento, sem opinião e sem resumo de projetos) de como cada tipo de proposição tramita no Congresso Nacional, que caminhos pode seguir e como reconhecemos cada etapa nos campos que o site já coleta. A tabela `ETAPAS_POR_TIPO` de `site/assets/js/etapas.js` é a tradução desta base; um teste confere que as duas têm os mesmos ids de etapa.

Como ler:
- Cada tipo tem um **caminho principal** (a sequência mais comum, a que a faixa mostra) e uma **tabela de arestas** (os desvios possíveis: não é uma linha só).
- Cada etapa é um cabeçalho `#### \`id\` — Rótulo`. Os ids estão em minúsculas e hífen.
- "Como reconhecer" usa os campos já coletados. Senado: `situacoes[i][3]` (descrição da situação), `despachos [dia, provimento, destinos[], terminativa]`, na ficha `dl{t,d,p}` (deliberação: texto, data, plenário/comissão), `ng` (norma gerada), `cn/cd/cdx` (número na Câmara). Câmara: `eventos [dia, orgao, tipo, situacao, despacho]`, índice `p.s` (situação), `sf` (ficha vinda do Senado), `ng`.
- Etapa sem campo que a reconheça fica marcada **"não reconhecível com os dados atuais"**: a faixa só a mostra como futura ou, se já passou, deduz pelas etapas seguintes.
- A caixa da situação difere por Casa (Senado em MAIÚSCULAS, Câmara em Title Case): compare sem diferenciar caixa nem acento.
- Situação da fonte que nenhuma etapa reconhece **não aponta etapa**: o site mostra só a situação crua, sem faixa. Os nomes de situação reconhecidos são nomes inteiros; a classe de cada código oficial (Senado 175 situações, 33 decisões; Câmara 99 situações, 235 tipos de tramitação) está em `tests/fixtures/contratos/situacoes_etapas.json` e um teste a compara com o reconhecimento. Só entra o nome que este documento lista; os demais ficam "sem classe".
- Regra de ouro do reconhecimento: vale o evento mais recente. Uma etapa posterior reconhecida marca como feitas (ou puladas, quando a proposição não passou por ela) todas as anteriores.

Vocabulário real observado nos dados (índice local, 9.419 proposições): Senado, `situacoes[i][3]` tem 20 valores nas matérias coletadas, entre eles AGUARDANDO DESPACHO, AGUARDANDO RECEBIMENTO DE EMENDAS, AGUARDANDO DESIGNAÇÃO DO RELATOR, MATÉRIA COM A RELATORIA, MATÉRIA DESPACHADA, INCLUÍDA NA PAUTA DA REUNIÃO, PRONTA PARA A PAUTA NA COMISSÃO, APROVADO PARECER NA COMISSÃO, APRECIADA EM DECISÃO TERMINATIVA PELAS COMISSÕES, AGUARDANDO INTERPOSIÇÃO DE RECURSO, PRONTO PARA DELIBERAÇÃO DO PLENÁRIO, INCLUÍDA EM ORDEM DO DIA, APROVADA, REMETIDA À CÂMARA DOS DEPUTADOS, REMETIDA À SANÇÃO, TRANSFORMADA EM NORMA JURÍDICA, RETIRADA PELO AUTOR, PEDIDO DE VISTA CONCEDIDO, AGUARDANDO AUDIÊNCIA PÚBLICA, MATÉRIA EM TRAMITAÇÃO. Provimentos de despacho: "Análise", "Tramitação Conjunta", "Ao Plenário". Em `p.s` aparecem ainda PREJUDICADA, ARQUIVADA AO FINAL DA LEGISLATURA. Câmara em `p.s`: "Aguardando Designação de Relator(a)", "Tramitando em Conjunto", "Aguardando Parecer", "Pronta para Pauta", "Aguardando Encaminhamento", "Arquivada", "Transformada em Norma Jurídica", "Aguardando Despacho do Presidente da Câmara dos Deputados (Chancela)".

---

## Tipo: PL, PLP

Projeto de lei ordinária (PL) e projeto de lei complementar (PLP). Iniciativa: deputados, senadores, comissões, Presidente da República, tribunais superiores, Procurador-Geral da República e cidadãos, conforme a matéria (CF art. 61). PLP exige maioria absoluta para aprovação (CF art. 69); PL, maioria simples. A Casa onde o projeto nasce é a **Casa de origem** (Câmara ou Senado); a outra é a **Casa revisora** (CF art. 64 e 65). Projeto de iniciativa do Presidente da República, do Supremo Tribunal Federal ou dos Tribunais Superiores tem a discussão e a votação iniciadas na Câmara (CF art. 64, caput): a Câmara é sempre a Casa de origem deles. O Presidente da República pode pedir urgência para projeto seu: se a Câmara e o Senado não se manifestarem, cada uma em até 45 dias, as demais deliberações da Casa ficam sobrestadas até a votação, salvo as de prazo constitucional; a Câmara aprecia as emendas do Senado em 10 dias; os prazos não correm no recesso nem valem para projeto de código (CF art. 64 §§1-4; RICD art. 204). A revisão pela outra Casa é em turno único (CF art. 65).

**Caminho principal:** `apresentado` → `comissoes` → `plenario-origem` → `casa-revisora` → `sancao-veto` → `lei`.

### Etapas

#### `apresentado` — Apresentado
Projeto protocolado, ainda sem relator ou sem despacho às comissões.
- **Como reconhecer.** Senado: situação da classe `abertura` (tabela "Nomes de situação reconhecidos") sem nenhum `despachos` ainda; ou primeira entrada de `situacoes`. Câmara: `p.s` da classe `abertura` (inclui "(Chancela)"), ou `eventos` só com o tipo de apresentação.
- **O que pode acontecer depois.** Receber despacho às comissões (`comissoes`), ir direto ao plenário (`plenario-origem`, com urgência ou despacho "Ao Plenário"), ser retirado pelo autor ou arquivado (`arquivado`).
- **O que ainda falta.** "Ainda não é lei. O projeto foi apresentado e aguarda o despacho que define por quais comissões ou plenário ele passa."

#### `comissoes` — Comissões
Análise do mérito e da constitucionalidade nas comissões da Casa de origem.
- **Como reconhecer.** Senado: `despachos[i][1]` = "Análise" com `destinos[]` de comissões; situação da classe `comissao`. "Tramitação Conjunta" indica projeto apensado a outro. Câmara: `p.s` da classe `comissao` (inclui "Tramitando em Conjunto"); `eventos[i][1]` com sigla de comissão (CCJC, CFT e semelhantes).
- **Etapa pulada.** Se o despacho for direto ao Plenário (provimento "Ao Plenário" no Senado) ou houver urgência aprovada antes do parecer, a etapa aparece como pulada (tracejada).
- **O que pode acontecer depois.** Parecer aprovado e ida ao Plenário (`plenario-origem`); decisão terminativa (Senado) ou conclusiva (Câmara) que dispensa o Plenário, nos limites abaixo; rejeição que arquiva; requerimento de urgência que leva ao Plenário (no Senado, pode incluir em Ordem do Dia matéria pendente de parecer, RISF art. 336 III; na Câmara a urgência não dispensa os pareceres das Comissões ou de Relator designado, RICD art. 152 §1º II).
- **Quando a comissão decide sozinha.** Senado (RISF art. 91 I): só projeto de lei ordinária de autoria de Senador, ressalvado projeto de código; para as demais matérias do §1º depende de o Presidente do Senado, ouvidas as lideranças, conferir a competência. **PLP e PL vindo da Câmara não estão entre os casos do art. 91 I.** Câmara (RICD art. 24 II): só projeto de lei, exceto os de lei complementar, de código, de iniciativa popular, de Comissão, os de matéria que não possa ser delegada (CF art. 68 §1º), os oriundos do Senado ou por ele emendados que tenham sido aprovados pelo Plenário de qualquer das Casas, os que tenham recebido pareceres divergentes e os em regime de urgência. **PLP nunca é conclusivo na Câmara.**
- **Recurso ao Plenário.** Senado: 5 dias úteis a partir da publicação da comunicação da decisão, com assinatura de um décimo dos Senadores (RISF art. 91 §§3 e 4). Câmara: 5 sessões a partir da publicação, com assinatura de um décimo dos Deputados (RICD art. 58 §§1 e 3). Sem recurso, o projeto é, no Senado, "encaminhado à sanção, promulgado, remetido à Câmara ou arquivado, conforme o caso" (RISF art. 91 §5) e, na Câmara, vai à redação final e depois ao Senado ou à Presidência da República (RICD art. 58 §§4 e 5).
- **O que ainda falta.** "Ainda não é lei. O projeto está nas comissões, que dão parecer; depois segue ao Plenário, a não ser que a comissão decida sozinha (terminativa/conclusiva)."

#### `plenario-origem` — Plenário da Casa de origem
Votação em Plenário (turno único) na Casa onde o projeto foi apresentado.
- **Como reconhecer.** Senado: situação da classe `plenario`; na ficha `dl.p` = Plenário e `dl.d` com a data. Câmara: nenhum nome de situação da classe `plenario` existe na lista oficial; vale `eventos[i][3]` com aprovação no Plenário (descrição contendo "Aprovad" e órgão PLEN) (não conferido). "Pronta para Pauta" é da classe `comissao`, mesmo com órgão PLEN.
- **O que pode acontecer depois.** Aprovado: vai à Casa revisora (`casa-revisora`); aprovado na Casa iniciadora em decisão terminativa/conclusiva e sem recurso, segue conforme a regra do tipo (Senado: REMETIDA À CÂMARA DOS DEPUTADOS; Câmara: remessa ao Senado). Rejeitado: `arquivado`. Retirado: `arquivado`.
- **O que ainda falta.** "Ainda não é lei. O Plenário vota; se aprovar, o texto vai à outra Casa para ser revisto."

#### `casa-revisora` — Casa revisora
A outra Casa analisa o texto: comissões e Plenário. Recebe número novo (`cn/cd/cdx` quando o projeto é do Senado e foi à Câmara).
- **Como reconhecer.** Senado como origem: situação REMETIDA À CÂMARA DOS DEPUTADOS (RMCD, classe `outra-casa`; em `situacoes[i][3]`), e `cn/cd/cdx` com o número na Câmara; em seguida os `eventos` da Câmara do projeto de mesmo `cn`. Câmara como origem: `p.s` "Aguardando Apreciação pelo Senado Federal" (código 926, classe `outra-casa`) e, na ficha, `sf` preenchido (a matéria veio do Senado). Senado como revisora: matéria com `sf`/origem da Câmara e despacho do Senado.
- **O que pode acontecer depois.** Aprovar sem mudar (`sancao-veto`); aprovar com mudanças (emendas ou substitutivo), e então volta à Casa de origem (`retorno-origem`); rejeitar (`arquivado`).
- **O que ainda falta.** "Ainda não é lei. A [Casa revisora], como Casa revisora, pode aprovar, mudar ou rejeitar o texto; se mudar, ele volta à Casa de origem. Depois vai à sanção."

#### `retorno-origem` — Volta à Casa de origem
Só ocorre quando a Casa revisora alterou o texto. "Sendo o projeto emendado, voltará à Casa iniciadora" (CF art. 65, parágrafo único). O que a Casa de origem pode fazer com as mudanças (aceitar ou rejeitar cada uma, vedado texto novo) vem do regimento e não foi conferido nesta base.
- **Como reconhecer.** Nenhum nome da lista oficial de situações indica o retorno: as situações "APROVADA(S) EMENDA(S) DO SENADO FEDERAL" e "REJEITADA(S) EMENDA(S) DO SENADO FEDERAL" (Senado), "Aguardando despacho de Emenda" e "Aguardando despacho de Substitutivo" (Câmara) existem na lista, mas não há texto oficial lido que as ligue a esta etapa (não conferido); por isso a etapa não é reconhecida pela situação. Câmara: `eventos` posteriores ao envio com órgão PLEN e tipo de apreciação de emendas do Senado (não conferido). Não reconhecível com os dados atuais quando a fonte não distingue o retorno.
- **O que pode acontecer depois.** Concluída a votação, a Casa enviará o projeto ao Presidente da República (CF art. 66, caput): `sancao-veto`. O efeito de rejeitar as mudanças da revisora não foi conferido.
- **O que ainda falta.** "Ainda não é lei. O texto foi mudado na outra Casa e voltou para a Casa de origem decidir sobre as mudanças. Depois vai à sanção."

#### `sancao-veto` — Sanção ou veto
O Presidente da República tem 15 dias úteis para sancionar ou vetar (CF art. 66).
- **Como reconhecer.** Senado: situação REMETIDA À SANÇÃO (RMSAN, classe `sancao`); `dl` mais recente. Câmara: `p.s` "Aguardando Sanção" (código 1150, classe `sancao`) ou evento de remessa à sanção em `eventos`. Veto total ou parcial: situações VETADA, VETO DELIBERADO PELO PLENÁRIO, VETO DERRUBADO (Senado) e "Vetado totalmente", "Aguardando Apreciação do Veto" (Câmara), da classe `veto`; informe/evento com "Veto" no texto (campo de texto de `informes` ou `eventos[i][4]`) (não conferido).
- **O que pode acontecer depois.** Sancionado: `lei` (a sanção expressa ou o silêncio depois dos 15 dias, CF art. 66 §3). Vetado, total ou parcialmente: `veto-congresso`; o Presidente comunica os motivos ao Presidente do Senado em 48 horas (§1º) e o veto parcial só abrange texto integral de artigo, parágrafo, inciso ou alínea (§2º). Nos casos de sanção tácita e de veto derrubado, se a lei não for promulgada em 48 horas pelo Presidente da República, o Presidente do Senado a promulga e, se este não o fizer em igual prazo, o Vice-Presidente do Senado (§7º).
- **O que ainda falta.** "Ainda não é lei. O Presidente da República decide em até 15 dias úteis se sanciona ou veta."

#### `veto-congresso` — Veto no Congresso
Sessão conjunta do Congresso aprecia o veto em até 30 dias a contar do recebimento; só pode rejeitá-lo a maioria absoluta dos Deputados e Senadores (CF art. 66 §4). Esgotado o prazo sem deliberação, o veto entra na ordem do dia da sessão imediata, sobrestadas as demais proposições, até a votação final (§6º). Regimento Comum (Res. 1/1970-CN, texto compilado até 31/7/2025): o prazo do §4º do art. 66 conta da protocolização do veto na Presidência do Senado (art. 104-A); os vetos distribuídos entram na Ordem do Dia, em sessão do Congresso na terceira terça-feira de cada mês (art. 106 e §1º), e a votação é nominal, por cédula (art. 106-B).
- **Como reconhecer.** Informe/evento com "Veto" e "sessão do Congresso" (não conferido). Sem campo coletado confiável: **não reconhecível com os dados atuais** além da menção de veto no texto.
- **O que pode acontecer depois.** Veto não mantido: o projeto é enviado ao Presidente da República para promulgação (CF art. 66 §5), `lei`. Veto mantido: nem a Constituição nem o Regimento Comum (arts. 43, 104-A, 106 a 106-D, lidos) dizem o destino; que o veto parcial mantido deixa valer o texto sancionado e que o veto total mantido arquiva o projeto é a consequência lógica, mas nenhuma regra lida o afirma (`lei` ou `arquivado`, não conferido).
- **O que ainda falta.** "O veto aguarda a sessão do Congresso, que pode derrubá-lo ou mantê-lo."

#### `lei` — Lei
- **Como reconhecer.** Senado: situação TRANSFORMADA EM NORMA JURÍDICA (ou "... COM VETO PARCIAL") e/ou campo `ng` (norma gerada) preenchido. Câmara: `p.s` "Transformado em Norma Jurídica" e `ng`.
- **O que pode acontecer depois.** Nada no processo legislativo; a lei pode ser alterada por novo projeto.
- **O que ainda falta.** "Já é lei: [ng]."

#### `arquivado` — Arquivado
Etapa de parada, mostrada em vermelho na etapa onde parou.
- **Como reconhecer.** Senado: situações ARQUIVADA, ARQUIVADA AO FINAL DA LEGISLATURA, RETIRADA PELO AUTOR, PREJUDICADA, PREJUDICADA AO FINAL DA LEGISLATURA, REJEITADA, REJEITADA A MATÉRIA (DECISÃO TERMINATIVA), ou rejeição em `dl`. Câmara: `p.s` "Arquivada" ou "Retirado pelo(a) Autor(a)" (lista oficial); "Prejudicada" e "Rejeitada" não constam da lista oficial de situações da Câmara.
- **O que pode acontecer depois.** Ao fim da legislatura, **Senado** (RISF art. 332): arquivam-se as proposições em tramitação, exceto as originárias da Câmara ou por ela revisadas, as de Senadores que permaneçam no mandato ou tenham sido reeleitos, as apresentadas por Senadores no último ano de mandato, as com parecer favorável das comissões, as de competência exclusiva do Congresso (CF art. 49), as de competência privativa do Senado (CF art. 52) e o pedido de sustação de processo contra Senador. A que estiver em tramitação há duas legislaturas é arquivada automaticamente, salvo requerimento de um terço dos Senadores em até 60 dias do início da legislatura seguinte e aprovado o desarquivamento pelo Plenário; se não concluir a tramitação nessa legislatura, é arquivada definitivamente ao fim dela (§§1 e 2). A proposição prejudicada é definitivamente arquivada (RISF art. 334 §4). **Câmara** (RICD art. 105): arquivam-se as proposições em tramitação, salvo as de iniciativa popular, os projetos de código, as relativas a tratados internacionais e a concessão, renovação e permissão de radiodifusão sonora e de sons e imagens, as relativas às contas do Presidente da República, as aprovadas pela Câmara e revisadas pelo Senado, e as do inciso VI (as destinadas à elaboração das espécies normativas do art. 59 da CF "que não tenham tramitado por 3 (três) legislaturas completas"). O texto atual do art. 105 não prevê desarquivamento (a palavra não aparece no RICD): o antigo parágrafo único, da Resolução nº 17/1989, dizia que "a proposição poderá ser desarquivada mediante requerimento do Autor, ou Autores, dentro dos primeiros cento e oitenta dias da primeira sessão legislativa ordinária da legislatura subsequente, retomando a tramitação desde o estágio em que se encontrava"; a Resolução nº 33/2022 o revogou (art. 1º, "§ 1º (Revogado)") e determinou que, finda a 56ª legislatura, arquivam-se definitivamente as proposições em tramitação por cinco legislaturas completas (art. 3º). No **Senado**, o RISF art. 332 §1º só prevê o desarquivamento aprovado pelo Plenário, a requerimento de um terço dos Senadores, da proposição com duas legislaturas; o Ato da Mesa nº 2/2014 (regulamenta o art. 332) define final de legislatura (22 de dezembro da quarta sessão legislativa, art. 2º I) e as categorias de proposição, e não diz em que etapa a proposição desarquivada volta. Em nenhuma das duas Casas, pelas fontes lidas, há regra vigente sobre a etapa em que a desarquivada volta a tramitar: por isso não há aresta de saída de `arquivado`.
- **O que ainda falta.** "Não tramita mais. [Motivo da situação]."

### Arestas de PL, PLP

| de | para | quando |
|---|---|---|
| `apresentado` | `comissoes` | o presidente da Casa despacha o projeto às comissões |
| `apresentado` | `plenario-origem` | urgência aprovada ou despacho direto "Ao Plenário": a etapa `comissoes` fica pulada |
| `comissoes` | `plenario-origem` | o parecer é aprovado e o projeto é incluído em pauta |
| `comissoes` | `casa-revisora` | decisão terminativa (Senado, RISF art. 91 I, só PL ordinário de autoria de Senador) ou conclusiva (Câmara, RICD art. 24 II, nunca PLP) aprova e ninguém recorre ao Plenário: dispensa `plenario-origem` |
| `comissoes` | `plenario-origem` | recurso contra a decisão terminativa ou conclusiva (Senado: 5 dias úteis; Câmara: 5 sessões; assinatura de um décimo dos membros) leva o projeto ao Plenário |
| `comissoes` | `arquivado` | a comissão rejeita o projeto em decisão terminativa/conclusiva, o autor o retira ou ele fica prejudicado |
| `plenario-origem` | `casa-revisora` | o Plenário aprova o texto e o remete à outra Casa |
| `plenario-origem` | `arquivado` | o Plenário rejeita o projeto |
| `casa-revisora` | `sancao-veto` | a revisora aprova sem mudar o texto |
| `casa-revisora` | `retorno-origem` | a revisora muda o texto (emenda ou substitutivo): volta à Casa de origem |
| `casa-revisora` | `arquivado` | a revisora rejeita o projeto |
| `retorno-origem` | `sancao-veto` | a Casa de origem decide sobre as mudanças e remete à sanção |
| `sancao-veto` | `lei` | o Presidente sanciona (ou deixa passar 15 dias úteis sem decidir) |
| `sancao-veto` | `veto-congresso` | o Presidente veta, total ou parcialmente |
| `veto-congresso` | `lei` | o veto não é mantido (o projeto é enviado para promulgação, CF art. 66 §5) ou é mantido só em parte |
| `veto-congresso` | `arquivado` | veto total mantido (destino não conferido nas fontes lidas) |

Outros desvios: urgência dispensa exigências, interstícios ou formalidades, mas não a publicação e distribuição, o quórum e os pareceres (Senado, RISF arts. 336-338: "salvo pareceres, quorum para deliberação e distribuição de cópias"; Câmara, RICD arts. 152-155: pareceres "das Comissões ou de Relator designado"). No Senado, o projeto do art. 91 I e II (terminativo) não pode ser apreciado em regime de urgência (RISF art. 336, parágrafo único); na Câmara, o regime de urgência afasta a apreciação conclusiva (RICD art. 24 II h). Requerimento de urgência da Câmara: um terço dos membros ou líderes que representem esse número (art. 154 II); a urgência do art. 155 (inclusão automática na Ordem do Dia) exige requerimento da maioria absoluta, aprovado pela maioria absoluta. Turno suplementar no Senado (RISF art. 282) vale quando se aprova substitutivo integral a projeto de lei, de decreto legislativo ou de resolução em turno único. Projeto de lei complementar segue o mesmo caminho, com aprovação por maioria absoluta (CF art. 69).

---

## Tipo: PEC

Proposta de emenda à Constituição. Não vai à sanção: é promulgada pelas Mesas da Câmara e do Senado (CF art. 60 §3), em sessão convocada quando a aprovação é ultimada (RISF art. 369; RICD art. 203, parágrafo único). Precisa de três quintos dos membros de cada Casa, em dois turnos em cada uma (CF art. 60 §2). Iniciativa de um terço dos deputados ou dos senadores, do Presidente da República ou de mais da metade das Assembleias Legislativas (CF art. 60 I-III). Rito próprio no Senado: RISF arts. 354-373; na Câmara: RICD arts. 201-203.

**Caminho principal:** `apresentado` → `comissoes` → `plenario-1-turno` → `plenario-2-turno` → `casa-revisora` → `promulgacao`.

### Etapas

#### `apresentado` — Apresentada
- **Como reconhecer.** Senado: situação da classe `abertura` (tabela "Nomes de situação reconhecidos") ainda sem despacho. Câmara: "Aguardando Despacho do Presidente da Câmara dos Deputados" (com ou sem "(Chancela)") ou "Aguardando Encaminhamento"; a fase de admissibilidade não tem nome próprio na lista oficial (não conferido).
- **O que pode acontecer depois.** Ir à comissão de constituição e justiça (`comissoes`); ser retirada ou arquivada.
- **O que ainda falta.** "Ainda não é emenda à Constituição. A proposta aguarda o despacho e a análise de admissibilidade."

#### `comissoes` — Comissão de Constituição e Justiça (CCJ)
Admissibilidade (não pode afrontar as cláusulas pétreas, CF art. 60 §4). Câmara: a CCJC se pronuncia sobre a admissibilidade em cinco sessões; admitida, o Presidente designa Comissão Especial para o mérito, com 40 sessões para o parecer (RICD art. 202 caput e §2). Senado: a CCJ tem até 30 dias do despacho para o parecer (RISF art. 356); decorrido o prazo sem parecer, a proposta é incluída em Ordem do Dia (RISF art. 358).
- **Como reconhecer.** Senado: despacho "Análise" com destino CCJ; situações da classe `comissao`. Câmara: `eventos[i][1]` = CCJC e, depois, comissão especial (não conferido); `p.s` da classe `comissao` ("Aguardando Designação de Relator(a)", "Aguardando Parecer", "Pronta para Pauta", "Tramitando em Conjunto").
- **O que pode acontecer depois.** Admitida e levada ao Plenário (`plenario-1-turno`); Senado: prazo da CCJ esgotado sem parecer, vai a Plenário (`plenario-1-turno`). Câmara: se inadmitida, o autor, com o apoio de líderes que representem um terço dos Deputados, pode requerer a apreciação preliminar em Plenário (RICD art. 202 §1º); o resultado dessa apreciação não foi conferido. Inadmissível sem esse requerimento, ou retirada: `arquivado`. No Senado, parecer da CCJ pela inconstitucionalidade faz a proposição ser "considerada rejeitada e arquivada definitivamente, por despacho do Presidente do Senado", salvo recurso de um décimo dos Senadores (RISF art. 101 §1º e art. 254). Na Câmara, o RICD art. 133 arquiva a proposição com pareceres contrários quanto ao mérito de todas as Comissões, mas a regra para a PEC inadmitida pela CCJC não foi encontrada (o art. 202 §1º chama de "apreciação preliminar em Plenário" o requerimento do autor; o art. 144 define esse instituto só para o recurso contra parecer terminativo, e o art. 145 §3º manda arquivar a proposição não aprovada na preliminar: se vale para a PEC, não foi conferido). A matéria "rejeitada ou havida por prejudicada" não pode ser reapresentada na mesma sessão legislativa (CF art. 60 §5 e RISF art. 373).
- **O que ainda falta.** "Ainda não é emenda à Constituição. A comissão examina se a proposta pode tramitar e dá o parecer."

#### `plenario-1-turno` — Plenário, 1º turno
- **Como reconhecer.** Senado: situação PRONTO PARA DELIBERAÇÃO DO PLENÁRIO / INCLUÍDA EM ORDEM DO DIA (classe `plenario`), e `dl` com o primeiro turno (texto contendo "1º turno"). Câmara: nenhum nome de situação da lista oficial indica o turno; vale `eventos` com órgão PLEN e despacho de "1º Turno" (não conferido).
- **O que pode acontecer depois.** Três quintos aprovam: `plenario-2-turno`; não alcançando o quórum: `arquivado` (a matéria rejeitada ou prejudicada não pode ser reapresentada na mesma sessão legislativa, CF art. 60 §5).
- **O que ainda falta.** "Ainda não é emenda à Constituição. O Plenário vota em primeiro turno; precisa de três quintos."

#### `plenario-2-turno` — Plenário, 2º turno
- **Como reconhecer.** Senado: `dl` com "2º turno" ou situação APROVADA depois do 1º turno. Câmara: despacho de "2º Turno" nos `eventos` (não conferido).
- **O que pode acontecer depois.** Aprovada: `casa-revisora` (se a Casa era a de origem) ou `promulgacao` (se era a revisora e o texto não mudou); rejeitada: `arquivado`.
- **O que ainda falta.** "Ainda não é emenda à Constituição. Falta a votação em segundo turno nesta Casa."

#### `casa-revisora` — Outra Casa (2 turnos)
- **Como reconhecer.** Senado como origem: REMETIDA À CÂMARA DOS DEPUTADOS (RMCD; na ficha da PEC a situação aparece abreviada assim) e `cn/cd/cdx`. Câmara como origem: "Aguardando Apreciação pelo Senado Federal" (código 926) e `sf` na ficha.
- **O que pode acontecer depois.** Aprovada sem mudança em dois turnos: `promulgacao`; aprovada com mudança: volta à Casa de origem (`retorno-origem`); rejeitada: `arquivado`.
- **O que ainda falta.** "Ainda não é emenda à Constituição. A outra Casa também vota em dois turnos; se mudar o texto, o regimento da Casa de origem define o que acontece. Depois é promulgada, sem sanção."

#### `retorno-origem` — Volta à Casa de origem
A CF art. 60 não regula o retorno da PEC alterada. **Câmara como Casa de origem:** "as emendas do Senado à proposta de emenda à Constituição oriunda da Câmara" têm a mesma tramitação da PEC (comissão especial e dois turnos, RICD art. 203) e, "ultimada na Câmara a aprovação", o fato é comunicado ao Presidente do Senado e convocada sessão para a promulgação (RICD art. 203, parágrafo único). **Senado como Casa de origem:** "considera-se proposta nova o substitutivo da Câmara a proposta de iniciativa do Senado" (RISF art. 367) e, na revisão do Senado a proposta da Câmara, aplicam-se as normas do mesmo título (art. 368); o que acontece com a proposta nova depois não está nos artigos lidos.
- **Como reconhecer.** Não reconhecível com os dados atuais; deduzido quando há remessa de volta após `casa-revisora`.
- **O que pode acontecer depois.** Câmara de origem: `promulgacao` (RICD art. 203) ou `arquivado`. Senado de origem: tramitação da proposta nova, não conferida.
- **O que ainda falta.** "Ainda não é emenda à Constituição. O texto mudou na outra Casa; o regimento da Casa de origem define o que acontece com a mudança."

#### `promulgacao` — Promulgação
Pelas Mesas da Câmara e do Senado, em sessão solene do Congresso, com número de ordem (CF art. 60 §3).
- **Como reconhecer.** `ng` preenchido (Emenda Constitucional nº N) e/ou situação TRANSFORMADA EM NORMA JURÍDICA (Senado) ou "Transformado em Norma Jurídica" (Câmara).
- **O que pode acontecer depois.** Nada; entra em vigor com a publicação.
- **O que ainda falta.** "Já é emenda à Constituição: [ng]."

#### `arquivado` — Arquivada
- **Como reconhecer.** Senado: PREJUDICADA, PREJUDICADA AO FINAL DA LEGISLATURA, ARQUIVADA, ARQUIVADA AO FINAL DA LEGISLATURA, REJEITADA, RETIRADA PELO AUTOR. Câmara: "Arquivada", "Retirado pelo(a) Autor(a)".
- **O que pode acontecer depois.** Regras de arquivamento ao fim da legislatura e de desarquivamento: as mesmas do tipo PL (RISF art. 332; RICD art. 105). Sem aresta de saída, porque a etapa de volta não foi conferida.
- **O que ainda falta.** "Não tramita mais. [Motivo]."

### Arestas de PEC

| de | para | quando |
|---|---|---|
| `apresentado` | `comissoes` | a proposta é despachada à comissão de constituição e justiça |
| `comissoes` | `plenario-1-turno` | a proposta é admitida e o parecer é aprovado, ou (Senado) o prazo da CCJ acaba sem parecer (RISF art. 358) |
| `comissoes` | `arquivado` | a comissão a declara inadmissível (Senado: RISF art. 101 §1º, salvo recurso; Câmara: sem requerimento de apreciação preliminar em Plenário, regra de arquivamento não conferida) ou o autor a retira |
| `plenario-1-turno` | `plenario-2-turno` | três quintos aprovam em 1º turno (interstício de cinco dias úteis no Senado, RISF art. 362; de cinco sessões na Câmara, RICD art. 202 §6º) |
| `plenario-1-turno` | `arquivado` | não alcança três quintos |
| `plenario-2-turno` | `casa-revisora` | aprovada em 2º turno na Casa de origem |
| `plenario-2-turno` | `promulgacao` | aprovada em 2º turno na revisora sem mudança do texto |
| `casa-revisora` | `promulgacao` | a outra Casa aprova nos dois turnos sem mudar o texto |
| `casa-revisora` | `retorno-origem` | a outra Casa muda o texto |
| `casa-revisora` | `arquivado` | rejeitada na outra Casa |
| `retorno-origem` | `promulgacao` | só com a Câmara como Casa de origem: aprova as emendas do Senado pelo rito do art. 202 e a sessão de promulgação é convocada (RICD art. 203 e parágrafo único) |

Outros desvios: o turno suplementar do RISF art. 282 não se aplica à PEC (vale para projeto de lei, de decreto legislativo e de resolução). No Senado, a PEC tem discussão em primeiro turno por cinco sessões deliberativas ordinárias consecutivas (RISF art. 358), no segundo turno três sessões para emendas que não envolvam o mérito (art. 363) e, aprovada sem emendas, é remetida à Câmara; emendada, vai à CCJ para a redação final em três dias (art. 365). Na Câmara, a Comissão Especial tem 40 sessões, só ela recebe emendas (nas dez primeiras sessões), e a proposta entra na Ordem do Dia duas sessões depois do parecer (RICD art. 202 §§2, 3 e 5), votação nominal em ambos os turnos (§7º). Não há sanção nem veto. A Constituição não pode ser emendada durante intervenção federal, estado de defesa ou estado de sítio (CF art. 60 §1). Urgência e calendário especial para PEC: nos arts. 354 a 373 do RISF não há menção a nenhum dos dois (prazos fixos); o RICD art. 196 inclui "as propostas de emenda à Constituição" entre os projetos "em regime de urgência" só para o prazo da redação final (uma sessão), e o art. 202 §8º aplica à PEC as regras dos projetos de lei "no que não colidir"; se a urgência do art. 152 e seguintes vale para a PEC não foi conferido, e "calendário especial" não aparece no RICD nem no RISF lidos.

---

## Tipo: MPV

Medida provisória: ato do Presidente da República com força de lei, que vale desde a publicação e precisa ser convertida em lei pelo Congresso (CF art. 62). Prazo de 60 dias, prorrogável por mais 60 (art. 62 §3); a contagem para durante o recesso (art. 62 §4); se não for apreciada em 45 dias contados da publicação, entra em regime de urgência em cada Casa e sobrestam-se as demais deliberações legislativas da Casa onde estiver (art. 62 §6). A votação começa na Câmara (art. 62 §8). A deliberação de cada Casa sobre o mérito depende de juízo prévio sobre o atendimento dos pressupostos constitucionais (art. 62 §5). Se o projeto de lei de conversão altera o texto original, a MPV segue em vigor até a sanção ou o veto do projeto (art. 62 §12). O rito do Congresso está na Resolução nº 1/2002-CN, "parte integrante do Regimento Comum" (art. 1º), lida no texto do Senado (com as notas da ADI 4029) e na publicação original da Câmara.

**Caminho principal:** `publicada` → `comissao-mista` → `plenario-camara` → `plenario-senado` → `sancao-veto` → `lei`.

### Etapas

#### `publicada` — Publicada (já vale)
- **Como reconhecer.** Senado: primeira situação; ficha com data de edição. Câmara: `eventos` iniciais com a apresentação da MPV e a leitura do ofício presidencial (não conferido).
- **O que pode acontecer depois.** Instalação da comissão mista (`comissao-mista`); perda de validade (`perdeu-validade`).
- **O que ainda falta.** "Já vale como lei, mas só por tempo limitado. O Congresso precisa convertê-la em lei em até 120 dias."

#### `comissao-mista` — Comissão mista
Deputados e senadores dão o parecer antes dos Plenários (CF art. 62 §9). Resolução nº 1/2002-CN: a Presidência da Mesa do Congresso designa a comissão em 48 horas da publicação (art. 2º), com 12 senadores e 12 deputados (§2º); emendas só na comissão, nos seis primeiros dias (art. 4º); parecer único sobre os aspectos constitucional, de mérito e de adequação financeira e orçamentária; a comissão pode concluir por projeto de lei de conversão e por projeto de decreto legislativo sobre as relações do período (art. 5º §4º), e o parecer aprovado vai à Câmara (§5º).
- **Como reconhecer.** Senado: `despachos` com destino "Comissão Mista"; situação da classe `comissao` ou AGUARDANDO DESIGNAÇÃO DO RELATOR (classe `abertura`). Câmara: `eventos[i][1]` com "CMMPV" ou semelhante (não conferido).
- **O que pode acontecer depois.** Parecer aprovado e ida à Câmara (`plenario-camara`); perda de prazo (`perdeu-validade`). A CF diz que a comissão mista examina a MPV e emite parecer "antes de serem apreciadas, em sessão separada, pelo plenário de cada uma das Casas" (art. 62 §9). A Resolução previa o prazo de 14 dias para o parecer (art. 5º, caput) e, esgotado ele, o envio do processo à Câmara, com parecer dado no Plenário pelo relator (art. 6º §§1º e 2º); o STF, na ADI 4029 (8/3/2012), declarou a inconstitucionalidade incidental desses dispositivos (art. 5º caput e art. 6º §§1º e 2º): as MPVs novas "deverão ser obrigatoriamente apreciadas por uma comissão integrada por deputados e senadores, não podendo mais ser apreciadas pelo Parlamento apenas com parecer do relator", sem alcançar as já convertidas nem as em tramitação na época (notícia do STF de 8/3/2012). Ou seja, a MPV não segue ao Plenário sem o parecer da comissão mista. O que acontece se a comissão não o emitir, o texto lido não diz; o ritmo de 14 dias aparece no texto atual do Senado só como dispositivo declarado inconstitucional. A Resolução nº 1/2002 art. 3º dá 24 horas para a instalação.
- **O que ainda falta.** "Já vale como lei. A comissão mista analisa antes de a Câmara votar."

#### `plenario-camara` — Câmara dos Deputados
- **Como reconhecer.** Câmara: `eventos` com órgão PLEN após a comissão; `p.s` "Pronta para Pauta" (classe `comissao` na lista; o órgão PLEN vem dos `eventos`). Senado: situação REMETIDA À CÂMARA DOS DEPUTADOS... (para a MPV é o inverso: o Senado só recebe depois). Campo `dl` de origem Câmara na ficha.
- **O que pode acontecer depois.** Aprovada: `plenario-senado`; rejeitada: `arquivado`; prazo vence: `perdeu-validade`. A Câmara tem até o 28º dia de vigência (Res. 1/2002-CN, art. 6º) e, antes do mérito, o Plenário decide em apreciação preliminar se há os pressupostos de relevância e urgência e a adequação financeira e orçamentária; se não houver, a MPV é arquivada (art. 8º e parágrafo único).
- **O que ainda falta.** "Já vale como lei. A Câmara vota primeiro; depois o Senado."

#### `plenario-senado` — Senado Federal
- **Como reconhecer.** Senado: situação PRONTO PARA DELIBERAÇÃO DO PLENÁRIO, INCLUÍDA EM ORDEM DO DIA (classe `plenario`); `dl.p` = Plenário do Senado.
- **O que pode acontecer depois.** O Senado tem até o 42º dia de vigência (Res. 1/2002-CN, art. 7º). Aprovada sem alteração de mérito: o texto da MPV "será promulgado pelo Presidente da Mesa do Congresso Nacional para publicação, como lei" (art. 12) e vai a `lei`; aprovado projeto de lei de conversão, a Casa onde a votação terminou o envia à sanção (art. 13; CF art. 62 §12): `sancao-veto`; se o Senado modifica o texto aprovado pela Câmara, ele volta à Câmara, como emenda, em turno único e sem novas alterações, com 3 dias para a Câmara apreciar (art. 7º §§3º e 4º): `plenario-camara`; rejeitada em qualquer Casa: `arquivado`, com ato declaratório do Presidente da Casa (art. 14); prazo vence: `perdeu-validade`.
- **O que ainda falta.** "Já vale como lei. O Senado vota; se mudar o texto, ele volta à Câmara; se aprovar o projeto de lei de conversão, ele vai à sanção."

#### `sancao-veto` — Sanção ou veto
Só quando o Congresso aprovou projeto de lei de conversão com alterações (CF art. 62 §12). Prazo e regras iguais às de PL (CF art. 66).
- **Como reconhecer.** Situação REMETIDA À SANÇÃO (Senado) ou "Aguardando Sanção" (Câmara), classe `sancao`.
- **O que pode acontecer depois.** `lei` ou `veto-congresso`.
- **O que ainda falta.** "Já vale como lei. Falta a sanção ou o veto do Presidente ao texto convertido."

#### `veto-congresso` — Veto no Congresso
Igual ao de PL (CF art. 66 §4). Não reconhecível com os dados atuais além da menção ao veto no texto.
- **O que pode acontecer depois.** `lei` (veto derrubado ou mantido em parte) ou `arquivado` (veto total mantido).

#### `lei` — Lei de conversão
- **Como reconhecer.** `ng` preenchido ("Lei nº ..."); situação TRANSFORMADA EM NORMA JURÍDICA (Senado) ou "Transformado em Norma Jurídica" (Câmara).
- **O que ainda falta.** "Convertida em lei: [ng]."

#### `perdeu-validade` — Perdeu a validade (caducidade)
A MPV não foi votada em 120 dias e deixa de valer; o Congresso deve regular por decreto legislativo as relações jurídicas do período (CF art. 62 §3 e §11). Esgotado o prazo, o Presidente da Mesa do Congresso comunica o fato ao Presidente da República e publica ato declaratório de encerramento (Res. 1/2002-CN, art. 14, parágrafo único); a comissão mista elabora o projeto de decreto legislativo em 15 dias (art. 11 e §1º); sem decreto em 60 dias, as relações do período seguem regidas pela MPV (§2º).
- **Como reconhecer.** Senado: decisão PERDA_EFICACIA (lista oficial de tipos de decisão) ou situação SEM EFICÁCIA (SEFICA, lista oficial; o texto oficial lido não liga esta situação à perda de validade da MPV, não conferido). Câmara: situação "Perdeu a Eficácia" (lista oficial de códigos; idem). Nenhuma MPV no recorte local.
- **O que pode acontecer depois.** Nada; o Presidente não pode reeditar a MPV na mesma sessão legislativa (CF art. 62 §10).
- **O que ainda falta.** "Perdeu a validade: não foi votada a tempo."

#### `arquivado` — Arquivada (rejeitada)
- **Como reconhecer.** Rejeição registrada em `dl` ou `p.s` "Arquivada" após rejeição em Plenário.
- **O que pode acontecer depois.** Nada; vale o mesmo bloqueio de reedição na sessão legislativa (CF art. 62 §10).
- **O que ainda falta.** "Rejeitada: deixou de valer."

### Arestas de MPV

| de | para | quando |
|---|---|---|
| `publicada` | `comissao-mista` | o Congresso instala a comissão mista |
| `publicada` | `perdeu-validade` | os 120 dias acabam sem votação |
| `comissao-mista` | `plenario-camara` | o parecer da comissão mista é aprovado (a votação começa na Câmara, CF art. 62 §8; sem o parecer a MPV não vai ao Plenário, STF, ADI 4029) |
| `comissao-mista` | `perdeu-validade` | os 120 dias acabam |
| `plenario-camara` | `plenario-senado` | a Câmara aprova |
| `plenario-camara` | `arquivado` | a Câmara rejeita |
| `plenario-camara` | `perdeu-validade` | os 120 dias acabam |
| `plenario-senado` | `lei` | o Senado aprova sem alteração de mérito: o texto é promulgado pelo Presidente da Mesa do Congresso (Res. 1/2002-CN, art. 12) |
| `plenario-senado` | `sancao-veto` | é aprovado projeto de lei de conversão: vai à sanção (art. 13; CF art. 62 §12) |
| `plenario-senado` | `plenario-camara` | o Senado modifica o texto aprovado pela Câmara: volta como emenda, turno único, 3 dias (art. 7º §§3º e 4º) |
| `plenario-senado` | `arquivado` | o Senado rejeita |
| `plenario-senado` | `perdeu-validade` | os 120 dias acabam |
| `sancao-veto` | `lei` | o Presidente sanciona |
| `sancao-veto` | `veto-congresso` | o Presidente veta |
| `veto-congresso` | `lei` | o veto não é mantido (CF art. 66 §5) |
| `veto-congresso` | `arquivado` | veto total mantido (destino não conferido nas fontes lidas) |

---

## Tipo: PDL

Projeto de decreto legislativo: matérias de competência exclusiva do Congresso (CF art. 49), como aprovar tratados e sustar atos do Executivo. A sanção "não [é] exigida" para o que está nos arts. 49, 51 e 52 (CF art. 48, caput), então não há sanção nem veto. Quem promulga: o Presidente do Senado "promulgar as resoluções do Senado e os decretos legislativos" (RISF art. 48 XXVIII) e, na matéria de competência exclusiva do Congresso votada em sessão conjunta, o texto "será promulgado pelo Presidente do Senado" (Regimento Comum, art. 52, parágrafo único). O RICD (art. 17 m e art. 200 §2º) só trata da promulgação das resoluções da Câmara pelo seu Presidente; para o decreto legislativo o RICD diz apenas que se destina a matérias de exclusiva competência do Poder Legislativo, sem sanção (art. 109 II), e que a proposição aprovada é encaminhada "à sanção, à promulgação ou ao Senado" (art. 200). Revisão pelas duas Casas: o RICD trata o projeto de decreto legislativo como um dos projetos (art. 108), mantém sua numeração "com indicação da Casa de origem" e anexa ao projeto primitivo as emendas do Senado a projeto da Câmara (art. 138 I d e IV); o RISF dá às emendas da Câmara a projeto do Senado o tratamento dos arts. 285 a 287 e envia o projeto aprovado "à sanção, à promulgação ou à Câmara" (art. 328). No Senado, o PDL do art. 223 §1º da CF (radiodifusão) tem decisão terminativa da comissão (RISF art. 91 III); sem recurso, o projeto é "encaminhado à sanção, promulgado, remetido à Câmara ou arquivado, conforme o caso" (art. 91 §5). Na Câmara, a apreciação conclusiva do RICD art. 24 II só alcança "projetos de lei": não há via conclusiva para PDL.

**Caminho principal:** `apresentado` → `comissoes` → `plenario-origem` → `casa-revisora` → `promulgacao`.

### Etapas

#### `apresentado` — Apresentado
- **Como reconhecer.** Senado: situação da classe `abertura` (tabela "Nomes de situação reconhecidos"), sem despacho. Câmara: "Aguardando Despacho do Presidente da Câmara dos Deputados" ou "Aguardando Encaminhamento".
- **O que pode acontecer depois.** `comissoes`, `plenario-origem` (urgência), `arquivado`.
- **O que ainda falta.** "Ainda não é decreto legislativo. Aguarda despacho às comissões."

#### `comissoes` — Comissões
- **Como reconhecer.** Igual a PL: despacho "Análise" e situações da classe `comissao` (Câmara: "Aguardando Designação de Relator(a)", "Aguardando Parecer", "Pronta para Pauta", "Tramitando em Conjunto").
- **O que pode acontecer depois.** `plenario-origem`; urgência que pula esta etapa; `arquivado`.
- **O que ainda falta.** "Ainda não é decreto legislativo. As comissões dão o parecer; depois segue ao Plenário."

#### `plenario-origem` — Plenário da Casa de origem
- **Como reconhecer.** Igual a PL: situações da classe `plenario` (PRONTO PARA DELIBERAÇÃO DO PLENÁRIO, INCLUÍDA EM ORDEM DO DIA, APROVADA); `dl.p` = Plenário.
- **O que pode acontecer depois.** `casa-revisora` ou `arquivado`.
- **O que ainda falta.** "Ainda não é decreto legislativo. Se o Plenário aprovar, o texto vai à outra Casa."

#### `casa-revisora` — Outra Casa
- **Como reconhecer.** REMETIDA À CÂMARA DOS DEPUTADOS (Senado) ou "Aguardando Apreciação pelo Senado Federal" (Câmara) e `cn/cd/cdx`; ou `sf` na ficha da Câmara.
- **O que pode acontecer depois.** Aprovado: `promulgacao`; mudado: volta à Casa de origem (`retorno-origem`); rejeitado: `arquivado`.
- **O que ainda falta.** "Ainda não é decreto legislativo. A outra Casa pode aprovar, mudar ou rejeitar; depois é promulgado, sem sanção."

#### `retorno-origem` — Volta à Casa de origem
- **Como reconhecer.** Não reconhecível com os dados atuais. A CF art. 65 (revisão e retorno) trata de "projeto de lei"; para o decreto legislativo valem os regimentos: o RICD anexa as emendas do Senado ao projeto da Câmara (art. 138 IV) e as distribui às Comissões (art. 123); o RISF vota em globo as emendas da Câmara a projeto do Senado (arts. 285 a 287). Os artigos dizem "projeto"; o RICD art. 108 inclui entre os projetos o de decreto legislativo.
- **O que pode acontecer depois.** `promulgacao` ou `arquivado`.
- **O que ainda falta.** "O texto mudou na outra Casa e volta para a Casa de origem decidir sobre as mudanças."

#### `promulgacao` — Promulgação
- **Como reconhecer.** `ng` ("Decreto Legislativo nº ...") e/ou TRANSFORMADA EM NORMA JURÍDICA (Senado) / "Transformado em Norma Jurídica" (Câmara).
- **O que ainda falta.** "Já é decreto legislativo: [ng]."

#### `arquivado` — Arquivado
- **Como reconhecer.** Senado: PREJUDICADA, PREJUDICADA AO FINAL DA LEGISLATURA, ARQUIVADA, ARQUIVADA AO FINAL DA LEGISLATURA, RETIRADA PELO AUTOR, REJEITADA; Câmara: "Arquivada", "Retirado pelo(a) Autor(a)".
- **O que pode acontecer depois.** Ao fim da legislatura, no Senado, as proposições "que tratem de matéria de competência exclusiva do Congresso Nacional (Const., art. 49)" estão entre as exceções ao arquivamento (RISF art. 332 V): PDL em tramitação não é arquivado só pelo fim da legislatura, salvo a regra das duas legislaturas (§1º). O Ato da Mesa nº 2/2014 do Senado (art. 3º §4º) acrescenta que os projetos de decreto legislativo de matéria de iniciativa não parlamentar (concessão de radiodifusão, atos internacionais e outras) continuam tramitando, "mesmo aqueles que tramitem há 2 (duas) legislaturas". Na Câmara vale o RICD art. 105 (ver PL); o inciso VIII exclui do arquivamento as proposições relativas a tratados internacionais e a radiodifusão. Sem aresta de saída: a etapa de volta não está definida nas fontes lidas.
- **O que ainda falta.** "Não tramita mais. [Motivo]."

### Arestas de PDL

| de | para | quando |
|---|---|---|
| `apresentado` | `comissoes` | despacho às comissões |
| `apresentado` | `plenario-origem` | urgência ou despacho ao Plenário: `comissoes` fica pulada |
| `comissoes` | `plenario-origem` | parecer aprovado |
| `comissoes` | `casa-revisora` | Senado: PDL do art. 223 §1º da CF (RISF art. 91 III), decisão terminativa da comissão sem recurso, remetido à Câmara (art. 91 §5); só o Senado, como Casa de origem |
| `comissoes` | `promulgacao` | Senado como Casa revisora: PDL do art. 223 §1º da CF, decisão terminativa sem recurso, "promulgado" (RISF art. 91 §5) |
| `comissoes` | `arquivado` | rejeitado, retirado ou prejudicado |
| `plenario-origem` | `casa-revisora` | Plenário aprova |
| `plenario-origem` | `arquivado` | Plenário rejeita |
| `casa-revisora` | `promulgacao` | aprovado sem mudar o texto |
| `casa-revisora` | `retorno-origem` | texto mudado |
| `casa-revisora` | `arquivado` | rejeitado |
| `retorno-origem` | `promulgacao` | a Casa de origem decide sobre as mudanças; o decreto legislativo é promulgado pelo Presidente do Senado (RISF art. 48 XXVIII; promulgação na Câmara não conferida) |

---

## Tipo: PRS, PRC

Projeto de resolução do Senado (PRS, CF art. 52) e da Câmara (PRC, CF art. 51): atos de organização e de competência privativa de uma só Casa. Não passam pela outra Casa nem pelo Presidente da República. Requerimentos (de informação, de urgência etc.) seguem curto caminho próprio na mesma Casa e podem ser tratados junto desta seção: apresentação, decisão da Mesa ou do Plenário, fim.

**Caminho principal:** `apresentado` → `comissoes` → `plenario` → `promulgacao`.

### Etapas

#### `apresentado` — Apresentado
- **Como reconhecer.** Senado: situação da classe `abertura` (tabela "Nomes de situação reconhecidos"), sem despacho. Câmara: "Aguardando Designação de Relator(a)" (classe `comissao` na lista oficial; no início do rito vale o evento) e "Aguardando Encaminhamento".
- **O que pode acontecer depois.** `comissoes`, `plenario` (urgência), `arquivado`.
- **O que ainda falta.** "Ainda não é resolução. Aguarda o despacho às comissões ou ao Plenário."

#### `comissoes` — Comissões
- **Como reconhecer.** Senado: despacho "Análise"; situações da classe `comissao`. Câmara: "Aguardando Parecer", "Pronta para Pauta", "Tramitando em Conjunto".
- **O que pode acontecer depois.** `plenario` ou, com urgência/despacho direto, a etapa fica pulada; `arquivado`.
- **O que ainda falta.** "Ainda não é resolução. As comissões dão o parecer; depois vota o Plenário."

#### `plenario` — Plenário
- **Como reconhecer.** Senado: situações da classe `plenario`; `dl.p` = Plenário. Câmara: PLEN em `eventos`.
- **O que pode acontecer depois.** Aprovado: `promulgacao`; rejeitado: `arquivado`.
- **O que ainda falta.** "Ainda não é resolução. O Plenário desta Casa decide; aprovado, é promulgado sem passar pela outra Casa."

#### `promulgacao` — Promulgação
- **Como reconhecer.** Senado: TRANSFORMADA EM NORMA JURÍDICA (a situação mais frequente em PRS no índice) e/ou `ng` ("Resolução nº ..."). Câmara: "Transformado em Norma Jurídica" / `ng`.
- **O que ainda falta.** "Já é resolução: [ng]."

#### `arquivado` — Arquivado
- **Como reconhecer.** Senado: PREJUDICADA, PREJUDICADA AO FINAL DA LEGISLATURA, ARQUIVADA, ARQUIVADA AO FINAL DA LEGISLATURA, RETIRADA PELO AUTOR; Câmara: "Arquivada", "Retirado pelo(a) Autor(a)".
- **O que ainda falta.** "Não tramita mais. [Motivo]."

### Arestas de PRS, PRC

| de | para | quando |
|---|---|---|
| `apresentado` | `comissoes` | despacho às comissões |
| `apresentado` | `plenario` | urgência ou despacho ao Plenário: `comissoes` fica pulada |
| `comissoes` | `plenario` | parecer aprovado |
| `comissoes` | `promulgacao` | só PRS do art. 52 X da CF no Senado: decisão terminativa da comissão sem recurso, "promulgado" (RISF art. 91 II e §5) |
| `comissoes` | `arquivado` | rejeitado, retirado ou prejudicado |
| `plenario` | `promulgacao` | o Plenário aprova: a resolução é promulgada pela Casa, sem sanção |
| `plenario` | `arquivado` | o Plenário rejeita |

Senado, PRS: o projeto de resolução que suspende, no todo ou em parte, lei declarada inconstitucional por decisão definitiva do STF (CF art. 52 X) tem decisão terminativa da comissão (RISF art. 91 II); sem recurso, o projeto é "encaminhado à sanção, promulgado, remetido à Câmara ou arquivado, conforme o caso" (art. 91 §5), de modo que `comissoes` leva direto a `promulgacao`. No arquivamento ao fim da legislatura, as proposições de competência privativa do Senado (CF art. 52) estão entre as exceções (RISF art. 332 VI). Sem aresta de saída de `arquivado`: a etapa de volta não foi conferida.

---

## Nomes de situação reconhecidos

Cada nome abaixo foi conferido na lista oficial de códigos (Senado: `processo/tipos-situacao`; Câmara: `referencias/proposicoes/codSituacao`; cópias e capturas em `tests/fixtures/contratos/`) e a classe vem de `situacoes_etapas.json`. O reconhecimento compara o nome inteiro, sem caixa nem acento: nome fora desta tabela não aponta etapa. Duas classes vêm de leitura do regimento, não da lista: na Câmara, as situações de criação, constituição, instalação e eleição de presidente e relator da Comissão Especial, mais a de relator que deixou de ser membro, são da classe `comissao` porque o RICD arts. 33 e 34 criam a Comissão Especial para dar parecer e o art. 41 VI atribui ao Presidente de Comissão a designação de relatores; no Senado, "ARQUIVADO NA CÂMARA DOS DEPUTADOS" é da classe `parada` pelo texto do próprio nome (o RICD arts. 105 e 164 §4º tratam de arquivamento como fim da tramitação). A classe é leitura nossa da etapa a que o nome corresponde; o que a lista oficial não diz sobre o nome (por exemplo, a etapa de uma situação como "Aguardando Deliberação") fica sem classe, e a faixa de etapas não aparece.

| Classe | Etapa | Senado (sigla: nome) | Câmara (código: nome) |
|---|---|---|---|
| `abertura` | `apresentado` | AGDREL: AGUARDANDO DESIGNAÇÃO DO RELATOR; AGDESP: AGUARDANDO DESPACHO; AGUARD: AGUARDANDO DESPACHO; AGREMD: AGUARDANDO RECEBIMENTO DE EMENDAS | 905: Aguardando Despacho do Presidente da Câmara dos Deputados; 910: Aguardando Encaminhamento; 1201: Aguardando Despacho do Presidente da Câmara dos Deputados (Chancela); 1382: Aguardando Despacho do Presidente da Câmara dos Deputados |
| `comissao` | `comissoes` | AGAUDPUB: AGUARDANDO AUDIÊNCIA PÚBLICA; AGINR: AGUARDANDO INTERPOSIÇÃO DE RECURSO; APRCD(DT): APRECIADA EM DECISÃO TERMINATIVA PELAS COMISSÕES; APRVPAR: APROVADO PARECER NA COMISSÃO; INPAUTA: INCLUÍDA NA PAUTA DA REUNIÃO; RELATOR: MATÉRIA COM A RELATORIA; MATDESP: MATÉRIA DESPACHADA; PEDVISTA: PEDIDO DE VISTA CONCEDIDO; PRONTPAUT: PRONTA PARA A PAUTA NA COMISSÃO | 901: Aguardando Constituição de Comissão Temporária; 902: Aguardando Criação de Comissão Temporária; 907: Aguardando Designação de Relator(a); 911: Aguardando Instalação de Comissão Temporária; 915: Aguardando Parecer; 924: Pronta para Pauta; 925: Tramitando em Conjunto; 1170: Aguardando Designação - Aguardando Devolução de Relator(a) que deixou de ser Membro; 1296: Aguardando Eleição do(a) Presidente da Comissão Especial e do(a) Relator(a); 1297: Aguardando Parecer da Comissão Especial |
| `plenario` | `plenario-origem` | APRVD: APROVADA; INCLOD: INCLUÍDA EM ORDEM DO DIA; PRONDEPLEN: PRONTO PARA DELIBERAÇÃO DO PLENÁRIO | — |
| `outra-casa` | `casa-revisora` | RMCD: REMETIDA À CÂMARA DOS DEPUTADOS | 926: Aguardando Apreciação pelo Senado Federal |
| `sancao` | `sancao-veto` | RMSAN: REMETIDA À SANÇÃO | 1150: Aguardando Sanção |
| `veto` | `veto-congresso` | VTDA: VETADA; VETDELIB: VETO DELIBERADO PELO PLENÁRIO; VETODERR: VETO DERRUBADO | 937: Vetado totalmente; 939: Aguardando Apreciação do Veto |
| `norma` | `lei` / `promulgacao` | TNJR: TRANSFORMADA EM NORMA JURÍDICA; TNJRVETO: TRANSFORMADA EM NORMA JURÍDICA COM VETO PARCIAL | 1140: Transformado em Norma Jurídica |
| `parada` | `arquivado` | ARQV: ARQUIVADA; ARQVD: ARQUIVADA AO FINAL DA LEGISLATURA; ARQV_CD: ARQUIVADO NA CÂMARA DOS DEPUTADOS; PRJDA: PREJUDICADA; PREJFINLEG: PREJUDICADA AO FINAL DA LEGISLATURA; RJTDA: REJEITADA; RJTDA(DT): REJEITADA A MATÉRIA (DECISÃO TERMINATIVA); RTPA: RETIRADA PELO AUTOR | 923: Arquivada; 950: Retirado pelo(a) Autor(a) |

Fora da tabela (lista oficial, sem classe declarada): as demais 144 situações do Senado e 78 da Câmara, entre elas VETOMANT (VETO MANTIDO), SEFICA (SEM EFICÁCIA), APRVD(ESF) e a "Perdeu a Eficácia" da Câmara. Decisões do Senado com classe (10 de 33): `APROVADA_EM_COMISSAO_TERMINATIVA` (comissão), `APROVADA_NO_PLENARIO` (plenário), `PERDA_EFICACIA` (`perdeu-validade`, só MPV) e, como parada, `ARQUIVADO_FIM_LEGISLATURA`, `PREJUDICADO`, `REJEITADO_COMISSAO_NAO_TERM`, `REJEITADO_COMISSAO_TERM`, `REJEITADO_INCONSTICIONALIDADE_CCJ`, `REJEITADO_PLENARIO` e `RETIRADO_PELO_AUTOR`; as outras 23 ficam sem classe.

---

## Modelos da frase do estado

A frase do estado junta duas partes: o fato mais recente (modelo abaixo, com lacunas entre colchetes) e "o que ainda falta" da etapa atual (acima). Sempre se mostra também a situação crua da fonte, com data e fonte. Lacuna sem campo preenchido: o trecho inteiro some; nada se inventa.

| Quando | Modelo | Lacunas (campo) |
|---|---|---|
| Aprovado e enviado à outra Casa | "Aprovado pelo [dl.t] em [dl.d] e enviado à [dl.p] em [data da situação RMCD], onde tem o número [cn]" | `dl.t` texto da deliberação, `dl.d` data, `dl.p` Plenário/órgão, data de `situacoes[i][0]` da situação REMETIDA À CÂMARA DOS DEPUTADOS, `cn` número na Câmara (`cn/cd/cdx`) |
| Em comissão | "Em análise na [destino do despacho]; situação: [situacoes[i][3]] desde [situacoes[i][0]]" | `despachos[i][2]`, `situacoes` |
| Decisão terminativa | "Apreciado em decisão terminativa pela [comissão] em [data]; prazo de recurso para o Plenário" | `situacoes` APRECIADA EM DECISÃO TERMINATIVA PELAS COMISSÕES, `despachos[i][3]` |
| Remetido à sanção | "Aprovado pelo Congresso e remetido à sanção em [data]" | `situacoes` REMETIDA À SANÇÃO |
| Virou lei/norma | "Transformado em [ng] em [data]" | `ng`, situação TRANSFORMADA EM NORMA JURÍDICA |
| Parado | "[Arquivado/Retirado/Prejudicado] em [data]: [situação crua]" | `situacoes[i][3]`, `p.s` |
| Tramita na Câmara a partir do Senado | "Veio do Senado ([sf]) e está em [p.s] na Câmara" | `sf`, `p.s` |

## Fontes

Regra da base: vale o texto oficial; o que não foi lido na fonte fica marcado "não conferido" e não vira aresta nem frase do site.

**Conferência de 20/11/2026**, com os textos baixados e lidos inteiros nos trechos citados:
- Constituição Federal, texto atualizado até a EC 141, do site da Câmara: https://www2.camara.leg.br/atividade-legislativa/legislacao/constituicao1988 (o planalto.gov.br recusou a conexão TLS do `curl`). Os links do site para a CF seguem `linkCF(art)` (ficha.js), `https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm#art<N>`.
- Regimento Interno da Câmara dos Deputados, texto atualizado até a Resolução nº 34/2026 (arquivo `RICDatualizadoatRCD342026.pdf`): https://www2.camara.leg.br/atividade-legislativa/legislacao/regimento-interno-da-camara-dos-deputados
- Regimento Interno do Senado Federal, volume 1 (arts. 1 a 413), arquivo "RISF 2018 Volume 1.pdf" que a página do Senado oferece como "texto compilado até 22/8/2025" (capa com a Mesa do biênio 2025-2026; a nota diz "versão consolidada pelo Ato da Comissão Diretora nº 15, de 2022, atualizada até julho de 2025"): https://www25.senado.leg.br/web/atividade/legislacao/regimento-interno. O texto lido já incorpora as resoluções posteriores a 2018; o arquivo baixado na conferência anterior é idêntico ao desta (artigos 48, 91, 282, 332, 334, 336-338, 354-369 e 373 comparados). O volume 2 (normas conexas) não foi lido.
- Regimento Comum do Congresso Nacional (Res. 1/1970-CN, "com normas conexas", texto consolidado até janeiro de 2023 e atualizado até julho de 2025): https://www.congressonacional.leg.br/legislacao-e-publicacoes/regimento-do-congresso-nacional (PDF do portal do Senado). Lidos: arts. 43, 46, 51, 52, 85, 104-A, 106 a 106-D e a Resolução nº 1/2002-CN (texto do Senado com notas da ADI 4029: https://www25.senado.leg.br/documents/137784508/140356431/resolucao01_2002cn.pdf; publicação original, para o texto dos dispositivos declarados inconstitucionais: https://www2.camara.leg.br/legin/fed/rescon/2002/resolucao-1-8-maio-2002-497942-publicacaooriginal-1-pl.html).
- ADI 4029 (STF): notícia oficial de 8/3/2012, "Tramitação de novas MPs no Congresso terá de obedecer rito previsto na Constituição": https://noticias.stf.jus.br/postsnoticias/tramitacao-de-novas-mps-no-congresso-tera-de-obedecer-rito-previsto-na-constituicao/ (o acórdão e a ementa não foram lidos).
- Resolução da Câmara nº 33/2022 (arts. 105 e 143 do RICD): https://www2.camara.leg.br/legin/int/rescad/2022/resolucaodacamaradosdeputados-33-4-agosto-2022-793091-publicacaooriginal-165882-pl.html. Texto original do RICD (Res. 17/1989), art. 105 e parágrafo único: https://www2.camara.leg.br/legin/fed/rescad/1989/resolucaodacamaradosdeputados-17-21-setembro-1989-320110-publicacaooriginal-1-pl.html.
- Ato da Mesa do Senado nº 2/2014 (arquivamento ao final da legislatura, regulamenta o RISF art. 332): https://legis.senado.leg.br/norma/43296332/publicacao/43296350
- "Como se fazem as leis" (Jovem Senador): https://www12.senado.leg.br/jovemsenador/home/arquivos/como-se-fazem-as-leis. O texto foi extraído, mas o fluxograma é uma imagem: não serve de fonte do grafo.

**Conferido nos textos acima:**
- CF art. 48 (sanção não exigida para o que está nos arts. 49, 51 e 52), 49, 51, 52, 57 §5, 59, 60 (§§1 a 5 e I a III), 61, 62 (§§3 a 12), 64, 65, 66, 69.
- RICD arts. 17 m, 24 II, 33, 34, 41 VI, 58, 105, 108, 109, 123, 133, 138, 144, 145, 152 a 155, 164 §4º, 196, 200, 202 a 204 (§8 do art. 202 lido nesta conferência).
- RISF arts. 48 XXVIII, 91, 101 §1º, 211, 254, 282, 285 a 287, 328, 332, 334, 336 a 338, 354 a 373 (arts. 367, 368 e 372 relidos).
- Regimento Comum arts. 43, 46, 51, 52, 85, 104-A, 106 a 106-D; Resolução nº 1/2002-CN arts. 1º a 14, 18; Resolução da Câmara nº 33/2022 (inteira); Ato da Mesa do Senado nº 2/2014 (inteiro).

**Não conferido** (aparece no texto acima como tal): o desfecho do veto mantido (nem a CF nem o Regimento Comum lidos o dizem); em que etapa uma proposição desarquivada volta a tramitar (RISF art. 332 e Ato da Mesa 2/2014 não dizem; o RICD vigente nem prevê o desarquivamento); o que acontece com a proposta nova do RISF art. 367 (substitutivo da Câmara a PEC do Senado) depois de lida (os arts. 368 e 372 mandam aplicar à revisão e à tramitação as normas do Título e, no que couber, as demais do Regimento, sem dizer mais); o arquivamento da PEC inadmitida na Câmara sem requerimento de apreciação preliminar (o RICD art. 202 §1º só dá ao autor a faculdade de requerê-la; o §8 manda aplicar à PEC as regras de tramitação dos projetos de lei "no que não colidir" com o art. 202, e o art. 145 §3º manda arquivar a proposição que perde na apreciação preliminar, mas o texto não diz se há colisão nem o que ocorre sem requerimento) e se a urgência dos arts. 152 a 155 vale para a PEC (o mesmo §8 a admite se não colidir com o interstício de cinco sessões do §6º, e o art. 152 diz que a urgência dispensa interstícios, mas o texto não resolve o choque); quem promulga o decreto legislativo quando a Câmara é a Casa que conclui (RICD silencioso); o que acontece quando a comissão mista da MPV não emite parecer (a regra de 14 dias foi declarada inconstitucional na parte lida); o acórdão da ADI 4029; os Atos da Mesa citados nas notas dos regimentos, exceto o Ato nº 2/2014 (o volume 2 do RISF, "Normas conexas", agosto de 2025, foi lido: é só a lista das normas, cada uma com link, sem o texto; o link do Ato nº 2/2014 é o já usado); as situações da lista oficial que nenhum artigo lido define ("Aguardando Deliberação", "Aguardando Definição Encaminhamento" na Câmara; AGUARDANDO INCLUSÃO ORDEM DO DIA DE REQUERIMENTO e AGUARDANDO DOCUMENTAÇÃO COMPLEMENTAR SOLICITADA no Senado), que ficam sem etapa. Tentativa de ler o acórdão da ADI 4029 pelo portal do STF: a página é dinâmica e não devolveu o texto.

- Glossário do Senado: https://www12.senado.leg.br/noticias/glossario-legislativo (âncoras `#<slug>-legislativo`, p. ex. `#turno-suplementar-legislativo`). Não há glossário público da Câmara.
- Situações do Senado: https://legis.senado.leg.br/dadosabertos/processo/tipos-situacao (175 itens `{id, sigla, descricao, dataInicio, dataFim}`, p. ex. AGDESP = AGUARDANDO DESPACHO, PRONTPAUT = PRONTA PARA A PAUTA NA COMISSÃO, RMCD = REMETIDA À CÂMARA DOS DEPUTADOS). Decisões: https://legis.senado.leg.br/dadosabertos/processo/tipos-decisao (33 itens, p. ex. PERDA_EFICACIA, REEDITADA, APROVADO_PLV, REJEITADO_COMISSAO_TERM).
- Situações da Câmara: https://dadosabertos.camara.leg.br/api/v2/referencias/proposicoes/codSituacao (99 itens); tipos de tramitação: https://dadosabertos.camara.leg.br/api/v2/referencias/proposicoes/codTipoTramitacao (235 itens).
- Guia de tramitação da Câmara (texto explicativo, sem fluxo formal): https://www2.camara.leg.br/comunicacao/assessoria-de-imprensa/guia-para-jornalistas/tramitacao-das-proposicoes
- Vocabulário observado nos dados do site: índice local de 9.419 proposições e 300 matérias do Senado.
