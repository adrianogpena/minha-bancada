# RJ (ALERJ): pesquisa de endpoints equivalentes ao coletor do PR

Ressalva: o `curl` direto em `alerjln1.alerj.rj.gov.br` deu "Empty reply" sem User-Agent de navegador, e a tentativa com User-Agent foi bloqueada pelo classificador do harness. As páginas do Lotus Notes (alerjln1) foram então lidas por WebFetch (sem corpo bruto salvo, só resumo). Formato real (HTML Domino, campos exatos) precisa ser confirmado ao implementar, com `comum.sessao()`. O portal de transparência foi testado por curl (HTTP 200, HTML Laravel).

## Já coleta
- deputados (TSE 2022, `dados/estaduais/RJ/deputados.json`), presença (Ordem do Dia, mensal, `presenca.json`), emendas impositivas 2025/2026 (XLSX /section/report/121), `ligacoes.json`.

## Itens do PR

### Proposições: ENCONTRADO (esforço médio)
- Base Domino, legislatura 2023-2027: `http://alerjln1.alerj.rj.gov.br/scpro2327.nsf/Internet/{LeiInt,LeiCompInt,EmendaInt,DecretoInt,ResolucaoInt,IndLegInt,IndInt,MensInt,MocaoInt,OficioInt,ProcessoInt,ReqInt,ReqInfInt,ReqSNInt,PropInt}?OpenForm`
- Lista HTML: colunas "Cadastro" (ex. 20260308467), "Data Publ.", "Autor(es)" (nome em maiúsculas, ou PODER EXECUTIVO), tags de comissão. Ordenação `&Count=15&ResortAscending=0`; paginação `&Start=N&Count=N` (padrão Domino). Mais novo primeiro (leitura incremental por parar na data conhecida).
- Documento: `/scpro2327.nsf/18c1dd68f96be3e7832566ec0018d833/<unid>?OpenDocument`: tipo, número/ano, código, autor(es), ementa, entrada/despacho/publicação, regime (urgência), comissões. Votação e tramitação detalhada: vazias/não mostradas na amostra.
- Alternativa por deputado: `/scpro2327.nsf/deputadosint?OpenForm&ExpandView` (lista de deputados com seus projetos; falhou com "socket hang up" por WebFetch, testar).
- Liga ao deputado só por nome (usar `identidades.ligar_nomes`, ESTRATEGIAS["RJ"]). Autores múltiplos por vírgula nas leis.
- Anos: legislaturas anteriores em scpro1923, scpro1519 (mesma estrutura). Sem filtro de data na URL; sem captcha/login observado.
- Riscos: HTML com cp1252 corrompido; Domino lento; volume alto (milhares de PL por legislatura, um GET por documento para ementa completa; a lista já dá autor+número, o que talvez baste).

### Normas legais (leis/decretos/resoluções com autoria): ENCONTRADO (baixo-médio)
- Leis ordinárias: `http://alerjln1.alerj.rj.gov.br/CONTLEI.NSF/LeiOrdInt?OpenForm` (colunas Lei, Ano, Status, Ementa, Autoria com deputados separados por vírgula; mais nova primeiro, ex. Lei 11347/2026 autor Carlos Minc).
- Também: `contlei.nsf/LeiCompInt`, `contlei.nsf/DecretoInt` (decretos legislativos), `contlei.nsf/ResolucaoInt` (Res. 2522/2026, colunas Res., Ano, Autoria, Ementa). Decreto: fetch falhou (socket hang up), mesma estrutura esperada.
- Documento da lei: `/CONTLEI.NSF/c8aa0900025feef6032564ec0060dfff/<unid>?OpenDocument` com Autoria, Projeto de origem (ex. PL 6164-A/2022), data, D.O., status, ementa. Sem PDF.
- Liga por nome. Decretos do Executivo não estão aqui (só legislativos).

### Votação nominal por deputado: NÃO PUBLICA (nesta fonte), tentar mais
- Ordem do Dia (`ordemdia.nsf/OrdemInt?OpenForm`, 1 documento por sessão) traz só a pauta (PL, autor, parecer, relator), sem resultado nem votos.
- "Discursos e Votações" (`taqalerj.nsf/AnoInt?OpenForm`) existe só para 2015/2019 e legislaturas anteriores (`taqalerj2006.nsf`): sem 2023-2027. Não testado o conteúdo.
- Nada de painel de votação em formato aberto achado (busca web sem resultado ALERJ). Status: NÃO PUBLICA para a legislatura atual (não confirmado em PDF de ata plenária).

