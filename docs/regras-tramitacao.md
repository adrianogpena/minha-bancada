# Regras de tramitação das proposições

Base de conhecimento (só procedimento, sem opinião e sem resumo de projetos) de como cada tipo de proposição tramita no Congresso Nacional, que caminhos pode seguir e como reconhecemos cada etapa nos campos que o site já coleta. A tabela `ETAPAS_POR_TIPO` de `site/assets/js/etapas.js` é a tradução desta base; um teste confere que as duas têm os mesmos ids de etapa.

Como ler:
- Cada tipo tem um **caminho principal** (a sequência mais comum, a que a faixa mostra) e uma **tabela de arestas** (os desvios possíveis: não é uma linha só).
- Cada etapa é um cabeçalho `#### \`id\` — Rótulo`. Os ids estão em minúsculas e hífen.
- "Como reconhecer" usa os campos já coletados. Senado: `situacoes[i][3]` (descrição da situação), `despachos [dia, provimento, destinos[], terminativa]`, na ficha `dl{t,d,p}` (deliberação: texto, data, plenário/comissão), `ng` (norma gerada), `cn/cd/cdx` (número na Câmara). Câmara: `eventos [dia, orgao, tipo, situacao, despacho]`, índice `p.s` (situação), `sf` (ficha vinda do Senado), `ng`.
- Etapa sem campo que a reconheça fica marcada **"não reconhecível com os dados atuais"**: a faixa só a mostra como futura ou, se já passou, deduz pelas etapas seguintes.
- A caixa da situação difere por Casa (Senado em MAIÚSCULAS, Câmara em Title Case): compare sem diferenciar caixa nem acento.
- Regra de ouro do reconhecimento: vale o evento mais recente. Uma etapa posterior reconhecida marca como feitas (ou puladas, quando a proposição não passou por ela) todas as anteriores.

Vocabulário real observado nos dados (índice local, 9.419 proposições): Senado, `situacoes[i][3]` tem 20 valores nas matérias coletadas, entre eles AGUARDANDO DESPACHO, AGUARDANDO RECEBIMENTO DE EMENDAS, AGUARDANDO DESIGNAÇÃO DO RELATOR, MATÉRIA COM A RELATORIA, MATÉRIA DESPACHADA, INCLUÍDA NA PAUTA DA REUNIÃO, PRONTA PARA A PAUTA NA COMISSÃO, APROVADO PARECER NA COMISSÃO, APRECIADA EM DECISÃO TERMINATIVA PELAS COMISSÕES, AGUARDANDO INTERPOSIÇÃO DE RECURSO, PRONTO PARA DELIBERAÇÃO DO PLENÁRIO, INCLUÍDA EM ORDEM DO DIA, APROVADA, REMETIDA À CÂMARA DOS DEPUTADOS, REMETIDA À SANÇÃO, TRANSFORMADA EM NORMA JURÍDICA, RETIRADA PELO AUTOR, PEDIDO DE VISTA CONCEDIDO, AGUARDANDO AUDIÊNCIA PÚBLICA, MATÉRIA EM TRAMITAÇÃO. Provimentos de despacho: "Análise", "Tramitação Conjunta", "Ao Plenário". Em `p.s` aparecem ainda PREJUDICADA, ARQUIVADA AO FINAL DA LEGISLATURA. Câmara em `p.s`: "Aguardando Designação de Relator(a)", "Tramitando em Conjunto", "Aguardando Parecer", "Pronta para Pauta", "Aguardando Encaminhamento", "Arquivada", "Transformada em Norma Jurídica", "Aguardando Despacho do Presidente da Câmara dos Deputados (Chancela)".

---

## Tipo: PL, PLP

Projeto de lei ordinária (PL) e projeto de lei complementar (PLP). Iniciativa: deputados, senadores, comissões, Presidente da República, tribunais superiores, Procurador-Geral da República e cidadãos, conforme a matéria (CF art. 61). PLP exige maioria absoluta para aprovação (CF art. 69); PL, maioria simples. A Casa onde o projeto nasce é a **Casa de origem** (Câmara ou Senado); a outra é a **Casa revisora** (CF art. 64 e 65).

**Caminho principal:** `apresentado` → `comissoes` → `plenario-origem` → `casa-revisora` → `sancao-veto` → `lei`.

### Etapas

#### `apresentado` — Apresentado
Projeto protocolado, ainda sem relator ou sem despacho às comissões.
- **Como reconhecer.** Senado: situação AGUARDANDO DESPACHO, AGUARDANDO RECEBIMENTO DE EMENDAS, AGUARDANDO DESIGNAÇÃO DO RELATOR sem nenhum `despachos` ainda; ou primeira entrada de `situacoes`. Câmara: `p.s` "Aguardando Despacho do Presidente da Câmara dos Deputados" (inclui "(Chancela)"), "Aguardando Encaminhamento", ou `eventos` só com o tipo de apresentação.
- **O que pode acontecer depois.** Receber despacho às comissões (`comissoes`), ir direto ao plenário (`plenario-origem`, com urgência ou despacho "Ao Plenário"), ser retirado pelo autor ou arquivado (`arquivado`).
- **O que ainda falta.** "Ainda não é lei. O projeto foi apresentado e aguarda o despacho que define por quais comissões ou plenário ele passa."

