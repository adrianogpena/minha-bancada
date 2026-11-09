import json

import pytest

import dados_minimos
import gerar_estaduais
import gerar_ministros
import gerar_politicos as g
import gerar_tribunais


def ler(caminho):
    return json.loads(caminho.read_text(encoding="utf-8"))


@pytest.fixture
def bruto(tmp_path, monkeypatch):
    pasta = tmp_path / "dados"
    monkeypatch.setattr(g, "BRUTO", pasta)
    monkeypatch.setattr(g, "SAIDA", tmp_path / "site")
    g._RESUMOS.clear()
    g._CUSTOS.clear()
    yield pasta
    g._RESUMOS.clear()
    g._CUSTOS.clear()


@pytest.fixture
def tse(bruto):
    dados_minimos.montar_bruto(bruto)
    dados_minimos.montar_tse_federal(bruto)
    return bruto


def eleito(seq, uf="SP", cargo="DEPUTADO FEDERAL", **extra):
    return {"sequencial": seq, "uf": uf, "cargo": cargo, "unidadeEleitoral": uf, "partido": "PT", **extra}


def test_medianas_do_custo_do_voto_por_cargo_e_partido(tse):
    m = g.medianas_custo_voto()
    assert m[(2022, "DEPUTADO FEDERAL")] == (35.0, 6)
    assert m[(2022, "DEPUTADO FEDERAL", "PT")] == (30.0, 5)
    assert (2022, "DEPUTADO FEDERAL", "PL") not in m
    assert (2022, "DEPUTADO ESTADUAL") not in m
    assert not any(k[1].startswith("VICE-") for k in m)
    assert g.medianas_custo_voto() is m


def test_contas_de_traz_custo_do_voto_com_medianas(tse):
    e = eleito("s3", partido="PT", votos=[{"turno": 1, "votos": 10}])
    contas = g.contas_de(2022, e)
    assert contas == {"receitas": 300.0, "origensReceita": [], "custoVoto": {"valor": 30.0, "cargo": {"mediana": 35.0, "n": 6}, "partido": {"mediana": 30.0, "n": 5}}}
    pl = g.contas_de(2022, eleito("s6", partido="PL", votos=[{"turno": 1, "votos": 10}]))
    assert pl["custoVoto"] == {"valor": 60.0, "cargo": {"mediana": 35.0, "n": 6}}


def test_contas_de_sem_custo_devolve_so_as_contas_ou_none(tse):
    assert g.contas_de(2022, eleito("s3")) == {"receitas": 300.0, "origensReceita": []}
    assert g.contas_de(2022, eleito("zzz")) is None


def test_contas_de_vice_usa_a_chapa_e_nao_compara(tse):
    vice = eleito("s8", cargo="VICE-GOVERNADOR", sequencialChapa="s9", votos=[{"turno": 1, "votos": 10}])
    assert g.contas_de(2022, vice) == {"receitas": 800.0, "origensReceita": [], "custoVoto": {"valor": 80.0}}


def test_secoes_disputa_partido_e_alianca_do_eleito(tse):
    e = eleito("s1")
    assert g.secoes_de(2022, e) == {"secoes": 12}
    assert g.secoes_de(2022, eleito("zzz")) is None
    assert g.disputa_de(2022, e) == {"vagas": 70}
    assert g.disputa_de(2022, eleito("s8", cargo="VICE-GOVERNADOR")) == {"vagas": 1}
    assert g.disputa_de(2022, eleito("s1", uf="RJ")) is None
    assert g.partido_de(2022, e) == {"votosLegenda": 10, "votosNominais": 500, "totalVotosPartidos": 1000, "federacao": "Fed X",
                                     "votosLegendaFederacao": 15, "votosNominaisFederacao": 550}
    assert g.partido_de(2022, eleito("s6", partido="PL")) == {"votosLegenda": 1, "votosNominais": 2, "totalVotosPartidos": 1000}
    assert g.partido_de(2022, eleito("s1", partido="NOVO")) is None
    assert g.partido_de(2022, eleito("s1", uf="RJ")) is None
    assert g.alianca_de(2022, e) == {"tipo": "F", "nome": "Fed X", "composicao": "PT/PC do B", "situacao": "Deferido"}
    assert g.alianca_de(2022, eleito("s6", partido="PL"))["tipo"] == "I"
    assert g.alianca_de(2022, eleito("s1", partido="NOVO")) is None
    assert g.alianca_de(2022, eleito("s1", uf="RJ")) is None