### Presença: JÁ TEM

### Diárias: ENCONTRADO como PDF (esforço médio-alto)
- Página `https://transparencia.alerj.rj.gov.br/section/report/119`: ~33 PDFs, um por mês (2024 a 09/2026), vários por mês por categoria (ex. "DIÁRIAS - CIVIL - NO EXTERIOR - 02").
- Download: `https://transparencia.alerj.rj.gov.br/download-spic?file=<url www2.alerj.rj.gov.br/leideacesso/verArquivo.asp?idArquivo=N urlencoded>` (302 até 200 application/pdf, texto extraível, ~100 KB).
- Conteúdo da amostra (id 2973): nome do servidor + valor. Não tem coluna de deputado nem destino. Valor da amostra: servidores civis, não deputados. Utilidade para deputado: provável baixa. Liga só por nome.

### Remuneração: ENCONTRADO (esforço médio)
- Subsídio: `/section/report/62` mostra valor bruto atual em HTML (R$ 34.774,64 bruto, previdência, IR); sem histórico em arquivo.
- Folha: `/section/report/73`, um PDF por mês (id ex. 2962, 79 págs, 9 MB), texto extraível com `pdftotext -layout`. Colunas: NOME, CARGO, FUNÇÃO, rendimentos, descontos, líquido. Tem deputados? A amostra lista servidores; a coluna de lotação diz "DEPUTADO ESTADUAL" (70 linhas) em vez do nome do deputado.
- Tabela remuneratória `/section/report/103`.

### Gabinete (servidores por deputado): NÃO PUBLICA por deputado (parcial)
- A folha (acima) tem cargos de gabinete (ASSESSOR PARLAMENTAR, CHEFE DE GABINETE PARLAMENTAR, ASSISTENTE) mas a lotação aparece só como "DEPUTADO ESTADUAL", sem identificar qual. Sem vínculo servidor-deputado nos arquivos vistos.
- Checar: `/section/report/74`, `/75`, `/96` (nível superior, médio, bolsa-auxílio) e `docigp.alerj.rj.gov.br` (link da página; não testado) como possível fonte de cotas/gabinete.

### Pautas e atas (links): ENCONTRADO (baixo)
- Pautas plenárias: `ordemdia.nsf/OrdemInt?OpenForm` (já parcialmente usado na presença): lista data, hora, tipo de sessão e link; documento com pauta completa por regime de tramitação. Por sessão, 1 GET.
- Atas de comissões: `compcom.nsf/AtasInt?OpenForm` (permanentes) e `comtemp.nsf/AtasInt?OpenForm` (temporárias): data, reunião, comissão e link para cada ata. Composição de comissões: `compcom.nsf/ComCompInt?OpenForm`, `comtemp.nsf/ComCompInt?OpenForm`.
- Ata de plenário: não achada; a Ordem do Dia não tem ata.

### Contratos e atas de registro de preço do órgão: ENCONTRADO como PDF (esforço médio)
- Contratos `/section/report/118`: PDFs (ex. id 2972, 3 págs, tabela: número, natureza, objeto, contratante, modalidade, CNPJ - contratado, situação, valor). Texto extraível. Contratada tem CNPJ (normalizar por `fornecedores`).
- ARP `/section/report/51`: PDFs por ata (ex. 728, 2,3 MB; texto não extraído, pode ser imagem/scan).
- Pagamentos `/section/report/120` (PDF mensal, não aberto). Licitações: `http://www2.alerj.rj.gov.br/licitacao/default2.asp?param=buscar&modalidade=C|I|P|T` (ASP, não testado).
- Id de PDF muda a cada publicação: coletar pela lista da página (padrão `verArquivo.asp?idArquivo=`).

### Regras/PDF do ressarcimento (verba): NÃO PUBLICA
- Sem página de cota parlamentar/ressarcimento no portal. `/section/report/33` (Benefícios) tem 1 PDF (`idArquivo=2941`), `/72` Benefícios, 107 "Resolução nº 178 de 2019, art. 2º" (provável base legal da verba). Não abertos. Despesa individual por deputado: não publicada (já indicado no docstring: só PDF).

## Resumo
- ENCONTRADO: proposições, leis/decretos/resoluções com autoria, pautas e atas de comissão, contratos (PDF), folha/subsídio (PDF/HTML), diárias (PDF, civis).
- NÃO PUBLICA/não achado: votação nominal 2023-2027, gabinete por deputado, ressarcimento.
- Prioridade sugerida: normas legais (baixo), proposições (médio), pautas/atas (baixo), contratos (médio).