#### `comissoes` — Comissões
Análise do mérito e da constitucionalidade nas comissões da Casa de origem.
- **Como reconhecer.** Senado: `despachos[i][1]` = "Análise" com `destinos[]` de comissões; situações MATÉRIA DESPACHADA, MATÉRIA COM A RELATORIA, INCLUÍDA NA PAUTA DA REUNIÃO, PRONTA PARA A PAUTA NA COMISSÃO, APROVADO PARECER NA COMISSÃO, PEDIDO DE VISTA CONCEDIDO, AGUARDANDO AUDIÊNCIA PÚBLICA. "Tramitação Conjunta" indica projeto apensado a outro. Câmara: `p.s` "Aguardando Designação de Relator(a)", "Aguardando Parecer", "Pronta para Pauta", "Tramitando em Conjunto"; `eventos[i][1]` com sigla de comissão (CCJC, CFT e semelhantes).
- **Etapa pulada.** Se o despacho for direto ao Plenário (provimento "Ao Plenário" no Senado) ou houver urgência aprovada antes do parecer, a etapa aparece como pulada (tracejada).
- **O que pode acontecer depois.** Parecer aprovado e ida ao Plenário (`plenario-origem`); decisão terminativa (Senado) ou conclusiva (Câmara) que dispensa o Plenário; rejeição que arquiva; requerimento de urgência que leva ao Plenário sem esperar parecer.
- **O que ainda falta.** "Ainda não é lei. O projeto está nas comissões, que dão parecer; depois segue ao Plenário, a não ser que a comissão decida sozinha (terminativa/conclusiva)."

#### `plenario-origem` — Plenário da Casa de origem
Votação em Plenário (turno único) na Casa onde o projeto foi apresentado.
- **Como reconhecer.** Senado: situação PRONTO PARA DELIBERAÇÃO DO PLENÁRIO, INCLUÍDA EM ORDEM DO DIA, APROVADA; na ficha `dl.p` = Plenário e `dl.d` com a data. Câmara: `p.s` "Pronta para Pauta" com órgão PLEN em `eventos`; `eventos[i][3]` com aprovação no Plenário (descrição contendo "Aprovad" e órgão PLEN) (não conferido).
- **O que pode acontecer depois.** Aprovado: vai à Casa revisora (`casa-revisora`); aprovado na Casa iniciadora em decisão terminativa/conclusiva e sem recurso, segue conforme a regra do tipo (Senado: REMETIDA À CÂMARA DOS DEPUTADOS; Câmara: remessa ao Senado). Rejeitado: `arquivado`. Retirado: `arquivado`.
- **O que ainda falta.** "Ainda não é lei. O Plenário vota; se aprovar, o texto vai à outra Casa para ser revisto."

#### `casa-revisora` — Casa revisora
A outra Casa analisa o texto: comissões e Plenário. Recebe número novo (`cn/cd/cdx` quando o projeto é do Senado e foi à Câmara).
- **Como reconhecer.** Senado como origem: situação REMETIDA À CÂMARA DOS DEPUTADOS (em `situacoes[i][3]`), e `cn/cd/cdx` com o número na Câmara; em seguida os `eventos` da Câmara do projeto de mesmo `cn`. Câmara como origem: `p.s` "Aguardando Apreciação pelo Senado Federal" (não conferido) e, na ficha, `sf` preenchido (a matéria veio do Senado). Senado como revisora: matéria com `sf`/origem da Câmara e despacho do Senado.
- **O que pode acontecer depois.** Aprovar sem mudar (`sancao-veto`); aprovar com mudanças (emendas ou substitutivo), e então volta à Casa de origem (`retorno-origem`); rejeitar (`arquivado`).
- **O que ainda falta.** "Ainda não é lei. A [Casa revisora], como Casa revisora, pode aprovar, mudar ou rejeitar o texto; se mudar, ele volta à Casa de origem. Depois vai à sanção."

#### `retorno-origem` — Volta à Casa de origem
Só ocorre quando a Casa revisora alterou o texto. A Casa de origem decide quais mudanças aceita; não pode introduzir texto novo (CF art. 65, parágrafo único).
- **Como reconhecer.** Senado: situação que indica retorno de substitutivo ou emendas da Câmara (APRECIAÇÃO DE EMENDAS/SUBSTITUTIVO DA CÂMARA, não conferido) depois de REMETIDA À CÂMARA DOS DEPUTADOS. Câmara: `eventos` posteriores ao envio com órgão PLEN e tipo de apreciação de emendas do Senado (não conferido). Não reconhecível com os dados atuais quando a fonte não distingue o retorno.
- **O que pode acontecer depois.** Aprovado: `sancao-veto`. Mudanças rejeitadas: vale o texto aprovado antes; `sancao-veto`.
- **O que ainda falta.** "Ainda não é lei. O texto foi mudado na outra Casa e voltou para a Casa de origem decidir sobre as mudanças. Depois vai à sanção."

