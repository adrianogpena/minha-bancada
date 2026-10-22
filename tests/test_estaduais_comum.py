"""Helpers comuns dos coletores estaduais (scripts/estaduais_comum.py)."""
import pytest

import estaduais_comum as ec


@pytest.mark.parametrize("texto,esperado", [
    ("4.000,00", 4000.0), ("R$ 99,90", 99.9), ("31310.41", 31310.41), ("1.234.567", 1234567.0),
    ("-12,5", -12.5), (7, 7.0), ("", None), ("-", None), (None, None),
])
def test_valor_br(texto, esperado):
    assert ec.valor_br(texto) == esperado


@pytest.mark.parametrize("nome,esperado", [
    ("janeiro", 1), ("Março", 3), ("DEZEMBRO", 12), ("mar", 3), ("07", 7), ("13", None), ("xyz", None), ("", None),
])
def test_mes_numero(nome, esperado):
    assert ec.mes_numero(nome) == esperado


@pytest.mark.parametrize("nome,esperado", [
    ("DEP ANA SILVA", "ANA SILVA"), ("Dep. Ana Silva", "Ana Silva"), ("DEPUTADO(A)  Ana  Silva", "Ana Silva"),
    ("Deputada Ana", "Ana"), ("Depoimento Souza", "Depoimento Souza"),
])
def test_nome_limpo(nome, esperado):
    assert ec.nome_limpo(nome) == esperado


def test_sem_acento():
    assert ec.sem_acento("  JOSÉ  da Conceição ") == "jose da conceicao"


def test_ligar_nomes_por_nome_e_nome_civil_sem_ambiguidade():
    deps = [{"id": 1, "nome": "Zé Maria", "nomeCivil": "José Maria da Silva"},
            {"id": 2, "nome": "Ana Souza", "nomeCivil": None},
            {"id": 3, "nome": "Ana Souza", "nomeCivil": None},
            {"id": 4, "nome": "João", "nomeCivil": "João Pereira"}]
    r = ec.ligar_nomes(["DEP ZÉ MARIA", "José Maria da Silva", "Ana Souza", "Fulano", "joao pereira"], deps)
    assert r == {"DEP ZÉ MARIA": 1, "José Maria da Silva": 1, "joao pereira": 4}


def test_salvar_e_ler_ida_e_volta(tmp_path):
    arq = tmp_path / "a" / "x.json"
    ec.salvar(arq, {"b": "ç", "a": 1})
    assert arq.read_text(encoding="utf-8") == '{"a":1,"b":"ç"}'
    assert ec.ler(arq) == {"a": 1, "b": "ç"} and ec.ler(tmp_path / "nada.json", []) == []


def test_sessao_limita_conexoes_por_host():
    s = ec.sessao()
    a = s.get_adapter("https://exemplo.gov.br")
    assert a._pool_maxsize == 2 and "Mozilla" in s.headers["User-Agent"]