def test_eleitos_por_nome_indexa_nome_e_urna_e_filtra_cargo(tse):
    achados = g.eleitos_por_nome("DEPUTADO FEDERAL")
    assert achados["ana maria souza|SP"] == achados["ana souza|SP"]
    (bloco,) = achados["ana maria souza|SP"]
    assert (bloco["ano"], bloco["sequencial"], bloco["cargoTse"], bloco["uf"]) == (2022, "s1", "DEPUTADO FEDERAL", "SP")
    assert (bloco["inicioMandato"], bloco["fimMandato"]) == ("2023-02-01", "2027-01-31")
    assert bloco["contas"]["receitas"] == 100.0 and bloco["secoes"] == {"secoes": 12} and bloco["disputa"] == {"vagas": 70}
    assert bloco["partidoVotos"]["federacao"] == "Fed X" and bloco["alianca"]["tipo"] == "F"
    assert "ines estadual|SP" not in achados and "pres ident|BR" not in achados


def test_achar_eleicao_prefere_a_mais_recente_e_filtra_pelo_fim_do_mandato(tse):
    achados = g.eleitos_por_nome("SENADOR")
    assert sorted({b["ano"] for b in achados["bia lima|RJ"]}) == [2018, 2022]
    assert g.achar_eleicao(achados, ["Bia Lima"], "RJ")["ano"] == 2022
    assert g.achar_eleicao(achados, [None, "Bia Lima"], "RJ", "2027-01-31")["ano"] == 2018
    assert g.achar_eleicao(achados, ["Bia Lima"], "RJ", "2031-01-31")["ano"] == 2022
    assert g.achar_eleicao(achados, ["Bia Lima"], "RJ", "2035-01-31") is None
    assert g.achar_eleicao(achados, ["Outra Pessoa"], "RJ") is None
    assert g.achar_eleicao(achados, ["Bia Lima"], "SP") is None


def test_eleicao_deputados_liga_por_nome_civil_ou_nome_e_suplente_fica_none(tse):
    deputados = {"101": {"nome": "Ana Souza", "nomeCivil": "Ana Maria Souza", "uf": "SP"},
                 "102": {"nome": "Edu Cinco", "nomeCivil": None, "uf": "SP"},
                 "103": {"nome": "Suplente Que Assumiu", "nomeCivil": "Suplente Silva", "uf": "SP"}}
    r = g.eleicao_deputados(deputados)
    assert r["101"]["sequencial"] == "s1" and r["102"]["sequencial"] == "s5" and r["103"] is None


def test_perfil_das_casas_por_uf(tse):
    g.gerar_perfil_casas()
    assert not (g.SAIDA / "perfil_casas" / "BR.json").exists()
    sp = ler(g.SAIDA / "perfil_casas" / "SP.json")
    assert sp["federal"]["total"] == 6 and "composicao" not in sp["federal"]
    assert sp["estadual"]["total"] == 1
    assert sp["estadual"]["custo"] == {"ano": 2023, "despesaLiquidada": 2000.0, "cadeiras": 1, "porParlamentar": 2000.0, "fonte": "https://dca"}
    assert sp["senado"]["total"] == 0
    assert sp["municipal"]["71072"]["total"] == 2
    assert sp["municipal"]["71072"]["custo"] == {"ano": 2023, "despesaLiquidada": 500.0, "cadeiras": 2, "porParlamentar": 250.0, "fonte": "https://dca-mun"}
    rj = ler(g.SAIDA / "perfil_casas" / "RJ.json")
    assert rj["senado"]["total"] == 2 and rj["federal"]["total"] == 0 and "municipal" not in rj


def test_perfil_das_casas_usa_a_bancada_atual_quando_ha_deputados(tse):
    g.gerar_perfil_casas({"101": {"nome": "Ana Souza", "nomeCivil": "Ana Maria Souza", "uf": "SP"},
                          "102": {"nome": "Sem Registro", "nomeCivil": None, "uf": "SP"}})
    federal = ler(g.SAIDA / "perfil_casas" / "SP.json")["federal"]
    assert federal["total"] == 1 and federal["composicao"] == "atual" and federal["emExercicio"] == 2
    assert federal["ocupacoes"] == [["Advogado", 1]]