#### `sancao-veto` — Sanção ou veto
O Presidente da República tem 15 dias úteis para sancionar ou vetar (CF art. 66).
- **Como reconhecer.** Senado: situação REMETIDA À SANÇÃO; `dl` mais recente. Câmara: `p.s` "Aguardando Sanção" (não conferido) ou evento de remessa à sanção em `eventos`. Veto total ou parcial: informe/evento com "Veto" no texto (campo de texto de `informes` ou `eventos[i][4]`) (não conferido).
- **O que pode acontecer depois.** Sancionado: `lei` (a sanção expressa ou o silêncio de 15 dias úteis, CF art. 66 §3). Vetado, total ou parcialmente: `veto-congresso`.
- **O que ainda falta.** "Ainda não é lei. O Presidente da República decide em até 15 dias úteis se sanciona ou veta."

#### `veto-congresso` — Veto no Congresso
Sessão conjunta do Congresso aprecia o veto; a rejeição exige maioria absoluta de deputados e de senadores (CF art. 66 §4).
- **Como reconhecer.** Informe/evento com "Veto" e "sessão do Congresso" (não conferido). Sem campo coletado confiável: **não reconhecível com os dados atuais** além da menção de veto no texto.
- **O que pode acontecer depois.** Veto derrubado: as partes vetadas são promulgadas (`lei`). Veto mantido: vale o resto do texto sancionado (`lei`) ou, em veto total, o projeto é arquivado (`arquivado`).
- **O que ainda falta.** "O veto aguarda a sessão do Congresso, que pode derrubá-lo ou mantê-lo."

#### `lei` — Lei
- **Como reconhecer.** Senado: situação TRANSFORMADA EM NORMA JURÍDICA e/ou campo `ng` (norma gerada) preenchido. Câmara: `p.s` "Transformada em Norma Jurídica" e `ng`.
- **O que pode acontecer depois.** Nada no processo legislativo; a lei pode ser alterada por novo projeto.
- **O que ainda falta.** "Já é lei: [ng]."

#### `arquivado` — Arquivado
Etapa de parada, mostrada em vermelho na etapa onde parou.
- **Como reconhecer.** Senado: situação RETIRADA PELO AUTOR, PREJUDICADA, ARQUIVADA AO FINAL DA LEGISLATURA, ou rejeição em `dl`. Câmara: `p.s` "Arquivada", "Retirado pelo Autor" ou "Prejudicada" (não conferido o texto exato).
- **O que pode acontecer depois.** Desarquivamento a pedido do autor no início da legislatura seguinte, conforme o regimento (RISF art. 332; RICD art. 105) (não conferido); volta à etapa em que estava.
- **O que ainda falta.** "Não tramita mais. [Motivo da situação]."

### Arestas de PL, PLP

| de | para | quando |
|---|---|---|
| `apresentado` | `comissoes` | o presidente da Casa despacha o projeto às comissões |
| `apresentado` | `plenario-origem` | urgência aprovada ou despacho direto "Ao Plenário": a etapa `comissoes` fica pulada |
| `comissoes` | `plenario-origem` | o parecer é aprovado e o projeto é incluído em pauta |
| `comissoes` | `casa-revisora` | comissão terminativa (Senado, RISF art. 91) ou conclusiva (Câmara, RICD art. 24 II) aprova e ninguém recorre ao Plenário: dispensa `plenario-origem` |
| `comissoes` | `plenario-origem` | recurso contra a decisão terminativa/conclusiva (prazo de cinco dias úteis, com assinatura de um décimo dos membros) leva o projeto ao Plenário |
| `comissoes` | `arquivado` | a comissão rejeita o projeto em decisão terminativa/conclusiva, o autor o retira ou ele fica prejudicado |
| `plenario-origem` | `casa-revisora` | o Plenário aprova o texto e o remete à outra Casa |
| `plenario-origem` | `arquivado` | o Plenário rejeita o projeto |
| `casa-revisora` | `sancao-veto` | a revisora aprova sem mudar o texto |
| `casa-revisora` | `retorno-origem` | a revisora muda o texto (emenda ou substitutivo): volta à Casa de origem |
| `casa-revisora` | `arquivado` | a revisora rejeita o projeto |
| `retorno-origem` | `sancao-veto` | a Casa de origem decide sobre as mudanças e remete à sanção |
| `sancao-veto` | `lei` | o Presidente sanciona (ou deixa passar 15 dias úteis sem decidir) |
| `sancao-veto` | `veto-congresso` | o Presidente veta, total ou parcialmente |
| `veto-congresso` | `lei` | o veto é derrubado (partes vetadas promulgadas) ou é mantido só em parte |
| `veto-congresso` | `arquivado` | veto total mantido |
| `arquivado` | `comissoes` | desarquivamento a pedido do autor, p. ex. ao fim da legislatura (arquivado ao final da legislatura) |

