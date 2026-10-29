# Endpoints usados

Lista de todos os endpoints externos que o projeto consulta (coletores em `scripts/` e navegador em `site/`).
As colunas **Status**, **Verificado em** e **Detalhe** são reescritas por `python scripts/testar_endpoints.py`;
o resto é editado à mão.

**Ao criar um endpoint novo, acrescente uma linha na tabela** (a URL de teste deve ser concreta e leve) e rode o script.
Um teste (`tests/test_endpoints_doc.py`) falha se um host usado no código não aparece aqui.

Status: ✅ OK · ❌ ERRO (resposta com falha ou fora do ar) · ❔ não testado.

| Nome | Grupo | URL de teste | Usado em | Status | Verificado em | Detalhe |
|---|---|---|---|---|---|---|
| camara_deputados | Câmara | https://dadosabertos.camara.leg.br/api/v2/deputados?itens=1 | scripts/coletar.py, site/assets/app.js, scripts/coletar_ministros.py | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_deputado | Câmara | https://dadosabertos.camara.leg.br/api/v2/deputados/204379 | scripts/coletar.py, site/assets/app.js | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_despesas | Câmara | https://dadosabertos.camara.leg.br/api/v2/deputados/204379/despesas?ano=2025&itens=1 | scripts/coletar.py, site/assets/app.js | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_cota_csv | Câmara | https://www.camara.leg.br/cotas/Ano-2026.csv.zip | scripts/coletar.py | ✅ OK | 2026-10-24 | HTTP 200, application/zip, 4.4 MB |
| camara_frentes_deputado | Câmara | https://dadosabertos.camara.leg.br/api/v2/deputados/204379/frentes | scripts/coletar.py, site/assets/app.js | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_profissoes | Câmara | https://dadosabertos.camara.leg.br/api/v2/deputados/204379/profissoes | scripts/coletar.py, site/assets/js/deputado.js (link de fonte) | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_ocupacoes | Câmara | https://dadosabertos.camara.leg.br/api/v2/deputados/204379/ocupacoes | scripts/coletar.py, site/assets/js/deputado.js (link de fonte) | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_mandatos_externos | Câmara | https://dadosabertos.camara.leg.br/api/v2/deputados/204379/mandatosExternos | scripts/coletar.py, site/assets/js/deputado.js (link de fonte) | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_historico | Câmara | https://dadosabertos.camara.leg.br/api/v2/deputados/204379/historico | scripts/coletar.py, site/assets/js/deputado.js (link de fonte), scripts/coletar_ministros.py | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_discursos | Câmara | https://dadosabertos.camara.leg.br/api/v2/deputados/204379/discursos?itens=2&ordem=DESC&ordenarPor=dataHoraInicio&dataInicio=2023-02-01 | scripts/coletar.py, site/assets/js/deputado.js (link de fonte) | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_eventos | Câmara | https://dadosabertos.camara.leg.br/api/v2/deputados/204379/eventos?itens=2&ordem=DESC&ordenarPor=dataHoraInicio&dataInicio=2023-02-01 | scripts/coletar.py, site/assets/js/deputado.js (link de fonte) | ✅ OK | 2026-10-29 | HTTP 200, application/json |
| camara_arquivo_temas | Câmara | https://dadosabertos.camara.leg.br/arquivos/proposicoesTemas/json/proposicoesTemas-2025.json | scripts/coletar.py, site/assets/app.js | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_arquivo_orgaos | Câmara | https://dadosabertos.camara.leg.br/arquivos/orgaosDeputados/json/orgaosDeputados-L57.json | scripts/coletar.py | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_arquivo_orientacoes | Câmara | https://dadosabertos.camara.leg.br/arquivos/votacoesOrientacoes/json/votacoesOrientacoes-2026.json | scripts/coletar.py, site/assets/app.js | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_blocos | Câmara | https://dadosabertos.camara.leg.br/api/v2/blocos?idLegislatura=57&itens=100 | scripts/coletar.py | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_arquivo_votacoes_proposicoes | Câmara | https://dadosabertos.camara.leg.br/arquivos/votacoesProposicoes/json/votacoesProposicoes-2025.json | scripts/coletar.py, site/assets/app.js (link de fonte) | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_arquivo_eventos | Câmara | https://dadosabertos.camara.leg.br/arquivos/eventos/json/eventos-2026.json | scripts/coletar.py, site/assets/app.js (link de fonte) | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_arquivo_presenca | Câmara | https://dadosabertos.camara.leg.br/arquivos/eventosPresencaDeputados/json/eventosPresencaDeputados-2026.json | scripts/coletar.py, site/assets/app.js (link de fonte) | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_proposicoes | Câmara | https://dadosabertos.camara.leg.br/api/v2/proposicoes?siglaTipo=PL&ano=2025&itens=1 | scripts/coletar.py | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_proposicao | Câmara | https://dadosabertos.camara.leg.br/api/v2/proposicoes/2270800 | scripts/coletar.py, scripts/coletar_executivo.py, site/assets/app.js | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_executivo | Câmara | https://dadosabertos.camara.leg.br/api/v2/proposicoes?autor=Poder%20Executivo&siglaTipo=PL&ano=2025&itens=1 | scripts/coletar_executivo.py | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_autores | Câmara | https://dadosabertos.camara.leg.br/api/v2/proposicoes/2270800/autores | scripts/coletar.py | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_tramitacoes | Câmara | https://dadosabertos.camara.leg.br/api/v2/proposicoes/2270800/tramitacoes | scripts/coletar.py, scripts/coletar_executivo.py, scripts/coletar_ministros.py | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_relacionadas | Câmara | https://dadosabertos.camara.leg.br/api/v2/proposicoes/2270800/relacionadas | scripts/coletar.py | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_votacoes | Câmara | https://dadosabertos.camara.leg.br/api/v2/votacoes?dataInicio=2025-03-01&dataFim=2025-03-31&itens=1 | scripts/coletar.py | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_votacao | Câmara | https://dadosabertos.camara.leg.br/api/v2/votacoes/2442848-52 | scripts/coletar.py, site/assets/app.js | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_votos | Câmara | https://dadosabertos.camara.leg.br/api/v2/votacoes/2442848-52/votos | scripts/coletar.py, site/assets/app.js | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| camara_arquivo_proposicoes | Câmara | https://dadosabertos.camara.leg.br/arquivos/proposicoes/json/proposicoes-2026.json | scripts/coletar_ministros.py | ❔ | — | — |
| camara_arquivo_autores | Câmara | https://dadosabertos.camara.leg.br/arquivos/proposicoesAutores/json/proposicoesAutores-2026.json | scripts/coletar_ministros.py | ❔ | — | — |
| senado_lista | Senado | https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json | scripts/coletar.py, scripts/coletar_ministros.py | ✅ OK | 2026-10-24 | HTTP 200, application/json, 11 KB |
| senado_senador | Senado | https://legis.senado.leg.br/dadosabertos/senador/5012 | site/assets/app.js (link de fonte) | ✅ OK | 2026-10-24 | HTTP 200, application/xml, 1 KB |
| senado_comissoes | Senado | https://legis.senado.leg.br/dadosabertos/senador/5012/comissoes.json | scripts/coletar.py, site/assets/js/senador.js (link de fonte) | ✅ OK | 2026-10-24 | HTTP 200, application/json, 5 KB |
| senado_mandatos | Senado | https://legis.senado.leg.br/dadosabertos/senador/5012/mandatos.json | scripts/coletar.py, site/assets/js/senador.js (link de fonte) | ✅ OK | 2026-10-24 | HTTP 200, application/json, 0 KB |
| senado_votacoes | Senado | https://legis.senado.leg.br/dadosabertos/votacao?dataInicio=2025-03-01&dataFim=2025-03-31 | scripts/coletar.py, site/assets/app.js | ✅ OK | 2026-10-24 | HTTP 200, application/json, 5 KB |
| senado_processos | Senado | https://legis.senado.leg.br/dadosabertos/processo?codigoParlamentarAutor=5012 | scripts/coletar.py | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| senado_processo | Senado | https://legis.senado.leg.br/dadosabertos/processo/1582415 | site/assets/app.js (link de fonte) | ✅ OK | 2026-10-24 | HTTP 200, application/json, 2 KB |
| senado_afastados | Senado | https://legis.senado.leg.br/dadosabertos/senador/lista/afastados.json | scripts/coletar_ministros.py | ❔ | — | — |
| senado_requerimentos | Senado | https://legis.senado.leg.br/dadosabertos/processo?sigla=RQS&ano=2026 | scripts/coletar_ministros.py | ❔ | — | — |
| camara_portal_pessoal | Câmara | https://www.camara.leg.br/deputados/204379/pessoal-gabinete | scripts/coletar.py (raspagem da contagem de pessoal por grupo funcional), site/assets/js/deputado.js (link de fonte) | ❔ | — | — |
| camara_portal_verba_ano | Câmara | https://www.camara.leg.br/deputados/204379/verba-gabinete?ano=2025 | scripts/coletar.py (raspagem da verba de gabinete mês a mês), site/assets/js/deputado.js (link de fonte) | ❔ | — | — |
| camara_portal_presenca | Câmara | https://www.camara.leg.br/deputados/204379/presenca-plenario/2025 | scripts/coletar.py (raspagem da ausências justificadas e não justificadas), site/assets/js/deputado.js (link de fonte) | ❔ | — | — |
| camara_portal_recursos | Câmara | https://www.camara.leg.br/deputados/204379 | scripts/coletar.py (raspagem do bloco "Recursos" e da verba de gabinete), site/assets/js/deputado.js (link de fonte) | ❔ | — | — |
| planalto_ministros | Planalto | https://www.gov.br/planalto/pt-br/conheca-a-presidencia/ministros-e-ministras | scripts/coletar_ministros.py | ❔ | — | — |
| wikipedia_ministros | Wikipédia | https://pt.wikipedia.org/wiki/Gabinete_do_Brasil | scripts/ministros_posse.json (posse e presidente que nomeou, anotados à mão; sem coletor), site/assets/js/ministros.js (link de fonte), site/sobre.html | ❔ | — | — |
| senado_ceaps | Senado | https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/despesas_ceaps/2025 | scripts/coletar.py, site/assets/app.js | ✅ OK | 2026-10-24 | HTTP 200, application/json, 10.1 MB |
| senado_recursos | Senado | https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/5012/recursos-utilizados?ano=2025 | scripts/coletar.py, site/assets/app.js (link de fonte) | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| senado_escritorios | Senado | https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/escritorios-apoio | scripts/coletar.py, site/assets/app.js (link de fonte) | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| tcu_inabilitados | TCU | https://contas.tcu.gov.br/ords/condenacao/consulta/inabilitados | scripts/coletar_tcu.py | ❔ | — | — |
| tcu_inidoneos | TCU | https://contas.tcu.gov.br/ords/condenacao/consulta/inidoneos | scripts/coletar_tcu.py | ❔ | — | — |
| senado_aposentados | Senado | https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/aposentados | scripts/coletar.py, site/assets/js/senador.js (link de fonte) | ✅ OK | 2026-10-29 | HTTP 200, application/json |
| tse_consulta_cand | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2024.zip | scripts/coletar_tse.py | ✅ OK | 2026-10-24 | HTTP 200, application/zip, 63.9 MB |
| tse_bem_candidato | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/bem_candidato/bem_candidato_2024.zip | scripts/coletar_tse.py | ✅ OK | 2026-10-24 | HTTP 200, application/zip, 44.2 MB |
| tse_votacao_candidato_munzona | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_candidato_munzona/votacao_candidato_munzona_2024.zip | scripts/coletar_tse.py | ✅ OK | 2026-10-24 | HTTP 200, application/zip, 48.2 MB |
| tse_rede_social_candidato | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/rede_social_candidato_2024.zip | scripts/coletar_tse.py | ✅ OK | 2026-10-24 | HTTP 200, application/zip, 20.0 MB |
| tse_rede_social_candidato_2022_UF | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/rede_social_candidato_2022_DF.zip | scripts/coletar_tse.py | ✅ OK | 2026-10-24 | HTTP 200, application/zip, 188 KB |
| tse_prestacao_contas | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2024.zip | scripts/baixar_tse.py, scripts/coletar_contas.py | ✅ OK | 2026-10-24 | HTTP 200, application/zip, 1348.3 MB |
| tse_votacao_partido_munzona | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_partido_munzona/votacao_partido_munzona_2024.zip | scripts/baixar_tse.py, scripts/coletar_partidos.py | ✅ OK | 2026-10-24 | HTTP 200, application/zip, 6.1 MB |
| tse_votacao_secao | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_DF.zip | scripts/baixar_tse.py, scripts/coletar_secoes.py | ✅ OK | 2026-10-24 | HTTP 200, application/zip, 34.3 MB |
| tse_votacao_secao_2024 | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2024_AC.zip | scripts/baixar_tse.py, scripts/coletar_secoes.py | ✅ OK | 2026-10-24 | HTTP 200, application/zip, 5.6 MB |
| tse_perfil_eleitorado | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitorado/perfil_eleitorado_2024.zip | scripts/baixar_tse.py, scripts/coletar_eleitorado.py | ✅ OK | 2026-10-24 | HTTP 200, application/zip, 333.6 MB |
| tse_detalhe_votacao_munzona | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_munzona/detalhe_votacao_munzona_2024.zip | scripts/baixar_tse.py, scripts/coletar_disputa.py, scripts/gerar_municipios_ibge.py | ✅ OK | 2026-10-24 | HTTP 200, application/zip, 1.5 MB |
| tse_consulta_coligacao | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_coligacao/consulta_coligacao_2024.zip | scripts/baixar_tse.py, scripts/coletar_coligacoes.py | ✅ OK | 2026-10-24 | HTTP 200, application/zip, 11.0 MB |
| tse_consulta_vagas | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_vagas/consulta_vagas_2024.zip | scripts/baixar_tse.py, scripts/coletar_disputa.py | ✅ OK | 2026-10-24 | HTTP 200, application/zip, 564 KB |
| tse_eleitorado_locais_votacao | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/eleitorado_locais_votacao/eleitorado_local_votacao_2024.zip | scripts/baixar_tse.py, scripts/coletar_secoes.py | ✅ OK | 2026-10-24 | HTTP 200, application/zip, 45.3 MB |
| tse_motivo_cassacao | TSE | https://cdn.tse.jus.br/estatistica/sead/odsele/motivo_cassacao/motivo_cassacao_2024.zip | scripts/baixar_tse.py | ✅ OK | 2026-10-24 | HTTP 200, application/zip, 588 KB |
| tse_fotos | TSE | https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2022/fotos/foto_cand2022_DF_div.zip | scripts/coletar_tse.py | ✅ OK | 2026-10-24 | HTTP 200, application/zip, 25.4 MB |
| tse_fotos_2024 | TSE | https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2024/fotos/foto_cand2024_AC_div.zip | scripts/coletar_tse.py | ✅ OK | 2026-10-24 | HTTP 200, application/zip, 68.3 MB |
| tse_dados_abertos | TSE | https://dadosabertos.tse.jus.br | links de fonte (site e README) | ✅ OK | 2026-10-24 | HTTP 200, text/html, 15 KB |
| receita_cnpj | Receita Federal | https://YggdBLfdninEJX9:@arquivos.receitafederal.gov.br/public.php/webdav/2026-09/Cnaes.zip | scripts/coletar_receita.py, scripts/empresas.py | ✅ OK | 2026-10-24 | HTTP 200, application/zip, 21 KB |
| tse_divulgacandcontas | TSE | https://divulgacandcontas.tse.jus.br/divulga/ | site/assets/app.js (link) | ❌ ERRO | 2026-10-24 | HTTP 403 |
| ibge_municipios | IBGE | https://servicodados.ibge.gov.br/api/v1/localidades/municipios | scripts/gerar_municipios_ibge.py | ❌ ERRO | 2026-10-24 | ConnectTimeout: HTTPSConnectionPool(host='servicodados.ibge.gov.br', port=443): Max retries exceeded with url: /api/ |
| ibge_malha_estado | IBGE | https://servicodados.ibge.gov.br/api/v3/malhas/estados/53?formato=application/vnd.geo%2Bjson&intrarregiao=municipio&qualidade=minima | site/assets/app.js | ❌ ERRO | 2026-10-24 | ConnectTimeout: HTTPSConnectionPool(host='servicodados.ibge.gov.br', port=443): Max retries exceeded with url: /api/ |
| ibge_malha_pais | IBGE | https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo%2Bjson&intrarregiao=UF&qualidade=minima | site/assets/app.js | ❌ ERRO | 2026-10-24 | ConnectTimeout: HTTPSConnectionPool(host='servicodados.ibge.gov.br', port=443): Max retries exceeded with url: /api/ |
| siconfi_rgf | Tesouro (SICONFI) | https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rgf?an_exercicio=2025&in_periodicidade=Q&nr_periodo=3&co_tipo_demonstrativo=RGF&no_anexo=RGF-Anexo%2001&co_esfera=E&co_poder=L&id_ente=16&limit=1 | scripts/coletar_siconfi.py | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| siconfi_dca | Tesouro (SICONFI) | https://apidatalake.tesouro.gov.br/ords/siconfi/tt/dca?an_exercicio=2024&no_anexo=DCA-Anexo%20I-E&id_ente=35&limit=1 | scripts/coletar_siconfi.py | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| df_geoserver_ras | DF | https://catalogo.ipe.df.gov.br/geoserver/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=geonode:regioes_administrativas&outputFormat=application/json&srsName=EPSG:4326&maxFeatures=1 | scripts/simplificar_df.py | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| sapl_estadual_PB | SAPL (Assembleias) | https://sapl.al.pb.leg.br/api/parlamentares/legislatura/?page_size=1 | scripts/coletar_estaduais.py | ✅ OK | 2026-10-24 | HTTP 200, application/json, 0 KB |
| sapl_estadual_AM | SAPL (Assembleias) | https://sapl.al.am.leg.br/api/parlamentares/legislatura/?page_size=1 | scripts/coletar_estaduais.py | ✅ OK | 2026-10-24 | HTTP 200, application/json, 0 KB |
| sapl_estadual_AL | SAPL (Assembleias) | https://sapl.al.al.leg.br/api/parlamentares/legislatura/?page_size=1 | scripts/coletar_estaduais.py | ✅ OK | 2026-10-24 | HTTP 200, application/json, 0 KB |
| sapl_estadual_RO | SAPL (Assembleias) | https://sapl.al.ro.leg.br/api/parlamentares/legislatura/?page_size=1 | scripts/coletar_estaduais.py | ✅ OK | 2026-10-24 | HTTP 200, application/json, 0 KB |
| sapl_estadual_AC | SAPL (Assembleias) | https://sapl.al.ac.leg.br/api/parlamentares/legislatura/?page_size=1 | scripts/coletar_estaduais.py | ✅ OK | 2026-10-24 | HTTP 200, application/json, 0 KB |
| sapl_estadual_PI | SAPL (Assembleias) | https://sapl.al.pi.leg.br/api/parlamentares/legislatura/?page_size=1 | scripts/coletar_estaduais.py | ✅ OK | 2026-10-24 | HTTP 200, application/json, 0 KB |
| sapl_estadual_TO | SAPL (Assembleias) | https://sapl.al.to.leg.br/api/parlamentares/legislatura/?page_size=1 | scripts/coletar_estaduais.py | ✅ OK | 2026-10-24 | HTTP 200, application/json, 0 KB |
| sapl_materia_PB | SAPL (Assembleias) | https://sapl.al.pb.leg.br/api/materia/materialegislativa/?page_size=1&ano=2025 | scripts/coletar_estaduais.py, scripts/contrato_apis.py | ✅ OK | 2026-10-24 | HTTP 200, application/json, 1 KB |
| sapl_votoparlamentar_PB | SAPL (Assembleias) | https://sapl.al.pb.leg.br/api/sessao/votoparlamentar/?page_size=1 | scripts/coletar_estaduais.py, scripts/contrato_apis.py | ✅ OK | 2026-10-24 | HTTP 200, application/json, 0 KB |
| sapl_municipal_AC | SAPL (Câmaras municipais) | https://sapl.riobranco.ac.leg.br/api/base/autor/?page_size=1 | scripts/coletar_prefeituras.py | ✅ OK | 2026-10-24 | HTTP 200, application/json, 0 KB |
| sapl_municipal_RR | SAPL (Câmaras municipais) | https://sapl.boavista.rr.leg.br/api/base/autor/?page_size=1 | scripts/coletar_prefeituras.py | ✅ OK | 2026-10-24 | HTTP 200, application/json, 0 KB |
| sapl_municipal_RN | SAPL (Câmaras municipais) | https://sapl.natal.rn.leg.br/api/base/autor/?page_size=1 | scripts/coletar_prefeituras.py | ✅ OK | 2026-10-24 | HTTP 200, application/json, 0 KB |
| sapl_municipal_PB | SAPL (Câmaras municipais) | https://sapl.joaopessoa.pb.leg.br/api/base/autor/?page_size=1 | scripts/coletar_prefeituras.py | ✅ OK | 2026-10-24 | HTTP 200, application/json, 0 KB |
| splegis_promoventes | Câmara de São Paulo | https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx/PromoventesCMSPJSON | scripts/coletar_prefeitura_sp.py | ✅ OK | 2026-10-24 | HTTP 200, application/json, 11 KB |
| splegis_projetos | Câmara de São Paulo | https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx/ProjetosPorAnoJSON?Ano=2025 | scripts/coletar_prefeitura_sp.py | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| splegis_consulta | Câmara de São Paulo | https://splegisconsulta.saopaulo.sp.leg.br | scripts/coletar_prefeitura_sp.py (link) | ✅ OK | 2026-10-24 | HTTP 200, text/html, 5 KB |
| go_suap | Câmara de Goiânia | https://suap.camaragyn.go.gov.br/camara/consulta_publica/?classificacao=PL&interessado=Prefeito&ano=2025&page=1 | scripts/coletar_prefeitura_go.py | ✅ OK | 2026-10-24 | HTTP 200, text/html, 4 KB; só com a cadeia extra de scripts/certs |
| ba_salvador | Câmara de Salvador | https://cmsalvador.sys.inf.br/cl/prop_interna/ | scripts/coletar_prefeitura_ba.py | ✅ OK | 2026-10-24 | HTTP 200, text/html, 44 KB |
| ba_salvador_tram | Câmara de Salvador | https://cmsalvador.sys.inf.br/cl/prop_interna_tram/ | scripts/coletar_prefeitura_ba.py | ✅ OK | 2026-10-24 | HTTP 200, text/html, 0 KB |
| camara_portal | Links e recursos do site | https://www.camara.leg.br/deputados/204379 | site/assets/app.js | ✅ OK | 2026-10-24 | HTTP 200, text/html |
| camara_ficha_tramitacao | Links e recursos do site | https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2270800 | site/assets/app.js | ✅ OK | 2026-10-24 | HTTP 200, text/html |
| camara_cota_limites | Links e recursos do site | https://www2.camara.leg.br/comunicacao/assessoria-de-imprensa/guia-para-jornalistas/cota-parlamentar | scripts/gerar.py, site/assets/app.js | ✅ OK | 2026-10-24 | HTTP 200, text/html |
| camara_decreto_legislativo_172 | Links e recursos do site | https://www2.camara.leg.br/legin/fed/decleg/2022/decretolegislativo-172-21-dezembro-2022-793529-republicacao-166629-pl.html | site/assets/app.js | ✅ OK | 2026-10-24 | HTTP 200, text/html, 8 KB |
| senado_materia_portal | Links e recursos do site | https://www25.senado.leg.br/web/atividade/materias/-/materia/99175 | site/assets/app.js | ✅ OK | 2026-10-24 | HTTP 200, text/html |
| senado_transparencia | Links e recursos do site | https://www6g.senado.leg.br/transparencia/sen/5012 | site/assets/app.js | ✅ OK | 2026-10-24 | HTTP 200, text/html, 44 KB |
| planalto_constituicao | Links e recursos do site | https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm | site/assets/app.js | ✅ OK | 2026-10-24 | HTTP 200, text/html, 1.8 MB |
| planalto_codigo_eleitoral | Links e recursos do site | https://www.planalto.gov.br/ccivil_03/leis/l4737compilado.htm | site/assets/app.js | ✅ OK | 2026-10-24 | HTTP 200, text/html, 436 KB |
| leaflet_js | Links e recursos do site | https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js | site/assets/app.js | ✅ OK | 2026-10-24 | HTTP 200, application/javascript, 41 KB |
| osm_tiles | Links e recursos do site | https://tile.openstreetmap.org/0/0/0.png | site/assets/app.js | ✅ OK | 2026-10-24 | HTTP 200, image/png, 6 KB |
| google_fonts | Links e recursos do site | https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible | site/*.html | ✅ OK | 2026-10-24 | HTTP 200, text/css |
| rs_dados_diarias | Assembleias (estaduais) | https://dados.rs.gov.br/api/3/action/package_show?id=diarias-do-estado | scripts/coletar_estadual_rs.py | ❌ ERRO | 2026-10-24 | ReadTimeout: HTTPSConnectionPool(host='dados.rs.gov.br', port=443): Read timed out. (read timeout=60) |
| es_dados_despesas | Assembleias (estaduais) | https://dados.es.gov.br/api/3/action/package_show?id=portal-da-transparencia-despesas-execucao-orcamentaria-e-financeira | scripts/coletar_estadual_es.py | ✅ OK | 2026-10-24 | HTTP 200, application/json, 87 KB |
| rs_transparencia_diarias | Assembleias (estaduais) | https://www.transparencia.rs.gov.br/relatorios/externo/diarias-assembleia/dados/ | scripts/coletar_estadual_rs.py | ✅ OK | 2026-10-24 | HTTP 200, text/html |
| rn_api_transparencia | Assembleias (estaduais) | https://api-transparencialegislativa.al.rn.leg.br/elegis-api-transp-legislativa/parlamentar | scripts/coletar_estadual_rn.py | ✅ OK | 2026-10-24 | HTTP 200, application/json, 32 KB |
| rn_transparencia_verbas | Assembleias (estaduais) | https://transparencia.al.rn.leg.br/verbas | scripts/coletar_estadual_rn.py | ✅ OK | 2026-10-24 | HTTP 200, text/html |
| rn_transparencia_legislativa | Assembleias (estaduais) | https://transparencialegislativa.al.rn.leg.br | scripts/coletar_estadual_rn.py | ✅ OK | 2026-10-24 | HTTP 200, text/html |
| rr_deputados | Assembleias (estaduais) | https://al.rr.leg.br/deputados-estaduais-2023/ | scripts/coletar_estadual_rr.py | ✅ OK | 2026-10-24 | HTTP 200, text/html, 35 KB |
| rr_sapl | Assembleias (estaduais) | https://sapl.al.rr.leg.br | scripts/coletar_estadual_rr.py | ❌ ERRO | 2026-10-24 | HTTP 403 |
| rr_transparencia | Assembleias (estaduais) | https://transparencia.al.rr.leg.br | scripts/coletar_estadual_rr.py | ✅ OK | 2026-10-24 | HTTP 200, text/html |
| pa_alepa | Assembleias (estaduais) | https://alepa.pa.gov.br/Transparencia/FrequenciaSessoes | scripts/coletar_estadual_pa.py | ✅ OK | 2026-10-24 | HTTP 200, text/html, 124 KB |
| pa_sigep | Assembleias (estaduais) | https://sigep.alepa.pa.gov.br/transp/frame_verbagabinete.php | scripts/coletar_estadual_pa.py | ✅ OK | 2026-10-24 | HTTP 200, text/html, 6 KB |
| pa_quartertec | Assembleias (estaduais) | https://alepa.quartertec.com.br/api/dashboard/data?dashboardId=dashboard57&parameters=%5B%7B%22name%22%3A%22CPF_Deputados%22%2C%22value%22%3A%227BD68C11-DC21-4571-8EF6-AAB6E15355EF%22%2C%22type%22%3A%22System.String%22%2C%22allowMultiselect%22%3Atrue%2C%22selectAll%22%3Atrue%7D%5D&itemId=gridDashboardItem2&query=%7B%22Filter%22%3A%5B%7B%22dimensions%22%3A%5B%7B%22%40ItemType%22%3A%22Dimension%22%2C%22%40DataMember%22%3A%22Ano%22%2C%22%40DefaultId%22%3A%22DataItem0%22%2C%22NumericFormat%22%3A%7B%22%40FormatType%22%3A%22General%22%7D%2C%22%40SortOrder%22%3A%22Descending%22%7D%5D%2C%22values%22%3A%5B%5B2026%5D%5D%7D%5D%7D | scripts/coletar_estadual_pa.py | ✅ OK | 2026-10-24 | HTTP 200, application/json, 45 KB |
| se_deputados | Assembleias (estaduais) | https://al.se.leg.br/ | scripts/coletar_estadual_se.py | ✅ OK | 2026-10-24 | HTTP 200, text/html |
| se_legis | Assembleias (estaduais) | https://aleselegis.al.se.leg.br/spl/parlamentar.aspx | scripts/coletar_estadual_se.py | ❌ ERRO | 2026-10-24 | ConnectTimeout: HTTPSConnectionPool(host='aleselegis.al.se.leg.br', port=443): Max retries exceeded with url: /spl/p |
| ba_deputados | Assembleias (estaduais) | https://www.al.ba.gov.br/deputados/deputados-estaduais | scripts/coletar_estadual_ba.py | ✅ OK | 2026-10-24 | HTTP 200, text/html, 105 KB |
| ba_dados_emendas | Assembleias (estaduais) | https://dados.ba.gov.br/dataset/emendas-parlamentares | scripts/coletar_estadual_ba.py | ❌ ERRO | 2026-10-24 | SSLError: HTTPSConnectionPool(host='dados.ba.gov.br', port=443): Max retries exceeded with url: /dataset/emend |
| sc_portal_elegis | Assembleias (estaduais) | https://portalelegis.alesc.sc.gov.br | scripts/coletar_estadual_sc.py | ✅ OK | 2026-10-24 | HTTP 200, text/html |
| sc_transparencia | Assembleias (estaduais) | https://transparencia.alesc.sc.gov.br/deputados?ano=&mes= | scripts/coletar_estadual_sc.py | ✅ OK | 2026-10-24 | HTTP 200, text/html |
| ce_deputados | Assembleias (estaduais) | https://www.al.ce.gov.br/deputados | scripts/coletar_estadual_ce.py | ✅ OK | 2026-10-24 | HTTP 200, text/html, 20 KB |
| ce_proposicoes | Assembleias (estaduais) | https://www2.al.ce.gov.br/legislativo/proposicoes/numero.php | scripts/coletar_estadual_ce.py | ✅ OK | 2026-10-24 | HTTP 200, text/html, 0 KB |
| ce_transparencia | Assembleias (estaduais) | https://transparencia.al.ce.gov.br | scripts/coletar_estadual_ce.py | ✅ OK | 2026-10-24 | HTTP 200, text/html |
| ms_transparencia | Assembleias (estaduais) | https://transparencia2.al.ms.gov.br | scripts/coletar_estadual_ms.py | ✅ OK | 2026-10-24 | HTTP 200, text/html, 9 KB |
| pe_dadosabertos | Assembleias (estaduais) | https://dadosabertos.alepe.pe.gov.br/api/v1/parlamentares/ | scripts/coletar_estadual_pe.py | ✅ OK | 2026-10-24 | HTTP 200, application/json, 2 KB |
| pe_transparencia | Assembleias (estaduais) | https://transparencia.alepe.pe.gov.br/financas/verbas-indenizatorias | scripts/coletar_estadual_pe.py | ✅ OK | 2026-10-24 | HTTP 200, text/html, 0 KB |
| pe_legis | Assembleias (estaduais) | https://legis.alepe.pe.gov.br | scripts/coletar_estadual_pe.py | ✅ OK | 2026-10-24 | HTTP 200, text/html, 144 KB |
| pe_deputados | Assembleias (estaduais) | https://www.alepe.pe.gov.br/servicos/transparencia/dep/deputados.php?leg=-16 | scripts/coletar_estadual_pe.py | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| mt_site | Assembleias (estaduais) | https://www.al.mt.gov.br | scripts/coletar_estadual_mt.py | ❌ ERRO | 2026-10-24 | ConnectTimeout: HTTPSConnectionPool(host='www.al.mt.gov.br', port=443): Max retries exceeded with url: / (Caused by  |
| mt_eloweb | Assembleias (estaduais) | https://almt.eloweb.net/portaltransparencia/1/ | scripts/coletar_estadual_mt.py | ✅ OK | 2026-10-24 | HTTP 200, text/html |
| rj_transparencia | Assembleias (estaduais) | https://transparencia.alerj.rj.gov.br/section/report/121 | scripts/coletar_estadual_rj.py | ✅ OK | 2026-10-24 | HTTP 200, text/html |
| rj_ordemdia | Assembleias (estaduais) | https://alerjln1.alerj.rj.gov.br/ordemdia.nsf/presint?OpenForm | scripts/coletar_estadual_rj.py | ✅ OK | 2026-10-24 | HTTP 200, text/html |
| mg_site | Assembleias (estaduais) | https://www.almg.gov.br/transparencia/prestacao-de-contas/deputados/verba-indenizatoria/ | scripts/coletar_estadual_mg.py | ❌ ERRO | 2026-10-24 | ConnectTimeout: HTTPSConnectionPool(host='www.almg.gov.br', port=443): Max retries exceeded with url: /transparencia |
| mg_dadosabertos | Assembleias (estaduais) | https://dadosabertos.almg.gov.br/api/v2 | scripts/coletar_estadual_mg.py | ❌ ERRO | 2026-10-24 | ConnectTimeout: HTTPSConnectionPool(host='dadosabertos.almg.gov.br', port=443): Max retries exceeded with url: /api/ |
| go_portal | Assembleias (estaduais) | https://portal.al.go.leg.br/deputados/em-exercicio | scripts/coletar_estadual_go.py | ✅ OK | 2026-10-24 | HTTP 200, text/html |
| go_transparencia | Assembleias (estaduais) | https://transparencia.al.go.leg.br/api/transparencia/verbas_indenizatorias?ano=2026&mes=8 | scripts/coletar_estadual_go.py | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| pr_site | Assembleias (estaduais) | https://www.assembleia.pr.leg.br/deputados/conheca | scripts/coletar_estadual_pr.py | ✅ OK | 2026-10-24 | HTTP 200, text/html |
| pr_transparencia | Assembleias (estaduais) | https://transparencia.assembleia.pr.leg.br/api/remuneracao | scripts/coletar_estadual_pr.py | ❌ ERRO | 2026-10-24 | HTTP 403 |
| pr_webservices | Assembleias (estaduais) | https://webservices.assembleia.pr.leg.br/api/public/proposicao/filtrar | scripts/coletar_estadual_pr.py | ❌ ERRO | 2026-10-24 | SSLError: HTTPSConnectionPool(host='webservices.assembleia.pr.leg.br', port=443): Max retries exceeded with ur |
| pr_consultas | Assembleias (estaduais) | https://consultas.assembleia.pr.leg.br/#/pesquisa-legislativa | scripts/coletar_estadual_pr.py | ✅ OK | 2026-10-24 | HTTP 200, text/html, 1 KB |
| sp_dados_abertos | Assembleias (estaduais) | https://www.al.sp.gov.br/repositorioDados/deputados/deputados.xml | scripts/coletar_estadual_sp.py | ✅ OK | 2026-10-24 | HTTP 200, application/xml |
| sp_legis_api | Assembleias (estaduais) | https://legis-api-portal-prd.al.sp.gov.br/parlamentar-portal | scripts/coletar_estadual_sp.py | ✅ OK | 2026-10-24 | HTTP 200, application/json |
| sp_legis | Assembleias (estaduais) | https://www3.al.sp.gov.br/legis/ | scripts/coletar_estadual_sp.py | ✅ OK | 2026-10-24 | HTTP 200, text/html |

## Observações sobre os erros

- **senado_transparencia**: o link antigo `www12.senado.leg.br/transparencia/sen/<id>` dava 404; o site passou a usar `www6g.senado.leg.br/transparencia/sen/<id>` (`site/assets/js/senador.js`, `site/assets/js/comum.js`).
- **tse_votacao_secao_2024** e **tse_fotos_2024**: a sonda usa o AC; o DF não tem eleição municipal e dá 404 em 2024 (os arquivos existem para as demais UFs).
- **tse_divulgacandcontas**: responde 403 a clientes automatizados; é só link para o navegador (pode funcionar para pessoas).
- **sapl_*_PB (Assembleia da Paraíba)**: o servidor não responde (timeout de 60 s).
- **Assembleias estaduais bloqueadas ou fora do ar (2026-10-22)**: `www.al.ap.leg.br`, `www.cl.df.gov.br`, `www.al.es.gov.br` e `sistemas.al.ma.leg.br` dão timeout de qualquer ferramenta (sem coletor). `sapl.al.rr.leg.br` responde 403 a clientes automatizados; `albalegis.nopapercloud.com.br` (BA) dá 403 do Cloudflare; `sgpl.consulta.al.ms.gov.br` (MS) pede captcha; `api-transparencia.al.rn.leg.br` (RN) exige token Bearer; `consultas.assembleia.pr.leg.br` (PR) usa reCAPTCHA; `aleselegis.al.se.leg.br` e `www.al.mt.gov.br` não respondem. São só links de fonte ou hosts não coletados.

- **crt.sectigo.com (BA)**: o servidor de dados abertos da BA não envia o certificado intermediário (Sectigo OV R36); `coletar_estadual_ba.py` traz o arquivo `sectigo_ov_r36.pem`, baixado uma vez de `http://crt.sectigo.com/SectigoPublicServerAuthenticationCAOVR36.crt`. Não é consultado a cada coleta.
