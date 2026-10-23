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


def test_prazo_esgotado_interrompe_novas_requisicoes(monkeypatch):
    monkeypatch.setattr(ec, "PRAZO_FIM", None)
    ec.checar_prazo()  # sem prazo, nunca levanta
    monkeypatch.setattr(ec, "PRAZO_FIM", ec.time.monotonic() - 1)
    with pytest.raises(ec.PrazoEsgotado):
        ec.checar_prazo()
    with pytest.raises(ec.PrazoEsgotado):
        ec.sessao().get("https://exemplo.invalid/")


def test_sessao_tem_timeout_padrao(monkeypatch):
    monkeypatch.setattr(ec, "PRAZO_FIM", None)
    vistos = {}
    monkeypatch.setattr(ec.requests.Session, "request", lambda self, *a, **kw: vistos.update(kw))
    ec.sessao().get("https://exemplo.invalid/")
    assert vistos["timeout"] == (ec.TIMEOUT_CONEXAO, ec.TIMEOUT_PADRAO)
    ec.sessao().get("https://exemplo.invalid/", timeout=5)
    assert vistos["timeout"] == (5, 5)
    ec.sessao().get("https://exemplo.invalid/", timeout=(3, 90))
    assert vistos["timeout"] == (3, 90)


def test_host_sem_conexao_falha_na_hora_no_resto_da_coleta(monkeypatch):
    monkeypatch.setattr(ec, "PRAZO_FIM", None)
    chamadas = []

    def request(self, method, url, **kw):
        chamadas.append(url)
        if "fora" in url:
            raise ec.requests.ConnectTimeout("sem conexão")
        return "ok"
    monkeypatch.setattr(ec.requests.Session, "request", request)
    s = ec.sessao()
    for _ in range(2):
        with pytest.raises(ec.requests.ConnectTimeout):
            s.get("https://fora.gov.br/a")
    assert s.get("https://outro.gov.br/b") == "ok"
    assert chamadas == ["https://fora.gov.br/a", "https://outro.gov.br/b"]


def test_matriz_do_workflow_cobre_todas_as_ufs():
    """Cada UF nova (SAPL ou módulo coletar_estadual_<uf>.py) precisa entrar na matriz do job `estaduais` em atualizar.yml."""
    import re
    from conftest import RAIZ
    import coletar_estaduais
    texto = (RAIZ / ".github" / "workflows" / "atualizar.yml").read_text(encoding="utf-8")
    no_workflow = {u for ufs in re.findall(r'\{ id: \w+, ufs: "([A-Z ]+)"', texto) for u in ufs.split()}
    esperadas = set(coletar_estaduais.ASSEMBLEIAS) | set(coletar_estaduais.modulos_uf())
    assert no_workflow == esperadas


def test_meses_recentes_atravessa_o_ano():
    from datetime import date
    assert ec.meses_recentes(date(2026, 1, 10), 2) == {(2026, 1), (2025, 12)}
    assert ec.meses_recentes(date(2026, 5, 1), 3) == {(2026, 5), (2026, 4), (2026, 3)}


def test_ano_encerrado_so_com_arquivo_e_antes_do_ano_passado(tmp_path):
    from datetime import date
    hoje = date(2026, 10, 22)
    arq = tmp_path / "x.json"
    assert not ec.ano_encerrado(2024, hoje, arq)
    arq.write_text("{}")
    assert ec.ano_encerrado(2024, hoje, arq)
    assert not ec.ano_encerrado(2025, hoje, arq)
