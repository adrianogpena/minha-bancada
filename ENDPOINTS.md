# Endpoints usados

Lista de todos os endpoints externos que o projeto consulta (coletores em `scripts/` e navegador em `site/`).
As colunas **Status**, **Verificado em** e **Detalhe** são reescritas por `python scripts/testar_endpoints.py`;
o resto é editado à mão.

**Ao criar um endpoint novo, acrescente uma linha na tabela** (a URL de teste deve ser concreta e leve) e rode o script.
Um teste (`tests/test_endpoints_doc.py`) falha se um host usado no código não aparece aqui.

Status: ✅ OK · ❌ ERRO (resposta com falha ou fora do ar) · ❔ não testado.

| Nome | Grupo | URL de teste | Usado em | Status | Verificado em | Detalhe |
|---|---|---|---|---|---|---|
| camara_deputados | Câmara | https://dadosabertos.camara.leg.br/api/v2/deputados?itens=1 | scripts/coletar.py, site/assets/app.js | ✅ OK | 2026-10-21 | HTTP 200, application/json |
| camara_deputado | Câmara | https://dadosabertos.camara.leg.br/api/v2/deputados/204379 | scripts/coletar.py, site/assets/app.js | ✅ OK | 2026-10-21 | HTTP 200, application/json |
| camara_despesas | Câmara | https://dadosabertos.camara.leg.br/api/v2/deputados/204379/despesas?ano=2025&itens=1 | scripts/coletar.py, site/assets/app.js | ✅ OK | 2026-10-21 | HTTP 200, application/json |
| camara_cota_csv | Câmara | https://www.camara.leg.br/cotas/Ano-2026.csv.zip | scripts/coletar.py | ✅ OK | 2026-10-22 | baixado à mão (4.2 MB); ainda fora do `testar_endpoints.py` |
| camara_frentes_deputado | Câmara | https://dadosabertos.camara.leg.br/api/v2/deputados/204379/frentes | scripts/coletar.py, site/assets/app.js | ✅ OK | 2026-10-22 | HTTP 200, application/json |
| camara_arquivo_temas | Câmara | https://dadosabertos.camara.leg.br/arquivos/proposicoesTemas/json/proposicoesTemas-2025.json | scripts/coletar.py, site/assets/app.js | ✅ OK | 2026-10-22 | baixado à mão (~10 MB); ainda fora do `testar_endpoints.py` |
| camara_arquivo_orgaos | Câmara | https://dadosabertos.camara.leg.br/arquivos/orgaosDeputados/json/orgaosDeputados-L57.json | scripts/coletar.py | ✅ OK | 2026-10-22 | baixado à mão (~8 MB); ainda fora do `testar_endpoints.py` |
| camara_proposicoes | Câmara | https://dadosabertos.camara.leg.br/api/v2/proposicoes?siglaTipo=PL&ano=2025&itens=1 | scripts/coletar.py | ✅ OK | 2026-10-21 | HTTP 200, application/json |
| camara_proposicao | Câmara | https://dadosabertos.camara.leg.br/api/v2/proposicoes/2270800 | scripts/coletar.py, scripts/coletar_executivo.py, site/assets/app.js | ✅ OK | 2026-10-21 | HTTP 200, application/json |
| camara_executivo | Câmara | https://dadosabertos.camara.leg.br/api/v2/proposicoes?autor=Poder%20Executivo&siglaTipo=PL&ano=2025&itens=1 | scripts/coletar_executivo.py | ✅ OK | 2026-10-21 | HTTP 200, application/json |
| camara_autores | Câmara | https://dadosabertos.camara.leg.br/api/v2/proposicoes/2270800/autores | scripts/coletar.py | ✅ OK | 2026-10-21 | HTTP 200, application/json |
| camara_tramitacoes | Câmara | https://dadosabertos.camara.leg.br/api/v2/proposicoes/2270800/tramitacoes | scripts/coletar_executivo.py | ✅ OK | 2026-10-21 | HTTP 200, application/json |
| camara_votacoes | Câmara | https://dadosabertos.camara.leg.br/api/v2/votacoes?dataInicio=2025-03-01&dataFim=2025-03-31&itens=1 | scripts/coletar.py | ✅ OK | 2026-10-21 | HTTP 200, application/json |
| camara_votacao | Câmara | https://dadosabertos.camara.leg.br/api/v2/votacoes/2442848-52 | scripts/coletar.py, site/assets/app.js | ✅ OK | 2026-10-21 | HTTP 200, application/json |
| camara_votos | Câmara | https://dadosabertos.camara.leg.br/api/v2/votacoes/2442848-52/votos | scripts/coletar.py, site/assets/app.js | ✅ OK | 2026-10-21 | HTTP 200, application/json |
| senado_lista | Senado | https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json | scripts/coletar.py | ✅ OK | 2026-10-21 | HTTP 200, application/json, 11 KB |
| senado_senador | Senado | https://legis.senado.leg.br/dadosabertos/senador/5012 | site/assets/app.js (link de fonte) | ✅ OK | 2026-10-21 | HTTP 200, application/xml, 1 KB |
| senado_votacoes | Senado | https://legis.senado.leg.br/dadosabertos/votacao?dataInicio=2025-03-01&dataFim=2025-03-31 | scripts/coletar.py, site/assets/app.js | ✅ OK | 2026-10-21 | HTTP 200, application/json, 5 KB |
| senado_processos | Senado | https://legis.senado.leg.br/dadosabertos/processo?codigoParlamentarAutor=5012 | scripts/coletar.py | ✅ OK | 2026-10-21 | HTTP 200, application/json, 400 KB |
| senado_processo | Senado | https://legis.senado.leg.br/dadosabertos/processo/1582415 | site/assets/app.js (link de fonte) | ✅ OK | 2026-10-21 | HTTP 200, application/json, 2 KB |
| senado_ceaps | Senado | https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/despesas_ceaps/2025 | scripts/coletar.py, site/assets/app.js | ✅ OK | 2026-10-21 | HTTP 200, application/json, 10.1 MB |
| senado_recursos | Senado | https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/5012/recursos-utilizados?ano=2025 | scripts/coletar.py, site/assets/app.js (link de fonte) | ❔ não testado | 2026-10-22 | HTTP 200, application/json |
| senado_escritorios | Senado | https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/escritorios-apoio | scripts/coletar.py, site/assets/app.js (link de fonte) | ❔ não testado | 2026-10-22 | HTTP 200, application/json, 27 KB |
| tse_consulta_cand | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2024.zip | scripts/coletar_tse.py | ✅ OK | 2026-10-21 | HTTP 200, application/zip, 63.9 MB |
| tse_bem_candidato | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/bem_candidato/bem_candidato_2024.zip | scripts/coletar_tse.py | ✅ OK | 2026-10-21 | HTTP 200, application/zip, 45.9 MB |
| tse_votacao_candidato_munzona | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_candidato_munzona/votacao_candidato_munzona_2024.zip | scripts/coletar_tse.py | ✅ OK | 2026-10-21 | HTTP 200, application/zip, 48.0 MB |
| tse_rede_social_candidato | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/rede_social_candidato_2024.zip | scripts/coletar_tse.py | ✅ OK | 2026-10-21 | HTTP 200, application/zip, 20.0 MB |
| tse_rede_social_candidato_2022_UF | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/rede_social_candidato_2022_DF.zip | scripts/coletar_tse.py | ✅ OK | 2026-10-21 | HTTP 200, application/zip, 188 KB |
| tse_prestacao_contas | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2024.zip | scripts/baixar_tse.py, scripts/coletar_contas.py | ✅ OK | 2026-10-21 | HTTP 200, application/zip, 1355.6 MB |
| tse_votacao_partido_munzona | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_partido_munzona/votacao_partido_munzona_2024.zip | scripts/baixar_tse.py, scripts/coletar_partidos.py | ✅ OK | 2026-10-21 | HTTP 200, application/zip, 6.1 MB |
| tse_votacao_secao | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_DF.zip | scripts/baixar_tse.py, scripts/coletar_secoes.py | ✅ OK | 2026-10-21 | HTTP 200, application/zip, 34.3 MB |
| tse_votacao_secao_2024 | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_DF.zip | scripts/baixar_tse.py, scripts/coletar_secoes.py | ❌ ERRO | 2026-10-21 | HTTP 404 |
| tse_perfil_eleitorado | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitorado/perfil_eleitorado_2024.zip | scripts/baixar_tse.py, scripts/coletar_eleitorado.py | ✅ OK | 2026-10-21 | HTTP 200, application/zip, 333.6 MB |
| tse_detalhe_votacao_munzona | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_munzona/detalhe_votacao_munzona_2024.zip | scripts/baixar_tse.py, scripts/coletar_disputa.py, scripts/gerar_municipios_ibge.py | ✅ OK | 2026-10-21 | HTTP 200, application/zip, 1.5 MB |
| tse_consulta_coligacao | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_coligacao/consulta_coligacao_2024.zip | scripts/baixar_tse.py, scripts/coletar_coligacoes.py | ✅ OK | 2026-10-21 | HTTP 200, application/zip, 11.0 MB |
| tse_consulta_vagas | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_vagas/consulta_vagas_2024.zip | scripts/baixar_tse.py, scripts/coletar_disputa.py | ✅ OK | 2026-10-21 | HTTP 200, application/zip, 564 KB |
| tse_eleitorado_locais_votacao | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/eleitorado_locais_votacao/eleitorado_local_votacao_2024.zip | scripts/baixar_tse.py, scripts/coletar_secoes.py | ✅ OK | 2026-10-21 | HTTP 200, application/zip, 45.3 MB |
| tse_motivo_cassacao | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/motivo_cassacao/motivo_cassacao_2024.zip | scripts/baixar_tse.py | ✅ OK | 2026-10-21 | HTTP 200, application/zip, 587 KB |
| tse_fotos | TSE | https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2022/fotos/foto_cand2022_DF_div.zip | scripts/coletar_tse.py | ✅ OK | 2026-10-21 | HTTP 200, application/zip, 25.4 MB |
| tse_fotos_2024 | TSE | https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2024/fotos/foto_cand2024_DF_div.zip | scripts/coletar_tse.py | ❌ ERRO | 2026-10-21 | HTTP 404 |
| tse_dados_abertos | TSE | https://dadosabertos.tse.jus.br | links de fonte (site e README) | ✅ OK | 2026-10-21 | HTTP 200, text/html, 15 KB |
| tse_divulgacandcontas | TSE | https://divulgacandcontas.tse.jus.br/divulga/ | site/assets/app.js (link) | ❌ ERRO | 2026-10-21 | HTTP 403 |
| ibge_municipios | IBGE | https://servicodados.ibge.gov.br/api/v1/localidades/municipios | scripts/gerar_municipios_ibge.py | ✅ OK | 2026-10-21 | HTTP 200, application/json |
| ibge_malha_estado | IBGE | https://servicodados.ibge.gov.br/api/v3/malhas/estados/53?formato=application/vnd.geo%2Bjson&intrarregiao=municipio&qualidade=minima | site/assets/app.js | ✅ OK | 2026-10-21 | HTTP 200, application/vnd.geo+json |
| ibge_malha_pais | IBGE | https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo%2Bjson&intrarregiao=UF&qualidade=minima | site/assets/app.js | ✅ OK | 2026-10-21 | HTTP 200, application/vnd.geo+json |
| df_geoserver_ras | DF | https://catalogo.ipe.df.gov.br/geoserver/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=geonode:regioes_administrativas&outputFormat=application/json&srsName=EPSG:4326&maxFeatures=1 | scripts/simplificar_df.py | ✅ OK | 2026-10-21 | HTTP 200, application/json |
| sapl_estadual_PB | SAPL (Assembleias) | https://sapl.al.pb.leg.br/api/parlamentares/legislatura/?page_size=1 | scripts/coletar_estaduais.py | ❌ ERRO | 2026-10-21 | ReadTimeout: HTTPSConnectionPool(host='sapl.al.pb.leg.br', port=443): Read timed out. (read timeout=60) |
| sapl_estadual_AM | SAPL (Assembleias) | https://sapl.al.am.leg.br/api/parlamentares/legislatura/?page_size=1 | scripts/coletar_estaduais.py | ✅ OK | 2026-10-21 | HTTP 200, application/json, 0 KB |
| sapl_estadual_AL | SAPL (Assembleias) | https://sapl.al.al.leg.br/api/parlamentares/legislatura/?page_size=1 | scripts/coletar_estaduais.py | ✅ OK | 2026-10-21 | HTTP 200, application/json, 0 KB |
| sapl_estadual_RO | SAPL (Assembleias) | https://sapl.al.ro.leg.br/api/parlamentares/legislatura/?page_size=1 | scripts/coletar_estaduais.py | ✅ OK | 2026-10-21 | HTTP 200, application/json, 0 KB |
| sapl_estadual_AC | SAPL (Assembleias) | https://sapl.al.ac.leg.br/api/parlamentares/legislatura/?page_size=1 | scripts/coletar_estaduais.py | ✅ OK | 2026-10-21 | HTTP 200, application/json, 0 KB |
| sapl_estadual_PI | SAPL (Assembleias) | https://sapl.al.pi.leg.br/api/parlamentares/legislatura/?page_size=1 | scripts/coletar_estaduais.py | ✅ OK | 2026-10-21 | HTTP 200, application/json, 0 KB |
| sapl_estadual_TO | SAPL (Assembleias) | https://sapl.al.to.leg.br/api/parlamentares/legislatura/?page_size=1 | scripts/coletar_estaduais.py | ✅ OK | 2026-10-21 | HTTP 200, application/json, 0 KB |
| sapl_materia_PB | SAPL (Assembleias) | https://sapl.al.pb.leg.br/api/materia/materialegislativa/?page_size=1&ano=2025 | scripts/coletar_estaduais.py, scripts/contrato_apis.py | ❌ ERRO | 2026-10-21 | ReadTimeout: HTTPSConnectionPool(host='sapl.al.pb.leg.br', port=443): Read timed out. (read timeout=60) |
| sapl_votoparlamentar_PB | SAPL (Assembleias) | https://sapl.al.pb.leg.br/api/sessao/votoparlamentar/?page_size=1 | scripts/coletar_estaduais.py, scripts/contrato_apis.py | ❌ ERRO | 2026-10-21 | ReadTimeout: HTTPSConnectionPool(host='sapl.al.pb.leg.br', port=443): Read timed out. (read timeout=60) |
| sapl_municipal_AC | SAPL (Câmaras municipais) | https://sapl.riobranco.ac.leg.br/api/base/autor/?page_size=1 | scripts/coletar_prefeituras.py | ✅ OK | 2026-10-21 | HTTP 200, application/json, 0 KB |
| sapl_municipal_RR | SAPL (Câmaras municipais) | https://sapl.boavista.rr.leg.br/api/base/autor/?page_size=1 | scripts/coletar_prefeituras.py | ✅ OK | 2026-10-21 | HTTP 200, application/json, 0 KB |
| sapl_municipal_RN | SAPL (Câmaras municipais) | https://sapl.natal.rn.leg.br/api/base/autor/?page_size=1 | scripts/coletar_prefeituras.py | ✅ OK | 2026-10-21 | HTTP 200, application/json, 0 KB |
| sapl_municipal_PB | SAPL (Câmaras municipais) | https://sapl.joaopessoa.pb.leg.br/api/base/autor/?page_size=1 | scripts/coletar_prefeituras.py | ✅ OK | 2026-10-21 | HTTP 200, application/json, 0 KB |
| splegis_promoventes | Câmara de São Paulo | https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx/PromoventesCMSPJSON | scripts/coletar_prefeitura_sp.py | ✅ OK | 2026-10-21 | HTTP 200, application/json, 11 KB |
| splegis_projetos | Câmara de São Paulo | https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx/ProjetosPorAnoJSON?Ano=2025 | scripts/coletar_prefeitura_sp.py | ✅ OK | 2026-10-21 | HTTP 200, application/json |
| splegis_consulta | Câmara de São Paulo | https://splegisconsulta.saopaulo.sp.leg.br | scripts/coletar_prefeitura_sp.py (link) | ✅ OK | 2026-10-21 | HTTP 200, text/html, 5 KB |
| go_suap | Câmara de Goiânia | https://suap.camaragyn.go.gov.br/camara/consulta_publica/?classificacao=PL&interessado=Prefeito&ano=2025&page=1 | scripts/coletar_prefeitura_go.py | ✅ OK | 2026-10-21 | HTTP 200, text/html, 4 KB; só com a cadeia extra de scripts/certs |
| ba_salvador | Câmara de Salvador | https://cmsalvador.sys.inf.br/cl/prop_interna/ | scripts/coletar_prefeitura_ba.py | ✅ OK | 2026-10-21 | HTTP 200, text/html, 44 KB |
| ba_salvador_tram | Câmara de Salvador | https://cmsalvador.sys.inf.br/cl/prop_interna_tram/ | scripts/coletar_prefeitura_ba.py | ✅ OK | 2026-10-21 | HTTP 200, text/html, 0 KB |
| camara_portal | Links e recursos do site | https://www.camara.leg.br/deputados/204379 | site/assets/app.js | ✅ OK | 2026-10-21 | HTTP 200, text/html |
| camara_ficha_tramitacao | Links e recursos do site | https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2270800 | site/assets/app.js | ✅ OK | 2026-10-21 | HTTP 200, text/html |
| camara_cota_limites | Links e recursos do site | https://www2.camara.leg.br/comunicacao/assessoria-de-imprensa/guia-para-jornalistas/cota-parlamentar | scripts/gerar.py, site/assets/app.js | ✅ OK | 2026-10-22 | HTTP 200, text/html |
| camara_decreto_legislativo_172 | Links e recursos do site | https://www2.camara.leg.br/legin/fed/decleg/2022/decretolegislativo-172-21-dezembro-2022-793529-republicacao-166629-pl.html | site/assets/app.js | ✅ OK | 2026-10-22 | HTTP 200, text/html |
| senado_materia_portal | Links e recursos do site | https://www25.senado.leg.br/web/atividade/materias/-/materia/99175 | site/assets/app.js | ✅ OK | 2026-10-21 | HTTP 200, text/html, 66 KB |
| senado_transparencia | Links e recursos do site | https://www12.senado.leg.br/transparencia/sen/5012 | site/assets/app.js | ❌ ERRO | 2026-10-21 | HTTP 404 |
| planalto_constituicao | Links e recursos do site | https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm | site/assets/app.js | ✅ OK | 2026-10-21 | HTTP 200, text/html, 1.8 MB |
| planalto_codigo_eleitoral | Links e recursos do site | https://www.planalto.gov.br/ccivil_03/leis/l4737compilado.htm | site/assets/app.js | ✅ OK | 2026-10-21 | HTTP 200, text/html, 436 KB |
| leaflet_js | Links e recursos do site | https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js | site/assets/app.js | ✅ OK | 2026-10-21 | HTTP 200, application/javascript, 41 KB |
| osm_tiles | Links e recursos do site | https://tile.openstreetmap.org/0/0/0.png | site/assets/app.js | ✅ OK | 2026-10-21 | HTTP 200, image/png, 6 KB |
| google_fonts | Links e recursos do site | https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible | site/*.html | ✅ OK | 2026-10-21 | HTTP 200, text/css |

## Observações sobre os erros

- **senado_transparencia**: o site monta o link em `www12.senado.leg.br/transparencia/sen/<id>` (404); o endereço que responde é `www6g.senado.leg.br/transparencia/sen/<id>`. Link quebrado em `site/assets/app.js`.
- **tse_votacao_secao_2024** e **tse_fotos_2024**: o TSE não publica esses arquivos para 2024 (só 2022); os coletores avisam e seguem.
- **tse_divulgacandcontas**: responde 403 a clientes automatizados; é só link para o navegador (pode funcionar para pessoas).
- **sapl_*_PB (Assembleia da Paraíba)**: o servidor não responde (timeout de 60 s).