Outros desvios: urgência (Senado, RISF arts. 336-338; Câmara, RICD arts. 152-155) reduz prazos e pode levar o projeto ao Plenário sem parecer das comissões. Turno suplementar no Senado (RISF art. 282) vale para substitutivo integral aprovado em Plenário. Projeto de lei complementar segue o mesmo caminho, com quórum de maioria absoluta (CF art. 69).

---

## Tipo: PEC

Proposta de emenda à Constituição. Não vai à sanção: é promulgada pelas Mesas da Câmara e do Senado (CF art. 60 §3). Precisa de três quintos dos membros de cada Casa, em dois turnos em cada uma (CF art. 60 §2). Iniciativa de um terço dos deputados ou dos senadores, do Presidente da República ou de mais da metade das Assembleias Legislativas (CF art. 60 I-III).

**Caminho principal:** `apresentado` → `comissoes` → `plenario-1-turno` → `plenario-2-turno` → `casa-revisora` → `promulgacao`.

### Etapas

#### `apresentado` — Apresentada
- **Como reconhecer.** Senado: AGUARDANDO DESPACHO, AGUARDANDO DESIGNAÇÃO DO RELATOR ainda sem despacho. Câmara: "Aguardando Despacho do Presidente da Câmara dos Deputados (Chancela)" ou fase de admissibilidade.
- **O que pode acontecer depois.** Ir à comissão de constituição e justiça (`comissoes`); ser retirada ou arquivada.
- **O que ainda falta.** "Ainda não é emenda à Constituição. A proposta aguarda o despacho e a análise de admissibilidade."

#### `comissoes` — Comissão de Constituição e Justiça (CCJ)
Admissibilidade (não pode afrontar as cláusulas pétreas, CF art. 60 §4) e, na Câmara, comissão especial para o mérito.
- **Como reconhecer.** Senado: despacho "Análise" com destino CCJ; MATÉRIA COM A RELATORIA, PRONTA PARA A PAUTA NA COMISSÃO. Câmara: `eventos[i][1]` = CCJC e, depois, comissão especial (não conferido); `p.s` "Aguardando Designação de Relator(a)", "Aguardando Parecer".
- **O que pode acontecer depois.** Admitida e levada ao Plenário (`plenario-1-turno`); inadmissível: `arquivado`.
- **O que ainda falta.** "Ainda não é emenda à Constituição. A comissão examina se a proposta pode tramitar e dá o parecer."

#### `plenario-1-turno` — Plenário, 1º turno
- **Como reconhecer.** Senado: situação PRONTO PARA DELIBERAÇÃO DO PLENÁRIO / INCLUÍDA EM ORDEM DO DIA, e `dl` com o primeiro turno (texto contendo "1º turno"). Câmara: `eventos` com órgão PLEN e despacho de "1º Turno" (não conferido).
- **O que pode acontecer depois.** Três quintos aprovam: `plenario-2-turno`; não alcançando o quórum: `arquivado` (a matéria rejeitada ou prejudicada não pode ser reapresentada na mesma sessão legislativa, CF art. 60 §5).
- **O que ainda falta.** "Ainda não é emenda à Constituição. O Plenário vota em primeiro turno; precisa de três quintos."

#### `plenario-2-turno` — Plenário, 2º turno
- **Como reconhecer.** Senado: `dl` com "2º turno" ou situação APROVADA depois do 1º turno. Câmara: despacho de "2º Turno" nos `eventos` (não conferido).
- **O que pode acontecer depois.** Aprovada: `casa-revisora` (se a Casa era a de origem) ou `promulgacao` (se era a revisora e o texto não mudou); rejeitada: `arquivado`.
- **O que ainda falta.** "Ainda não é emenda à Constituição. Falta a votação em segundo turno nesta Casa."

#### `casa-revisora` — Outra Casa (2 turnos)
- **Como reconhecer.** Senado como origem: REMETIDA À CÂMARA (a situação das PEC aparece abreviada assim) e `cn/cd/cdx`. Câmara como origem: remessa ao Senado e `sf` na ficha.
- **O que pode acontecer depois.** Aprovada sem mudança em dois turnos: `promulgacao`; aprovada com mudança: volta à Casa de origem (`retorno-origem`); rejeitada: `arquivado`.
- **O que ainda falta.** "Ainda não é emenda à Constituição. A outra Casa também vota em dois turnos; se mudar o texto, ele volta à Casa de origem. Depois é promulgada, sem sanção."

