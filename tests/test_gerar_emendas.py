import json

import gerar_emendas as ge


def item(codigo, ano, municipio, uf, empenhado, pago):
    return {"pessoa": "pes_a", "codigo": codigo, "ano": ano, "autor": "A", "tipo": "Individual", "local": f"{municipio} ({uf})", "municipio": municipio,
            "uf": uf, "empenhado": empenhado, "pago": pago}


def test_resume_por_ano_e_municipio_e_ordena_itens():
    r = ge.construir([item("1", 2023, "CAMPINAS", "SP", 100.0, 40.0), item("2", 2024, "CAMPINAS", "SP", 50.0, 50.0),
                      item("3", 2024, "SANTOS", "SP", 200.0, 0.0), {"pessoa": "pes_a", "codigo": "4", "ano": 2024, "autor": "A", "local": "CEARÁ", "empenhado": 1.0}])["pes_a"]
    assert [(a["ano"], a["n"], a["empenhado"], a["pago"]) for a in r["anos"]] == [(2024, 3, 251.0, 50.0), (2023, 1, 100.0, 40.0)]
    assert [(m["nome"], m["empenhado"], m["pago"], m["n"]) for m in r["municipios"]] == [("SANTOS", 200.0, 0.0, 1), ("CAMPINAS", 150.0, 90.0, 2)]
    assert [i["codigo"] for i in r["itens"]] == ["3", "2", "4", "1"]
    assert "pessoa" not in r["itens"][0] and "autor" not in r["itens"][0]


def test_salva_um_arquivo_por_pessoa(tmp_path):
    assert ge.salvar([item("1", 2024, "SANTOS", "SP", 1.0, 1.0)], tmp_path) == 1
    assert json.loads((tmp_path / "emendas" / "pes_a.json").read_text(encoding="utf-8"))["anos"][0]["ano"] == 2024
