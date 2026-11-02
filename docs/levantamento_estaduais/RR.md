# RR (ALE-RR) vs coletor do PR

Testado em 2026-10-31, curl/requests com User-Agent comum, pausa de 2 s. Amostras em `.../pesquisa/rr/` e `pessoal_out.xlsx`.

Já coleta: deputados, verba indenizatória (ODT mensal, a partir de set/2025), diárias (XLSX/ODS mensal, a partir de out/2025).

## Resumo
| Item do PR | Status |
|---|---|
| deputados | JÁ TEM |
| diárias | JÁ TEM (só a partir de out/2025; antes só PDF) |
| verba / ressarcimento | JÁ TEM (itens); regras/PDF não coletados |
| gabinete (servidores lotados) | ENCONTRADO |
| contratos do órgão | ENCONTRADO (só PDF + nome de pasta) |
| licitações / contratações diretas (extra) | ENCONTRADO (XLSX mensal) |
| remuneração | NÃO PUBLICA por deputado/servidor (só PDF de resumo da folha) |
| proposições, normas, votação nominal, presença, pautas, atas | BLOQUEADO (SAPL 403) |
| leis/atos via Diário Oficial | ENCONTRADO parcial (PDF diário, texto livre) |

## Gabinete: ENCONTRADO (esforço baixo)
- Página: https://transparencia.al.rr.leg.br/execucao-orcamentaria-e-financeira/gestao-de-pessoal-a-partir-de-set25/ (mesma lista WP Display Files das verbas/diárias: `wpdf_nonce` + `data-sid`, POST `admin-ajax.php` `wpdf_load_folder_data`; reusa `Lista` do coletor).
- Pastas: `Ano 2025`, `Ano 2026`; subpastas mensais (`10-Outubro`, `1-Janeiro de 2026`...). Cada uma tem `CONSULTA SERVIDORES.xlsx` (outubro: 342 KB, ~1 aba).
- Colunas: `Matrícula | Nome | Desc. Vínculo | Dt. Admissão | Cargo | Função | Setor | Unidade`.
- Gabinete: `Setor` = `GAB. DEP. <NOME>` e `Unidade` = `DEP. <NOME>` (ex.: `GAB. DEP. ANGELA PORTELLA`, cargo `FS-11 Secretario Parlamentar`, vínculo `COMISSIONADOS`). Em out/2026: 24 valores distintos de `GAB. DEP.` (um por deputado). Liga ao deputado só por nome (usar `identidades.ligar_nomes`, entrada em ESTRATEGIAS para o prefixo "GAB. DEP.").
- Sem remuneração (o docstring já diz). Nome do servidor e matrícula são públicos na fonte; admissão em dd/mm/aaaa.
- Mensal, snapshot completo (não incremental); ler só o mês mais recente e guardar histórico por mês. Anos anteriores a set/2025: `gestao-de-pessoal-ate-ago-25` (provavelmente PDF).
- Risco: encoding do nome de pasta (mojibake no JSON; já tratado nas verbas); matrícula não é id de pessoa estável entre meses (usar matrícula como id original em `ids.gerar_id`).

## Contratos do órgão: ENCONTRADO, só PDF (esforço médio)
- https://transparencia.al.rr.leg.br/execucao-orcamentaria-e-financeira/contratos-a-partir-de-out25/ (mesma lista WPDF). Pastas `Contratos - Ano 2024/2025/2026`, dentro uma pasta por processo (`Processo Eletrônico nº 103-2025`) com `CONTRATO 11-2026.pdf` e `PUBLICACAO DO CONTRATO 11-2026.pdf`.
- Sem metadados estruturados (fornecedor, valor, objeto só no PDF). Dá para coletar lista de links (processo, nº do contrato, ano, URL); campos exigem extrair texto do PDF (pypdf funciona em PDFs de texto) com risco de formato.
- Antes de out/2025: `contratos-ate-set25` (página sem lista WPDF; estático, não testado a fundo).
- Atas de registro de preço: não vi seção própria.
- Extra mais estruturado: https://transparencia.al.rr.leg.br/execucao-orcamentaria-e-financeira/licitacoes-a-partir-de-out25/ , pastas `Ano 2026/<mês>/` com `LICITAÇÕES <MÊS> 2026.xlsx` e `CONTRATAÇÕES DIRETAS <MÊS> 2026.xlsx` (+ PDF equivalentes). Colunas não inspecionadas; esforço baixo a médio.

## Remuneração: NÃO PUBLICA estruturado
`resumos-da-folha-a-partir-de-set25` e `resumos-da-folha-ate-ago25` (na página gestao-de-pessoal-intro): só resumos em PDF, sem valor por deputado/servidor (conforme docstring). Não reverificado.

## Proposições, normas, votação nominal, presença, pautas, atas: BLOQUEADO
- Todo o SAPL (`https://sapl.al.rr.leg.br/`, `/api/`, `/norma/pesquisar`, `/materia/pesquisar-materia`, `/media/sapl/public/sessaoplenaria/<id>/ata/*.pdf`) responde 403 Forbidden (Apache) a curl com UA de navegador; mesmo bloqueio nos PDFs de ata (que aparecem no Google). Menu do site oficial aponta para SAPL em "Leis Estaduais" e "Sistema de Apoio ao Processo Legislativo".
- `transparencia.al.rr.leg.br/materias/...` aparece em busca (texto original de projeto) mas dá 404 hoje.
- Não achei pauta/ata/presença/votação em `al.rr.leg.br` nem `transparencia` (WP REST de pages/types sem seção legislativa; `/sistema-do-processo-legislativo/` só linka o SAPL).
- Possibilidade não testada: SAPL liberar por IP de nuvem/GitHub Actions ou UA diferente (testei só dois UAs, sem sucesso); falta de acesso foi consistente em 5 rotas. Sem contornar.

## Diário Oficial da ALE-RR: ENCONTRADO parcial (esforço alto, valor incerto)
- https://diarios.al.rr.leg.br/ (WordPress; home lista os PDFs do mês corrente; sem posts na REST, `X-WP-Total: 0`; sem paginação visível na home).
- PDF diário: `https://diarios.al.rr.leg.br/wp-content/uploads/AAAA/MM/DIARIO-ALE-RR-ED.-<nº>-<dd.mm.aaaa>.pdf` (http redireciona 301 para https; seguir redirect). Ex.: ED. 4743 de 06/10/2026, 3 páginas, 870 KB, texto extraível (pypdf), ~14 mil caracteres.
- Conteúdo: atos da Mesa, composição de comissões com nomes de deputados, provavelmente leis promulgadas, decretos legislativos, resoluções. Texto livre sem estrutura; autoria de proposição não confirmada. Útil para normas com baixa precisão; não substitui SAPL.
- Risco: layout variável, parse por regex frágil; ~80 PDFs/mês de histórico na home só do mês.

## Regras/PDF do ressarcimento (verba): não coletado, esforço baixo
Resolução 036/2021 citada no docstring; a página `verbas-indenizatorias-intro` pode ter o PDF da norma. Não inspecionei; é só um link de fonte.

## Ordem sugerida de implementação
1. Gabinete (XLSX pessoal, baixo).
2. Licitações/contratações diretas XLSX (inspecionar colunas) e lista de contratos (links).
3. Pedir ao usuário se SAPL pode ser acessado de outro ambiente antes de qualquer trabalho em proposições/votação/pautas.