#### `retorno-origem` — Volta à Casa de origem
Texto alterado na revisora volta para nova votação em dois turnos da parte alterada (CF art. 60 §2, e prática das Casas) (não conferido).
- **Como reconhecer.** Não reconhecível com os dados atuais; deduzido quando há remessa de volta após `casa-revisora`.
- **O que pode acontecer depois.** `promulgacao` ou `arquivado`.
- **O que ainda falta.** "Ainda não é emenda à Constituição. O texto mudou na outra Casa e volta para decisão."

#### `promulgacao` — Promulgação
Pelas Mesas da Câmara e do Senado, em sessão solene do Congresso, com número de ordem (CF art. 60 §3).
- **Como reconhecer.** `ng` preenchido (Emenda Constitucional nº N) e/ou situação TRANSFORMADA EM NORMA JURÍDICA.
- **O que pode acontecer depois.** Nada; entra em vigor com a publicação.
- **O que ainda falta.** "Já é emenda à Constituição: [ng]."

#### `arquivado` — Arquivada
- **Como reconhecer.** Senado: PREJUDICADA, ARQUIVADA AO FINAL DA LEGISLATURA, RETIRADA PELO AUTOR. Câmara: "Arquivada".
- **O que pode acontecer depois.** Desarquivamento a pedido do autor na legislatura seguinte (RISF art. 332) (não conferido).
- **O que ainda falta.** "Não tramita mais. [Motivo]."

### Arestas de PEC

| de | para | quando |
|---|---|---|
| `apresentado` | `comissoes` | a proposta é despachada à comissão de constituição e justiça |
| `comissoes` | `plenario-1-turno` | a proposta é admitida e o parecer é aprovado |
| `comissoes` | `arquivado` | a comissão a declara inadmissível ou o autor a retira |
| `plenario-1-turno` | `plenario-2-turno` | três quintos aprovam em 1º turno (há prazo entre os turnos, salvo calendário especial) |
| `plenario-1-turno` | `arquivado` | não alcança três quintos |
| `plenario-2-turno` | `casa-revisora` | aprovada em 2º turno na Casa de origem |
| `plenario-2-turno` | `promulgacao` | aprovada em 2º turno na revisora sem mudança do texto |
| `casa-revisora` | `promulgacao` | a outra Casa aprova nos dois turnos sem mudar o texto |
| `casa-revisora` | `retorno-origem` | a outra Casa muda o texto |
| `casa-revisora` | `arquivado` | rejeitada na outra Casa |
| `retorno-origem` | `promulgacao` | a Casa de origem conclui a votação do texto final |
| `arquivado` | `comissoes` | desarquivamento na legislatura seguinte |

Outros desvios: PEC pode ter turno suplementar no Senado (RISF art. 282, quando há substitutivo). Não há sanção nem veto. A Constituição não pode ser emendada durante intervenção federal, estado de defesa ou estado de sítio (CF art. 60 §1). Não há urgência regimental para PEC: o calendário especial no Plenário é aprovado pelas Casas (não conferido).

---

## Tipo: MPV

Medida provisória: ato do Presidente da República com força de lei, que vale desde a publicação e precisa ser convertida em lei pelo Congresso (CF art. 62). Prazo de 60 dias, prorrogável por mais 60 (art. 62 §3); a contagem para durante o recesso (art. 62 §4); depois de 45 dias sem votação passa a trancar a pauta da Casa onde está (art. 62 §6).

**Caminho principal:** `publicada` → `comissao-mista` → `plenario-camara` → `plenario-senado` → `sancao-veto` → `lei`.

### Etapas

#### `publicada` — Publicada (já vale)
- **Como reconhecer.** Senado: primeira situação; ficha com data de edição. Câmara: `eventos` iniciais com a apresentação da MPV e a leitura do ofício presidencial (não conferido).
- **O que pode acontecer depois.** Instalação da comissão mista (`comissao-mista`); perda de validade (`perdeu-validade`).
- **O que ainda falta.** "Já vale como lei, mas só por tempo limitado. O Congresso precisa convertê-la em lei em até 120 dias."

#### `comissao-mista` — Comissão mista
Deputados e senadores dão o parecer antes dos Plenários (CF art. 62 §9).
- **Como reconhecer.** Senado: `despachos` com destino "Comissão Mista"; situação AGUARDANDO DESIGNAÇÃO DO RELATOR, MATÉRIA COM A RELATORIA. Câmara: `eventos[i][1]` com "CMMPV" ou semelhante (não conferido).
- **O que pode acontecer depois.** Parecer aprovado e ida à Câmara (`plenario-camara`); a comissão não vota no prazo e a matéria segue ao Plenário da Câmara sem parecer (prática do STF, ADI 4029) (não conferido); perda de prazo (`perdeu-validade`).
- **O que ainda falta.** "Já vale como lei. A comissão mista analisa antes de a Câmara votar."

#### `plenario-camara` — Câmara dos Deputados
- **Como reconhecer.** Câmara: `eventos` com órgão PLEN após a comissão; `p.s` "Pronta para Pauta". Senado: situação REMETIDA À CÂMARA... (para a MPV é o inverso: o Senado só recebe depois). Campo `dl` de origem Câmara na ficha.
- **O que pode acontecer depois.** Aprovada: `plenario-senado`; rejeitada: `arquivado`; prazo vence: `perdeu-validade`.
- **O que ainda falta.** "Já vale como lei. A Câmara vota primeiro; depois o Senado."