def test_relatorias_do_tcu_somam_por_ano_e_guardam_recentes(bruto):
    dados_minimos.montar_tribunais_e_ministros(bruto)
    anos, recentes, ultima = gerar_tribunais.relatorias_tcu(bruto)
    assert {r: dict(a) for r, a in anos.items()} == {"AROLDO CEDRAZ": {"2026": 4, "2025": 2}, "ANDRE SUBSTITUTO": {"2026": 1, "2024": 5}}
    assert recentes == {"AROLDO CEDRAZ": [{"numero": 1, "ano": 2026}]} and ultima == "2026-03-10"


def test_relatorias_do_tcu_sem_arquivo(tmp_path):
    anos, recentes, ultima = gerar_tribunais.relatorias_tcu(tmp_path)
    assert (dict(anos), recentes, ultima) == ({}, {}, None)


def test_relatorias_do_stj_somam_por_relator_e_ano(bruto):
    dados_minimos.montar_tribunais_e_ministros(bruto)
    anos = gerar_tribunais.relatorias_stj(bruto)
    assert {r: dict(a) for r, a in anos.items()} == {"HERMAN BENJAMIN": {"2025": 6, "2026": 1}, "FANTASMA": {"2020": 0}}


def test_relatorias_do_stj_sem_arquivo_ou_sem_contagem(tmp_path):
    assert dict(gerar_tribunais.relatorias_stj(tmp_path)) == {}
    dados_minimos.gravar(tmp_path / "tribunais" / "relatorias_stj.json", {"recursos": {"r": {}}})
    assert dict(gerar_tribunais.relatorias_stj(tmp_path)) == {}


def test_construir_tribunais_com_relatorias_do_tcu_e_do_stj(bruto):
    dados_minimos.montar_tribunais_e_ministros(bruto)
    um = gerar_tribunais.ministro("TCU", {"nome": "Aroldo Cedraz de Oliveira", "wiki": "Aroldo_Cedraz"}, {}, {})
    pessoas = {um["id"]: "pes_a"}
    por_sigla = {t["sigla"]: t for t in gerar_tribunais.construir(bruto, pessoas, {"pes_a": {"camara": 5, "senado": "7"}})}
    tcu, stj, stf = por_sigla["TCU"], por_sigla["STJ"], por_sigla["STF"]

    cedraz, dantas = tcu["ministros"]
    assert cedraz["pessoa"] == "pes_a" and cedraz["parlamentar"] == {"casa": "camara", "id": "5"} and cedraz["posse"] == "2007-01-01"
    assert cedraz["relatorias"] == {"2026": 4, "2025": 2} and cedraz["confirmado"] is True
    assert cedraz["recentes"] == [{"numero": 1, "ano": 2026}]
    assert "relatorias" not in dantas and dantas["confirmado"] is False and "pessoa" not in dantas
    assert tcu["outrosRelatores"] == [{"nome": "Andre Substituto", "relatorias": {"2026": 1, "2024": 5}, "ultimo": "2026"}]
    assert tcu["relatorias"]["ate"] == "2026-03-10" and tcu["relatorias"]["rotulo"].startswith("Acórdãos do TCU")
    assert tcu["coletadoEm"] == "2026-10-30"
    assert tcu["saidas"] == [{"id": tcu["saidas"][0]["id"], "nome": "Ex Ministro", "vistoDesde": "2026-01-01", "vistoAte": "2026-06-01"}]
    assert tcu["saidas"][0]["id"].startswith("mtr_")

    (herman,) = stj["ministros"]
    assert herman["relatorias"] == {"2026": 1, "2025": 6} and herman["confirmado"] is True
    assert stj["outrosRelatores"] == [] and stj["relatorias"]["rotulo"].startswith("Espelhos")
    assert "relatorias" not in stf and "outrosRelatores" not in stf and stf["saidas"] == []


def test_construir_tribunais_sem_coletadoEm_nao_confirma_ninguem(tmp_path):
    dados_minimos.gravar(tmp_path / "tribunais" / "tribunais.json", {"tribunais": {"STF": {
        "nome": "Supremo", "fonte": "f", "wikipedia": "w", "atuais": [{"nome": "Fulano de Tal"}]}}})
    (stf,) = gerar_tribunais.construir(tmp_path)
    assert stf["coletadoEm"] is None and stf["ministros"][0]["nome"] == "Fulano de Tal"


