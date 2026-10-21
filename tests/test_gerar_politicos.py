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