#### `plenario-senado` — Senado Federal
- **Como reconhecer.** Senado: situação PRONTO PARA DELIBERAÇÃO DO PLENÁRIO, INCLUÍDA EM ORDEM DO DIA; `dl.p` = Plenário do Senado.
- **O que pode acontecer depois.** Aprovada sem mudança: `lei` (promulgada pelo Presidente da Mesa do Congresso, art. 62 §12) (não conferido); aprovada com alterações (projeto de lei de conversão): `sancao-veto`; rejeitada: `arquivado`; prazo vence: `perdeu-validade`.
- **O que ainda falta.** "Já vale como lei. O Senado vota; se mudar o texto, o projeto de lei de conversão vai à sanção."

#### `sancao-veto` — Sanção ou veto
Só quando o Congresso aprovou projeto de lei de conversão com alterações (CF art. 62 §12). Prazo e regras iguais às de PL (CF art. 66).
- **Como reconhecer.** Situação REMETIDA À SANÇÃO.
- **O que pode acontecer depois.** `lei` ou `veto-congresso`.
- **O que ainda falta.** "Já vale como lei. Falta a sanção ou o veto do Presidente ao texto convertido."

#### `veto-congresso` — Veto no Congresso
Igual ao de PL (CF art. 66 §4). Não reconhecível com os dados atuais além da menção ao veto no texto.
- **O que pode acontecer depois.** `lei` (veto derrubado ou mantido em parte) ou `arquivado` (veto total mantido).

#### `lei` — Lei de conversão
- **Como reconhecer.** `ng` preenchido ("Lei nº ..."); situação TRANSFORMADA EM NORMA JURÍDICA.
- **O que ainda falta.** "Convertida em lei: [ng]."

#### `perdeu-validade` — Perdeu a validade (caducidade)
A MPV não foi votada em 120 dias e deixa de valer; o Congresso deve regular por decreto legislativo as relações jurídicas do período (CF art. 62 §3 e §11).
- **Como reconhecer.** Senado: situação como "PERDA DE EFICÁCIA" / "PERDEU A EFICÁCIA" (não conferido, nenhuma MPV no recorte local). Câmara: `p.s` "Arquivada" com despacho de perda de eficácia (não conferido).
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
| `comissao-mista` | `plenario-camara` | o parecer é aprovado, ou a matéria segue sem parecer no prazo |
| `comissao-mista` | `perdeu-validade` | os 120 dias acabam |
| `plenario-camara` | `plenario-senado` | a Câmara aprova |
| `plenario-camara` | `arquivado` | a Câmara rejeita |
| `plenario-camara` | `perdeu-validade` | os 120 dias acabam |
| `plenario-senado` | `lei` | o Senado aprova sem mudar o texto |
| `plenario-senado` | `sancao-veto` | o Senado aprova projeto de lei de conversão com alterações |
| `plenario-senado` | `arquivado` | o Senado rejeita |
| `plenario-senado` | `perdeu-validade` | os 120 dias acabam |
| `sancao-veto` | `lei` | o Presidente sanciona |
| `sancao-veto` | `veto-congresso` | o Presidente veta |
| `veto-congresso` | `lei` | o veto é derrubado |
| `veto-congresso` | `arquivado` | veto total mantido |

---

## Tipo: PDL

Projeto de decreto legislativo: matérias de competência exclusiva do Congresso (CF art. 49), como aprovar tratados e sustar atos do Executivo. Não há sanção nem veto; o decreto legislativo é promulgado pelo Presidente do Senado, como Presidente do Congresso (CF art. 57 §5) (não conferido).

**Caminho principal:** `apresentado` → `comissoes` → `plenario-origem` → `casa-revisora` → `promulgacao`.

### Etapas

#### `apresentado` — Apresentado
- **Como reconhecer.** Senado: AGUARDANDO DESPACHO, AGUARDANDO DESIGNAÇÃO DO RELATOR, sem despacho. Câmara: "Aguardando Despacho..." / "Aguardando Encaminhamento".
- **O que pode acontecer depois.** `comissoes`, `plenario-origem` (urgência), `arquivado`.
- **O que ainda falta.** "Ainda não é decreto legislativo. Aguarda despacho às comissões."

#### `comissoes` — Comissões
- **Como reconhecer.** Igual a PL (despacho "Análise", MATÉRIA COM A RELATORIA, PRONTA PARA A PAUTA NA COMISSÃO; Câmara: "Aguardando Designação de Relator(a)", "Aguardando Parecer", "Pronta para Pauta").
- **O que pode acontecer depois.** `plenario-origem`; urgência que pula esta etapa; `arquivado`.
- **O que ainda falta.** "Ainda não é decreto legislativo. As comissões dão o parecer; depois segue ao Plenário."

