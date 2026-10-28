import gerar_coautoria

TIPOS = {"PL"}


def dep(*ids_projetos):
    return {"proposicoes": [{"id": i, "tipo": t, "dataApresentacao": "2024-03-01"} for i, t in ids_projetos]}


def autoria(*ids):
    return {"autores": [[i, f"Dep {i}", "Deputado"] for i in ids]}


def construir(autorias, deputados=None, siglas=None):
    siglas = siglas or {"1": "AAA", "2": "AAA", "3": "BBB"}
    deputados = deputados or {i: dep((100, "PL"), (200, "PL"), (300, "REQ")) for i in siglas}
    return gerar_coautoria.construir(deputados, autorias, TIPOS, lambda i, dia: siglas.get(i))


def test_parceiros_e_partidos():
    por_dep, geral = construir({"100": autoria(1, 2), "200": autoria(1, 3), "300": autoria(1, 2)})
    assert por_dep["1"]["projetos"] == 2
    assert por_dep["1"]["parceiros"] == [["2", 1], ["3", 1]]
    assert por_dep["1"]["outroPartido"] == 1
    assert por_dep["2"]["outroPartido"] == 0
    assert geral["projetos"] == 2
    assert geral["pares"] == {"AAA|BBB": 1}
    assert {p["sigla"]: (p["projetos"], p["comOutros"]) for p in geral["partidos"]} == {"AAA": (2, 1), "BBB": (1, 1)}


def test_ignora_autor_sem_ficha_e_projeto_de_um_deputado_so():
    por_dep, geral = construir({"100": autoria(1, 99), "200": autoria(1)})
    assert por_dep == {}
    assert geral["projetos"] == 0


def test_assinatura_em_massa_nao_liga_todos_a_todos(monkeypatch):
    monkeypatch.setattr(gerar_coautoria, "MAX_AUTORES", 2)
    por_dep, geral = construir({"100": autoria(1, 2, 3)})
    assert por_dep == {}
    assert geral["ignorados"] == 1