def test_juntar_relatorias_ignora_contagem_zero_e_anexa_recentes():
    ministros = [{"nome": "Herman Benjamin"}]
    fora = gerar_tribunais.juntar_relatorias("STJ", ministros, {"HERMAN BENJAMIN": {"2026": 2}, "FANTASMA": {"2020": 0}, "NOVO RELATOR": {"2026": 1}},
                                             {"NOVO RELATOR": [{"numero": 9}]}, 2026)
    assert fora == [{"nome": "Novo Relator", "relatorias": {"2026": 1}, "ultimo": "2026", "recentes": [{"numero": 9}]}]
    assert ministros[0]["relatorias"] == {"2026": 2}


def test_casar_relator_vazio_nao_casa():
    assert gerar_tribunais.casar_relator("", [{"nome": "Herman Benjamin"}]) is None


def test_salvar_tribunais_grava_e_resume(tmp_path, capsys):
    lista = [{"sigla": "A", "ministros": [{"pessoa": "p"}, {}]}, {"sigla": "B", "ministros": [{}]}]
    gerar_tribunais.salvar_tribunais(lista, tmp_path / "site")
    assert ler(tmp_path / "site" / "tribunais.json") == lista
    assert "Tribunais: 2 cortes, 3 ministros, 1 ligados a pessoas" in capsys.readouterr().out


def test_requerimentos_da_camara(bruto):
    dados_minimos.montar_tribunais_e_ministros(bruto)
    pedidos, nomes = gerar_ministros.requerimentos_da_camara(bruto)
    assert pedidos == [{"id": "camara-10", "fonte": "camara", "idFonte": "10", "tipo": "RIC", "numero": 1, "ano": 2026,
                        "ementa": "Requer informações ao Ministro de Estado da Saúde sobre vacinas.", "situacao": "Aguardando",
                        "resposta": "Respondido", "natureza": "informacao", "data": "2026-03-01", "autores": ["101", "999"]}]
    assert nomes == {"101": "Ana Souza", "999": "Antigo Deputado"}


def test_requerimentos_do_senado(bruto):
    dados_minimos.montar_tribunais_e_ministros(bruto)
    primeiro, segundo = gerar_ministros.requerimentos_do_senado(bruto)
    assert primeiro == {"id": "senado-20", "fonte": "senado", "idFonte": "20", "tipo": "RQS", "numero": 5, "ano": 2026,
                        "ementa": "Requer a convocação do Ministro de Estado da Saúde.", "tramitando": True, "natureza": "convocacao",
                        "data": "2026-03-02", "_autoria": "Senador Bia Lima (PL/RJ)"}
    assert (segundo["tipo"], segundo["numero"], segundo["ano"], segundo["_autoria"]) == ("RQS", None, None, None)


def test_requerimentos_sem_pasta_de_ministros(tmp_path):
    assert gerar_ministros.requerimentos_da_camara(tmp_path) == ([], {})
    assert gerar_ministros.requerimentos_do_senado(tmp_path) == []


def test_natureza_convite_com_convocacao_vira_convocacao():
    assert gerar_ministros.natureza("REQ", "Requer o convite e a convocação do Ministro") == "convocacao"


def nucleo_com_ministro():
    return {"ministros": [{"pessoa": "pes_1", "nome": "Fulano de Tal", "cargo": "Ministro de Estado da Saúde", "pasta": "saude", "inicio": "2026-01-01",
                           "inicioFonte": "licenca"}],
            "pessoas": [{"id": "pes_1", "fontes": {"camara": 101}, "ligacao": {"planalto": "u"}}], "ligacoes": {}}


def test_construir_ministros_liga_pedidos_a_pasta_ministro_e_senador(bruto):
    dados_minimos.montar_tribunais_e_ministros(bruto)
    nucleo = nucleo_com_ministro()
    senadores = [{"id": "7", "nome": "Bia Lima", "uf": "RJ"}]
    res = gerar_ministros.construir(bruto, nucleo, senadores, {"101": {}})

    assert res["total"] == 3 and res["autoresFora"] == {"999": "Antigo Deputado"}
    (saude,) = [m for m in res["ministerios"] if m["pasta"] == "saude"]
    assert saude["ministro"] == {"pessoa": "pes_1", "nome": "Fulano de Tal", "inicio": "2026-01-01"}
    assert (saude["total"], saude["informacao"], saude["convocacao"], saude["respondidos"]) == (2, 1, 1, 1)

    pasta = res["ministerio"]["saude"]
    assert [r["id"] for r in pasta["requerimentos"]] == ["senado-20", "camara-10"]
    assert pasta["descricao"]["resumo"] and pasta["ministros"][0]["atual"] is True
    assert pasta["ministros"][0]["requerimentos"] == ["camara-10", "senado-20"]
    assert pasta["requerimentos"][0]["autores"] == ["7"]

    ficha = res["ministro"]["pes_1"]
    assert ficha["parlamentar"] == {"casa": "camara", "id": "101"} and ficha["ligacao"] == "u"
    assert ficha["cargos"][0]["pasta"] == "saude" and ficha["cargos"][0]["nomePasta"]

    lig = nucleo["ligacoes"]["ministros"]
    assert lig["requerimentos"] == {"camara-10": ["pes_1", "pasta+data", "média"], "senado-20": ["pes_1", "pasta+data", "média"]}
    assert lig["autoriaSenado"] == {"Senador Bia Lima (PL/RJ)": [["7", "nome+uf", "média"]]}
    assert (lig["resumo"]["requerimentos"], lig["resumo"]["semPasta"], lig["resumo"]["comMinistro"]) == (3, 1, 2)
    assert res["indice"][0]["codigoFeed"] == "min:saude"