#### `plenario-origem` — Plenário da Casa de origem
- **Como reconhecer.** Igual a PL: PRONTO PARA DELIBERAÇÃO DO PLENÁRIO, INCLUÍDA EM ORDEM DO DIA, APROVADA; `dl.p` = Plenário.
- **O que pode acontecer depois.** `casa-revisora` ou `arquivado`.
- **O que ainda falta.** "Ainda não é decreto legislativo. Se o Plenário aprovar, o texto vai à outra Casa."

#### `casa-revisora` — Outra Casa
- **Como reconhecer.** REMETIDA À CÂMARA (DOS DEPUTADOS) e `cn/cd/cdx`; ou `sf` na ficha da Câmara.
- **O que pode acontecer depois.** Aprovado: `promulgacao`; mudado: volta à Casa de origem (`retorno-origem`); rejeitado: `arquivado`.
- **O que ainda falta.** "Ainda não é decreto legislativo. A outra Casa pode aprovar, mudar ou rejeitar; depois é promulgado, sem sanção."

#### `retorno-origem` — Volta à Casa de origem
- **Como reconhecer.** Não reconhecível com os dados atuais.
- **O que pode acontecer depois.** `promulgacao` ou `arquivado`.
- **O que ainda falta.** "O texto mudou na outra Casa e volta para decisão."

#### `promulgacao` — Promulgação
- **Como reconhecer.** `ng` ("Decreto Legislativo nº ...") e/ou TRANSFORMADA EM NORMA JURÍDICA.
- **O que ainda falta.** "Já é decreto legislativo: [ng]."

#### `arquivado` — Arquivado
- **Como reconhecer.** PREJUDICADA, RETIRADA PELO AUTOR, ARQUIVADA AO FINAL DA LEGISLATURA; Câmara: "Arquivada".
- **O que pode acontecer depois.** Desarquivamento a pedido do autor na legislatura seguinte (não conferido).
- **O que ainda falta.** "Não tramita mais. [Motivo]."

### Arestas de PDL

| de | para | quando |
|---|---|---|
| `apresentado` | `comissoes` | despacho às comissões |
| `apresentado` | `plenario-origem` | urgência ou despacho ao Plenário: `comissoes` fica pulada |
| `comissoes` | `plenario-origem` | parecer aprovado |
| `comissoes` | `casa-revisora` | comissão em caráter terminativo/conclusivo aprova e ninguém recorre: dispensa `plenario-origem` |
| `comissoes` | `arquivado` | rejeitado, retirado ou prejudicado |
| `plenario-origem` | `casa-revisora` | Plenário aprova |
| `plenario-origem` | `arquivado` | Plenário rejeita |
| `casa-revisora` | `promulgacao` | aprovado sem mudar o texto |
| `casa-revisora` | `retorno-origem` | texto mudado |
| `casa-revisora` | `arquivado` | rejeitado |
| `retorno-origem` | `promulgacao` | a Casa de origem decide sobre as mudanças |
| `arquivado` | `comissoes` | desarquivamento na legislatura seguinte |

---

## Tipo: PRS, PRC

Projeto de resolução do Senado (PRS, CF art. 52) e da Câmara (PRC, CF art. 51): atos de organização e de competência privativa de uma só Casa. Não passam pela outra Casa nem pelo Presidente da República. Requerimentos (de informação, de urgência etc.) seguem curto caminho próprio na mesma Casa e podem ser tratados junto desta seção: apresentação, decisão da Mesa ou do Plenário, fim.

**Caminho principal:** `apresentado` → `comissoes` → `plenario` → `promulgacao`.

### Etapas

#### `apresentado` — Apresentado
- **Como reconhecer.** Senado: AGUARDANDO DESPACHO, AGUARDANDO DESIGNAÇÃO DO RELATOR sem despacho. Câmara: "Aguardando Designação de Relator(a)" no início do rito, "Aguardando Encaminhamento".
- **O que pode acontecer depois.** `comissoes`, `plenario` (urgência), `arquivado`.
- **O que ainda falta.** "Ainda não é resolução. Aguarda o despacho às comissões ou ao Plenário."

#### `comissoes` — Comissões
- **Como reconhecer.** Senado: despacho "Análise"; MATÉRIA COM A RELATORIA, PRONTA PARA A PAUTA NA COMISSÃO. Câmara: "Aguardando Parecer", "Pronta para Pauta", "Tramitando em Conjunto".
- **O que pode acontecer depois.** `plenario` ou, com urgência/despacho direto, a etapa fica pulada; `arquivado`.
- **O que ainda falta.** "Ainda não é resolução. As comissões dão o parecer; depois vota o Plenário."

