import pytest

import gerar_politicos as g


def test_chave_nome_normaliza_acento_caixa_e_espacos():
    assert g.chave_nome("  JOSÉ   da Silva ", "sp") == "jose da silva|SP"
    assert g.chave_nome(None, None) == "|"


def test_rotulo_por_genero():
    assert g.rotulo("PREFEITO", "FEMININO") == ("Prefeita", 8)
    assert g.rotulo("PREFEITO", "MASCULINO") == ("Prefeito", 8)
    assert g.rotulo("PREFEITO", None) == ("Prefeito", 8)
    assert g.rotulo("DEPUTADO FEDERAL", "F") == ("Deputada federal", 4)


def test_rotulo_cargo_desconhecido():
    assert g.rotulo("CARGO NOVO", "M") == ("Cargo Novo", 99)


def test_periodo():
    assert g.periodo(2024, "VEREADOR") == ("2025-01-01", "2028-12-31")
    assert g.periodo(2022, "PRESIDENTE") == ("2023-01-01", "2027-01-04")
    assert g.periodo(1990, "VEREADOR") == (None, None)
    assert g.periodo(2024, "PRESIDENTE") == (None, None)


def test_mandatos_sao_consistentes():
    for ano, cargos in g.MANDATOS.items():
        for cargo, (ini, fim) in cargos.items():
            assert ini < fim, (ano, cargo)
            assert cargo in g.CARGOS, (ano, cargo)


def test_mandatos_nao_se_sobrepoem_para_o_mesmo_cargo_executivo():
    # titulares de 2022 acabam antes de os de 2026 começarem
    for cargo in ("PRESIDENTE", "GOVERNADOR"):
        assert g.periodo(2022, cargo)[1] < g.periodo(2026, cargo)[0]


def test_cargos_atuais_existem():
    for cargos in g.MANDATO_ATUAL.values():
        assert cargos <= set(g.CARGOS)
    assert g.MUNICIPAIS <= set(g.CARGOS)


def test_perfil_eleitos_usa_as_mesmas_posicoes_do_eleitorado():
    eleitos = [
        {"genero": "FEMININO", "nascimento": "1990-05-01", "instrucao": "Superior completo", "corRaca": "Parda", "ocupacao": "ADVOGADO"},
        {"genero": "MASCULINO", "nascimento": "1950-01-01", "instrucao": "Ensino médio incompleto", "corRaca": "Branca", "ocupacao": "Advogado"},
        {"genero": "MASCULINO", "nascimento": None, "instrucao": "Lê e escreve"},
    ]
    p = g.perfil_eleitos(eleitos, 2022)
    assert p["total"] == 3 and p["genero"] == [2, 1]
    assert p["faixas"] == [0, 0, 1, 0, 0, 0, 1, 0]
    assert p["instrucao"] == [0, 1, 0, 0, 1, 0, 0, 1]
    assert p["ocupacoes"] == [("Advogado", 2)] and dict(p["raca"]) == {"Parda": 1, "Branca": 1}


def test_nivel_instrucao():
    assert g.nivel_instrucao("Ensino fundamental completo") == 3
    assert g.nivel_instrucao("Superior incompleto") == 6
    assert g.nivel_instrucao("Não informado") is None


def test_custo_do_voto_e_patrimonio(tmp_path, monkeypatch):
    e = {"votos": [{"votos": 100}, {"votos": 50}]}
    assert g.custo_do_voto(e, {"receitas": 300.0}) == 2.0
    assert g.custo_do_voto(e, None) is None
    assert g.custo_do_voto({"votos": []}, {"receitas": 10.0}) is None
    monkeypatch.setattr(g, "BRUTO", tmp_path)
    monkeypatch.setattr(g, "_CUSTOS", {})
    for ano, cargo, total in ((2018, "SENADOR", 100.0), (2022, "DEPUTADO FEDERAL", 300.0)):
        (tmp_path / "tse" / str(ano)).mkdir(parents=True)
        (tmp_path / "tse" / str(ano) / "SP.json").write_text(
            '[{"nome": "José da Silva", "nascimento": "1970-01-01", "cargo": "%s", "totalBens": %s, "uf": "SP"},'
            '{"nome": "José da Silva", "nascimento": "1980-01-01", "cargo": "%s", "totalBens": 1.0, "uf": "SP"}]' % (cargo, total, cargo), encoding="utf-8")
    atual = {"nome": "JOSE DA SILVA", "nascimento": "1970-01-01"}
    assert g.patrimonio_de(atual) == [[2018, "SENADOR", 100.0], [2022, "DEPUTADO FEDERAL", 300.0]]
    assert g.patrimonio_de({"nome": "Outra", "nascimento": "1970-01-01"}) is None