def test_salvar_ministros_grava_todos_os_arquivos(bruto, tmp_path, capsys):
    dados_minimos.montar_tribunais_e_ministros(bruto)
    res = gerar_ministros.construir(bruto, nucleo_com_ministro(), [])
    saida = tmp_path / "out"
    gerar_ministros.salvar_ministros(res, saida)
    assert ler(saida / "ministerios.json") == res["ministerios"]
    assert ler(saida / "ministros_autores.json") == {"101": "Ana Souza", "999": "Antigo Deputado"}
    assert ler(saida / "ministerio" / "saude.json")["pasta"] == "saude"
    assert ler(saida / "ministro" / "pes_1.json")["pessoa"] == "pes_1"
    assert "Ministros: 1 pessoas" in capsys.readouterr().out


def test_gerar_leis_ordena_normas_e_nao_grava_sem_normas(tmp_path, monkeypatch):
    monkeypatch.setattr(gerar_estaduais, "SAIDA", tmp_path / "site")
    pasta = tmp_path / "SP"
    dados_minimos.gravar(pasta / "leis_2025.json", {"fonte": "https://leis", "normas": {
        "a": {"ano": 2025, "numero": "9"}, "b": {"ano": 2025, "numero": "10"}, "c": {"ano": 2024, "numero": "x"}}})
    gerar_estaduais.gerar_leis("SP", pasta)
    arq = ler(tmp_path / "site" / "leis" / "SP.json")
    assert arq["fonte"] == "https://leis" and [n["id"] for n in arq["normas"]] == ["b", "a", "c"]
    gerar_estaduais.gerar_leis("RJ", tmp_path / "RJ")
    assert not (tmp_path / "site" / "leis" / "RJ.json").exists()


@pytest.fixture(scope="module")
def site_completo(tmp_path_factory):
    return dados_minimos.gerar_tudo_completo(tmp_path_factory.mktemp("completo"))


def test_integracao_tribunais_e_ministros_no_site(site_completo):
    tribunais = {t["sigla"]: t for t in ler(site_completo / "tribunais.json")}
    assert set(tribunais) == {"TCU", "STJ", "STF"} and tribunais["TCU"]["outrosRelatores"][0]["nome"] == "Andre Substituto"
    assert tribunais["STJ"]["ministros"][0]["relatorias"] == {"2026": 1, "2025": 6}
    assert (site_completo / "ministerios.json").is_file() and (site_completo / "ministerio" / "casa_civil.json").exists() is False
    assert ler(site_completo / "ministros_autores.json").get("999") == "Antigo Deputado"
    assert ler(site_completo / "nucleo" / "ligacoes.json")["ministros"]["resumo"]["requerimentos"] == 3


def test_integracao_eleicao_do_deputado_e_do_senador(site_completo):
    eleicao = ler(site_completo / "deputado" / "101.json")["eleicao"]
    assert eleicao["sequencial"] == "s1" and eleicao["contas"]["custoVoto"]["valor"] == 10.0
    assert eleicao["alianca"]["nome"] == "Fed X" and eleicao["secoes"] == {"secoes": 12}


def test_integracao_perfil_das_casas_e_ficha_do_tse(site_completo):
    sp = ler(site_completo / "perfil_casas" / "SP.json")
    assert sp["federal"]["composicao"] == "atual" and sp["estadual"]["custo"]["porParlamentar"] == 2000.0
    assert ler(site_completo / "perfil_casas" / "RJ.json")["senado"]["total"] == 2
    assert not (site_completo / "perfil_casas" / "BR.json").exists()