#### `plenario` — Plenário
- **Como reconhecer.** Senado: PRONTO PARA DELIBERAÇÃO DO PLENÁRIO, INCLUÍDA EM ORDEM DO DIA, APROVADA; `dl.p` = Plenário. Câmara: PLEN em `eventos`.
- **O que pode acontecer depois.** Aprovado: `promulgacao`; rejeitado: `arquivado`.
- **O que ainda falta.** "Ainda não é resolução. O Plenário desta Casa decide; aprovado, é promulgado sem passar pela outra Casa."

#### `promulgacao` — Promulgação
- **Como reconhecer.** Senado: TRANSFORMADA EM NORMA JURÍDICA (a situação mais frequente em PRS no índice) e/ou `ng` ("Resolução nº ..."). Câmara: "Transformada em Norma Jurídica" / `ng`.
- **O que ainda falta.** "Já é resolução: [ng]."

#### `arquivado` — Arquivado
- **Como reconhecer.** PREJUDICADA, RETIRADA PELO AUTOR; Câmara: "Arquivada".
- **O que ainda falta.** "Não tramita mais. [Motivo]."

### Arestas de PRS, PRC

| de | para | quando |
|---|---|---|
| `apresentado` | `comissoes` | despacho às comissões |
| `apresentado` | `plenario` | urgência ou despacho ao Plenário: `comissoes` fica pulada |
| `comissoes` | `plenario` | parecer aprovado |
| `comissoes` | `arquivado` | rejeitado, retirado ou prejudicado |
| `plenario` | `promulgacao` | o Plenário aprova: a resolução é promulgada pela Casa, sem sanção |
| `plenario` | `arquivado` | o Plenário rejeita |
| `arquivado` | `comissoes` | desarquivamento na legislatura seguinte (não conferido) |

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

Constituição Federal, via `linkCF(art)` (ficha.js:55), `https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm#art<N>`. Em nenhuma fonte abaixo foi possível baixar o texto (o planalto.gov.br recusou a conexão TLS do `curl` e as páginas dos regimentos não foram abertas): **todas as citações de artigo vêm da norma conhecida e não foram conferidas na fonte nesta sessão (não conferido)**; confira antes de tornar o texto autoridade.

- Iniciativa e quórum: PL/PLP, CF [art. 61](https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm#art61) (não conferido); PLP exige maioria absoluta, CF [art. 69](https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm#art69) (não conferido).
- Casa de origem e revisora, retorno de emendas: CF [art. 64](https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm#art64) e [art. 65](https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm#art65) (não conferido).
- Sanção, veto e sessão do Congresso: CF [art. 66](https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm#art66) (não conferido); urgência constitucional do Presidente: CF [art. 64](https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm#art64) §1º (não conferido).
- PEC: CF [art. 60](https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm#art60) (não conferido), dois turnos em cada Casa (§2º), promulgação pelas Mesas (§3º), cláusulas pétreas (§4º), impedimentos (§1º).
- MPV: CF [art. 62](https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm#art62) (não conferido), prazos §3º-§7º, comissão mista §9º, lei de conversão §12, reedição §10.
- PDL, PRS, PRC: competência exclusiva do Congresso, CF [art. 49](https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm#art49); da Câmara, [art. 51](https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm#art51); do Senado, [art. 52](https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm#art52); promulgação pelo Presidente do Congresso, [art. 57](https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm#art57) §5º (todos não conferidos).
- RISF (Regimento Interno do Senado Federal, artigos sem âncora): https://www25.senado.leg.br/web/atividade/legislacao/regimento-interno. Terminativo, RISF art. 91 (não conferido); urgência, RISF arts. 336-338 (não conferido); turno suplementar, RISF art. 282 (não conferido); arquivamento ao fim da legislatura e desarquivamento, RISF art. 332 (não conferido).
- RICD (Regimento Interno da Câmara dos Deputados): https://www2.camara.leg.br/atividade-legislativa/legislacao/regimento-interno-da-camara-dos-deputados. Conclusivo, RICD art. 24 II (não conferido); urgência, RICD arts. 152-155 (não conferido); desarquivamento, RICD art. 105 (não conferido).
- Glossário do Senado: https://www12.senado.leg.br/noticias/glossario-legislativo (âncoras `#<slug>-legislativo`, p. ex. `#turno-suplementar-legislativo`). Não há glossário público da Câmara.
- Situações do Senado: https://legis.senado.leg.br/dadosabertos/processo/tipos-situacao (175 itens `{id, sigla, descricao}`, p. ex. AGDESP = AGUARDANDO DESPACHO, PRONTPAUT = PRONTA PARA A PAUTA NA COMISSÃO, RMCD = REMETIDA À CÂMARA DOS DEPUTADOS).
- Situações da Câmara: https://dadosabertos.camara.leg.br/api/v2/referencias/proposicoes/codSituacao (99 itens); tipos de tramitação: https://dadosabertos.camara.leg.br/api/v2/referencias/proposicoes/codTipoTramitacao (235 itens).
- Vocabulário observado nos dados do site: relatório da etapa anterior do plano (índice local de 9.419 proposições e 300 matérias do Senado).
