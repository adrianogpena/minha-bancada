# CHANGELOG dos dados

Registro de **quando** cada conjunto de dados entrou no projeto, **de onde** vem (URL) e **como** foi baixado.
Regra: toda fonte nova ou mudança de coleta ganha uma entrada aqui, no mesmo commit.
Datas dos conjuntos que já existiam vêm do primeiro commit que os trouxe (`git log --diff-filter=A`).
Todas as coletas rodam sozinhas no GitHub Actions (`.github/workflows/atualizar.yml`, todo dia às 06:17 de Brasília), salvo onde indicado.

## Conjuntos já no projeto

### TSE: eleitos, bens, votos, fotos e redes (`dados/tse/<ano>/<UF>.json`)
- **Entrada:** 2022, 2024 e 2026 em 2026-10-17; 2018 (só senadores) em 2026-10-18.
- **De onde:** `https://cdn.tse.jus.br/estatistica/sead/odsele/` (portal https://dadosabertos.tse.jus.br):
  - `consulta_cand/consulta_cand_<ano>.zip` (candidatos e situação)
  - `bem_candidato/bem_candidato_<ano>.zip` (bens declarados)
  - `votacao_candidato_munzona/votacao_candidato_munzona_<ano>.zip` (votos)
  - `consulta_cand/rede_social_candidato_<ano>.zip` (redes sociais; 2022 é um ZIP por UF: `_<UF>.zip`)
  - `https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes<ano>/fotos/foto_cand<ano>_<UF>_div.zip` (fotos, só cargos estaduais e federais; salvas em `site/fotos/<ano>/`)
- **Como:** `python scripts/coletar_tse.py` baixa o ZIP por HTTP (requests, streaming) para um arquivo temporário, lê o CSV de dentro, guarda só os eleitos e as colunas usadas e grava um JSON por UF. Anos encerrados são baixados uma vez só; 2026 (em andamento) é refeito a cada 2 dias.

### Câmara dos Deputados: deputados, votações, proposições, despesas (`dados/votacoes/`, `dados/proposicoes/`, `dados/proposicoes_detalhe.json`)
- **Entrada:** 2026-10-17 (os que vão para o git; `dados/deputados*` é refeito a cada execução e fica fora do git).
- **De onde:** API de Dados Abertos da Câmara, `https://dadosabertos.camara.leg.br/api/v2` (documentação: https://dadosabertos.camara.leg.br/swagger/api.html).
- **Como:** `python scripts/coletar.py`, chamadas HTTP JSON paginadas com repetição automática; o histórico de votações cresce a cada execução (continua de onde parou).

### Senado: votações, matérias e gastos CEAPS (`dados/senado_votacoes/`, `dados/senado_materias.json`)
- **Entrada:** 2026-10-17 (votações e matérias). CEAPS e autorias (`dados/senado_ceaps.json`, `dados/senado_autorias.json`) entraram na versão de 2026-10-18 e não vão para o git (baixados de novo a cada execução).
- **De onde:** `https://legis.senado.leg.br/dadosabertos` (senadores, votações, autorias, matérias) e `https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/despesas_ceaps/<ano>` (CEAPS).
- **Como:** `python scripts/coletar.py` (mesmo script da Câmara, etapas do Senado), API JSON.

### Presidente: projetos e MPs enviados ao Congresso (`dados/executivo.json`)
- **Entrada:** 2026-10-17.
- **De onde:** API da Câmara (`https://dadosabertos.camara.leg.br/api/v2`), proposições PL, PLP, PEC e MPV de autoria do Presidente desde 2023, com a situação (sancionado, vetado, em tramitação…).
- **Como:** `python scripts/coletar_executivo.py`.

### Assembleias Legislativas: deputados, projetos e votos nominais (`dados/estaduais/<UF>/`)
- **Entrada:** 2026-10-17, para AC, AL, AM, PB, PI, RO e TO (Assembleias que usam o SAPL do Interlegis).
- **De onde:** API REST do SAPL de cada Assembleia, `https://sapl.al.<uf>.leg.br/api/` (hosts em `ASSEMBLEIAS`, em `scripts/coletar_estaduais.py`).
- **Como:** `python scripts/coletar_estaduais.py` (deputados, matérias de 2023 em diante, votações). Projetos de anos anteriores são consultados de novo só a cada 7 dias.

### Governadores: projetos, vetos e mensagens enviados à Assembleia (`dados/estaduais/<UF>/governo_<ano>.json`)
- **Entrada:** 2026-10-17 (mesmas Assembleias acima).
- **De onde:** SAPL de cada Assembleia, matérias cujo autor é o Governador/Poder Executivo.
- **Como:** `python scripts/coletar_governadores.py`.

### Prefeitos de capitais: projetos enviados à Câmara Municipal (`dados/municipais/<UF>/prefeitura_<ano>.json`)
- **Entrada:** 2026-10-18 (2025 e 2026), para Rio Branco (AC), Boa Vista (RR), Natal (RN), João Pessoa (PB), São Paulo, Salvador e Goiânia.
- **De onde e como:**
  - AC, RR, RN, PB: SAPL da Câmara Municipal, `python scripts/coletar_prefeituras.py`.
  - SP: webservice do SPLegis, `https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx`, `python scripts/coletar_prefeitura_sp.py`.
  - BA (Salvador): grade Scriptcase `https://cmsalvador.sys.inf.br/cl/prop_interna/`, `python scripts/coletar_prefeitura_ba.py`.
  - GO (Goiânia): consulta pública do SUAP `https://suap.camaragyn.go.gov.br/camara/consulta_publica/`, `python scripts/coletar_prefeitura_go.py` (usa os certificados em `scripts/certs/`).
- **Capitais sem coletor e o motivo:** `dados/municipais/capitais_sem_dados.md`.

### Mapas e códigos de municípios
- `dados/municipios_ibge.json` (código TSE do município → código IBGE), entrada em 2026-10-18. **Origem exata não registrada na época**: o arquivo foi adicionado pronto, sem script. Pendente: refazer com script e registrar a fonte aqui.
- Malhas do mapa do Brasil: carregadas pelo navegador direto da API do IBGE, `https://servicodados.ibge.gov.br/api/v3/malhas` (`site/assets/app.js`); nada fica salvo no projeto.
- `site/geo/df_ras.json` (Regiões Administrativas do DF), entrada em 2026-10-18: camada do IPE-DF baixada à mão e simplificada com `python scripts/simplificar_df.py <arquivo>`. URL da camada não registrada; pendente.

## Outros arquivos do TSE (ainda não usados no site)
Existem em `https://cdn.tse.jus.br/estatistica/sead/odsele/<pasta>/<arquivo>.zip`; URLs e tamanhos conferidos em 2026-10-18 (HTTP 200). Baixados com `python scripts/baixar_tse.py`, para `dados/tse_bruto/` (fora do git).

| Conjunto | Pasta / arquivo | 2022 | 2024 |
|---|---|---|---|
| Prestação de contas (receitas, despesas, doadores) | `prestacao_contas/prestacao_de_contas_eleitorais_candidatos_<ano>.zip` | 467 MB | 1,3 GB |
| Votos do partido por município/zona | `votacao_partido_munzona/votacao_partido_munzona_<ano>.zip` | 26 MB | 6 MB |
| Votos por seção | `votacao_secao/votacao_secao_<ano>_<UF>.zip` (um por UF, `ZZ` = exterior; SP: 901 MB e 476 MB) | por UF | por UF |
| Perfil do eleitorado | `perfil_eleitorado/perfil_eleitorado_<ano>.zip` | 77 MB | 334 MB |
| Comparecimento, brancos e nulos | `detalhe_votacao_munzona/detalhe_votacao_munzona_<ano>.zip` | 4 MB | 1,5 MB |
| Coligações | `consulta_coligacao/consulta_coligacao_<ano>.zip` | 0,4 MB | 11 MB |
| Vagas | `consulta_vagas/consulta_vagas_<ano>.zip` | 0,2 MB | 0,6 MB |
| Motivo de cassação (só indeferimento de candidatura; pouco útil para eleitos) | `motivo_cassacao/motivo_cassacao_<ano>.zip` | 0,2 MB | 0,6 MB |

Filiação partidária e certidões criminais: não achadas em dadosabertos.tse.jus.br.

## Downloads do TSE (script `scripts/baixar_tse.py`)

- 2026-10-18 20:01: `dados/tse_bruto/consulta_vagas/consulta_vagas_2022.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_vagas/consulta_vagas_2022.zip (0.2 MB, sha256 `be65a63ef644c91e…`)
- 2026-10-18 20:01: `dados/tse_bruto/consulta_vagas/consulta_vagas_2024.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_vagas/consulta_vagas_2024.zip (0.6 MB, sha256 `6f2f45b872904672…`)
- 2026-10-18 20:01: `dados/tse_bruto/detalhe_votacao_munzona/detalhe_votacao_munzona_2022.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_munzona/detalhe_votacao_munzona_2022.zip (4.4 MB, sha256 `402c9983670e012c…`)
- 2026-10-18 20:01: `dados/tse_bruto/detalhe_votacao_munzona/detalhe_votacao_munzona_2024.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_munzona/detalhe_votacao_munzona_2024.zip (1.5 MB, sha256 `6ea9094561410ed0…`)
- 2026-10-18 20:01: `dados/tse_bruto/consulta_coligacao/consulta_coligacao_2022.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_coligacao/consulta_coligacao_2022.zip (0.4 MB, sha256 `26be7b36352cc037…`)
- 2026-10-18 20:01: `dados/tse_bruto/consulta_coligacao/consulta_coligacao_2024.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_coligacao/consulta_coligacao_2024.zip (11.0 MB, sha256 `32fdd73f469a4ebc…`)
- 2026-10-18 20:01: `dados/tse_bruto/motivo_cassacao/motivo_cassacao_2022.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/motivo_cassacao/motivo_cassacao_2022.zip (0.2 MB, sha256 `e4f0b5c061763e12…`)
- 2026-10-18 20:01: `dados/tse_bruto/motivo_cassacao/motivo_cassacao_2024.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/motivo_cassacao/motivo_cassacao_2024.zip (0.6 MB, sha256 `50519d09bb4219a5…`)
- 2026-10-18 20:02: `dados/tse_bruto/votacao_partido_munzona/votacao_partido_munzona_2022.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_partido_munzona/votacao_partido_munzona_2022.zip (26.3 MB, sha256 `ee46ca2c66389a20…`)
- 2026-10-18 20:02: `dados/tse_bruto/votacao_partido_munzona/votacao_partido_munzona_2024.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_partido_munzona/votacao_partido_munzona_2024.zip (6.2 MB, sha256 `2831f03711e379a6…`)
- 2026-10-18 20:32: `dados/tse_bruto/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2022.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2022.zip (467.3 MB, sha256 `21dc6069bb956379…`)
- 2026-10-18 20:51: `dados/tse_bruto/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2024.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2024.zip (1335.3 MB, sha256 `f0463d92d97a3323…`)
- 2026-10-18 20:53: `dados/tse_bruto/perfil_eleitorado/perfil_eleitorado_2022.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitorado/perfil_eleitorado_2022.zip (76.7 MB, sha256 `4bccad7e39ec13ea…`)
- 2026-10-18 20:53: `dados/tse_bruto/perfil_eleitorado/perfil_eleitorado_2024.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitorado/perfil_eleitorado_2024.zip (333.6 MB, sha256 `fd6703bdaa89aba0…`)
- 2026-10-18 20:53: `dados/tse_bruto/votacao_secao/votacao_secao_2022_AC.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_AC.zip (6.7 MB, sha256 `d17b815a4d6faa49…`)
- 2026-10-18 20:54: `dados/tse_bruto/votacao_secao/votacao_secao_2022_AL.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_AL.zip (30.3 MB, sha256 `d5ae3a20a8ecc32b…`)
- 2026-10-18 20:55: `dados/tse_bruto/votacao_secao/votacao_secao_2022_AM.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_AM.zip (44.0 MB, sha256 `1ba6c258320799f5…`)
- 2026-10-18 20:55: `dados/tse_bruto/votacao_secao/votacao_secao_2022_AP.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_AP.zip (7.3 MB, sha256 `e7f0c8836f5dcbb0…`)
- 2026-10-18 21:01: `dados/tse_bruto/votacao_secao/votacao_secao_2022_BA.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_BA.zip (191.5 MB, sha256 `54d397ff4b5a39d6…`)
- 2026-10-18 21:05: `dados/tse_bruto/votacao_secao/votacao_secao_2022_CE.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_CE.zip (111.5 MB, sha256 `47a8a151d4b51196…`)
- 2026-10-18 21:06: `dados/tse_bruto/votacao_secao/votacao_secao_2022_DF.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_DF.zip (34.3 MB, sha256 `eb9184e4927df556…`)
- 2026-10-18 21:06: `dados/tse_bruto/votacao_secao/votacao_secao_2022_ES.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_ES.zip (49.9 MB, sha256 `2c5dbd8fe808b1e4…`)
- 2026-10-18 21:06: `dados/tse_bruto/votacao_secao/votacao_secao_2022_GO.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_GO.zip (94.8 MB, sha256 `be46c92b743a95ad…`)
- 2026-10-18 21:06: `dados/tse_bruto/votacao_secao/votacao_secao_2022_MA.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_MA.zip (71.3 MB, sha256 `7422ee2870be969a…`)
- 2026-10-18 21:14: `dados/tse_bruto/votacao_secao/votacao_secao_2022_MG.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_MG.zip (295.1 MB, sha256 `e35b85dcc15fea43…`)
- 2026-10-18 21:15: `dados/tse_bruto/votacao_secao/votacao_secao_2022_MS.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_MS.zip (38.4 MB, sha256 `0e377349b066b24b…`)
- 2026-10-18 21:15: `dados/tse_bruto/votacao_secao/votacao_secao_2022_MT.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_MT.zip (34.6 MB, sha256 `371117d76ec7f115…`)
- 2026-10-18 21:15: `dados/tse_bruto/votacao_secao/votacao_secao_2022_PA.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_PA.zip (97.0 MB, sha256 `efec9371ca3e571e…`)
- 2026-10-18 21:15: `dados/tse_bruto/votacao_secao/votacao_secao_2022_PB.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_PB.zip (48.0 MB, sha256 `6918c138a450eb21…`)
- 2026-10-18 21:16: `dados/tse_bruto/votacao_secao/votacao_secao_2022_PE.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_PE.zip (122.2 MB, sha256 `058f042466913b54…`)
- 2026-10-18 21:16: `dados/tse_bruto/votacao_secao/votacao_secao_2022_PI.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_PI.zip (33.0 MB, sha256 `3883b3e9a67ce1b2…`)
- 2026-10-18 21:16: `dados/tse_bruto/votacao_secao/votacao_secao_2022_PR.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_PR.zip (161.0 MB, sha256 `67048a3c8d94b96c…`)
- 2026-10-18 21:16: `dados/tse_bruto/votacao_secao/votacao_secao_2022_RJ.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_RJ.zip (314.5 MB, sha256 `0adf67cbe0573691…`)
- 2026-10-18 21:16: `dados/tse_bruto/votacao_secao/votacao_secao_2022_RN.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_RN.zip (34.7 MB, sha256 `b211fba5ddfecf2c…`)
- 2026-10-18 21:16: `dados/tse_bruto/votacao_secao/votacao_secao_2022_RO.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_RO.zip (20.7 MB, sha256 `399bd2850ac81cd4…`)
- 2026-10-18 21:16: `dados/tse_bruto/votacao_secao/votacao_secao_2022_RR.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_RR.zip (7.7 MB, sha256 `66b18486f64797d2…`)
- 2026-10-18 21:16: `dados/tse_bruto/votacao_secao/votacao_secao_2022_RS.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_RS.zip (181.9 MB, sha256 `a6ca495c557673c7…`)
- 2026-10-18 21:16: `dados/tse_bruto/votacao_secao/votacao_secao_2022_SC.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_SC.zip (100.2 MB, sha256 `a658388c8b6094c1…`)
- 2026-10-18 21:16: `dados/tse_bruto/votacao_secao/votacao_secao_2022_SE.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_SE.zip (25.9 MB, sha256 `96530d4198fa97a3…`)
- 2026-10-18 21:17: `dados/tse_bruto/votacao_secao/votacao_secao_2022_SP.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_SP.zip (900.9 MB, sha256 `36c417ab6af3fc0a…`)
- 2026-10-18 21:17: `dados/tse_bruto/votacao_secao/votacao_secao_2022_TO.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_TO.zip (16.8 MB, sha256 `b2dedc70f6921376…`)
- 2026-10-18 21:17: `dados/tse_bruto/votacao_secao/votacao_secao_2024_AC.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_AC.zip (5.6 MB, sha256 `3505fe23101505e1…`)
- 2026-10-18 21:17: `dados/tse_bruto/votacao_secao/votacao_secao_2024_AL.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_AL.zip (17.4 MB, sha256 `cf102015682676e3…`)
- 2026-10-18 21:17: `dados/tse_bruto/votacao_secao/votacao_secao_2024_AM.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_AM.zip (34.1 MB, sha256 `b1f8db5148c81c3d…`)
- 2026-10-18 21:17: `dados/tse_bruto/votacao_secao/votacao_secao_2024_AP.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_AP.zip (5.1 MB, sha256 `4c23d90e011ab450…`)
- 2026-10-18 21:21: `dados/tse_bruto/votacao_secao/votacao_secao_2024_BA.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_BA.zip (114.0 MB, sha256 `2c3d1ad1ecf37c01…`)
- 2026-10-18 21:21: `dados/tse_bruto/votacao_secao/votacao_secao_2024_CE.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_CE.zip (69.5 MB, sha256 `9d5c2b1e7cab3556…`)
- 2026-10-18 21:21: `dados/tse_bruto/votacao_secao/votacao_secao_2024_ES.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_ES.zip (31.9 MB, sha256 `32fca0a59d860708…`)
- 2026-10-18 21:23: `dados/tse_bruto/votacao_secao/votacao_secao_2024_GO.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_GO.zip (64.4 MB, sha256 `ce2cae527a10de2b…`)
- 2026-10-18 21:23: `dados/tse_bruto/votacao_secao/votacao_secao_2024_MA.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_MA.zip (48.9 MB, sha256 `727ad9b99feb8ca1…`)
- 2026-10-18 21:26: `dados/tse_bruto/votacao_secao/votacao_secao_2024_MG.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_MG.zip (201.4 MB, sha256 `b305cb4783deac6e…`)
- 2026-10-18 21:26: `dados/tse_bruto/votacao_secao/votacao_secao_2024_MS.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_MS.zip (23.3 MB, sha256 `1dfa19396cba24bc…`)
- 2026-10-18 21:26: `dados/tse_bruto/votacao_secao/votacao_secao_2024_MT.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_MT.zip (26.1 MB, sha256 `4d84497edbd8944c…`)
- 2026-10-18 21:26: `dados/tse_bruto/votacao_secao/votacao_secao_2024_PA.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_PA.zip (71.5 MB, sha256 `3a9a65d48a49c09b…`)
- 2026-10-18 21:26: `dados/tse_bruto/votacao_secao/votacao_secao_2024_PB.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_PB.zip (28.1 MB, sha256 `a2005be05e2ee36d…`)
- 2026-10-18 21:26: `dados/tse_bruto/votacao_secao/votacao_secao_2024_PE.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_PE.zip (66.7 MB, sha256 `a0644bdade0339f8…`)
- 2026-10-18 21:26: `dados/tse_bruto/votacao_secao/votacao_secao_2024_PI.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_PI.zip (23.3 MB, sha256 `e5eed87c495c4cb5…`)
- 2026-10-18 21:28: `dados/tse_bruto/votacao_secao/votacao_secao_2024_PR.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_PR.zip (110.1 MB, sha256 `737233f15259d9cc…`)
- 2026-10-18 21:28: `dados/tse_bruto/votacao_secao/votacao_secao_2024_RJ.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_RJ.zip (156.8 MB, sha256 `c956615e39ecc4ab…`)
- 2026-10-18 21:28: `dados/tse_bruto/votacao_secao/votacao_secao_2024_RN.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_RN.zip (21.6 MB, sha256 `9f986702c2059b17…`)
- 2026-10-18 21:28: `dados/tse_bruto/votacao_secao/votacao_secao_2024_RO.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_RO.zip (12.7 MB, sha256 `31fcada6606bd4e5…`)
- 2026-10-18 21:28: `dados/tse_bruto/votacao_secao/votacao_secao_2024_RR.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_RR.zip (4.1 MB, sha256 `3f2e5dd34af80b99…`)
- 2026-10-18 21:28: `dados/tse_bruto/votacao_secao/votacao_secao_2024_RS.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_RS.zip (96.1 MB, sha256 `42167998705f965f…`)
- 2026-10-18 21:28: `dados/tse_bruto/votacao_secao/votacao_secao_2024_SC.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_SC.zip (53.8 MB, sha256 `36cd7aa412d81ec3…`)
- 2026-10-18 21:28: `dados/tse_bruto/votacao_secao/votacao_secao_2024_SE.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_SE.zip (15.6 MB, sha256 `06a51a88f213f4e1…`)
- 2026-10-18 21:35: `dados/tse_bruto/votacao_secao/votacao_secao_2024_SP.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_SP.zip (475.8 MB, sha256 `3d7063c453ca4d2e…`)
- 2026-10-18 21:35: `dados/tse_bruto/votacao_secao/votacao_secao_2024_TO.zip` ← https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_TO.zip (10.2 MB, sha256 `9258920a27193be8…`)
