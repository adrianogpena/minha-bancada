import json

import cadastro_proposicoes as cp


def prop(i, ano=2025, tipo="PL", ementa="Dispõe sobre algo."):
    return {"id": i, "siglaTipo": tipo, "numero": i % 100, "ano": ano, "ementa": ementa}


def test_ids_de_le_os_dois_formatos():
    assert cp.ids_de({"ate": "x", "ids": [3, 2]}) == [3, 2]
    assert cp.ids_de({"itens": [prop(5), prop(4)]}) == [5, 4]
    assert cp.ids_de({"itens": [7, 6]}) == [7, 6]
    assert cp.ids_de(None) == [] and cp.ids_de({}) == []
    assert [p["id"] for p in cp.itens_legados({"itens": [prop(5)]})] == [5]
    assert cp.itens_legados({"ids": [5]}) == []


def test_cadastro_grava_por_ano_e_recarrega(tmp_path):
    c = cp.Cadastro(tmp_path / "cad")
    c.registrar(prop(10, 2025, ementa="  Ementa A \n"))
    c.registrar(prop(11, 2026, "REQ", "B"))
    assert c.get(10) == {"id": 10, "siglaTipo": "PL", "numero": 10, "ano": 2025, "ementa": "Ementa A"}
    assert c.get(99) is None
    assert not (tmp_path / "cad").exists()                      # abaixo do limite: nada é gravado sozinho
    c.gravar()
    assert not (tmp_path / "cad").exists()
    c.gravar(forcar=True)
    assert sorted(p.name for p in (tmp_path / "cad").iterdir()) == ["2025.json", "2026.json"]
    assert json.loads((tmp_path / "cad" / "2025.json").read_text(encoding="utf-8")) == {"10": ["PL", 10, "Ementa A"]}
    outro = cp.Cadastro(tmp_path / "cad")
    assert outro.get(11)["siglaTipo"] == "REQ" and {p["id"] for p in outro.todos()} == {10, 11}


def test_registrar_igual_nao_suja_e_mudanca_de_ano_move(tmp_path):
    c = cp.Cadastro(tmp_path / "cad")
    c.registrar(prop(10, 2025))
    c.gravar(forcar=True)
    c.registrar(prop(10, 2025))
    assert not c.sujos and c.novas == 0
    c.registrar({**prop(10, 2025), "ementa": "outra"})
    assert c.sujos == {2025} and c.get(10)["ementa"] == "outra"
    c.gravar(forcar=True)
    c.registrar(prop(10, 2026, ementa="outra"))
    c.gravar(forcar=True)
    assert json.loads((tmp_path / "cad" / "2025.json").read_text(encoding="utf-8")) == {}
    assert cp.Cadastro(tmp_path / "cad").get(10)["ano"] == 2026


def test_grava_sozinho_ao_passar_do_limite(tmp_path, monkeypatch):
    monkeypatch.setattr(cp, "LIMITE_PARA_GRAVAR", 3)
    c = cp.Cadastro(tmp_path / "cad")
    for i in range(3):
        c.registrar(prop(i))
    c.gravar()
    assert (tmp_path / "cad" / "2025.json").exists() and c.novas == 0


def test_ler_anos_monta_objetos():
    assert cp.ler_anos({2025: {"7": ["PL", 7, "x"]}, None: {"8": ["REQ", 1, "y"]}}) == {
        7: {"id": 7, "siglaTipo": "PL", "numero": 7, "ano": 2025, "ementa": "x"},
        8: {"id": 8, "siglaTipo": "REQ", "numero": 1, "ano": None, "ementa": "y"}}
