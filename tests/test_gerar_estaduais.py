import json

import gerar_estaduais as ge


def escrever(pasta, nome, obj):
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / nome).write_text(json.dumps(obj), encoding="utf-8")


def base(pasta, host="sapl.exemplo.leg.br", fonte_dep=None):
    dep = {"id": 1, "nome": "Ana", "nomeCivil": "Ana Silva", "foto": None, "email": None, "titular": True}
    if fonte_dep:
        dep["fonte"] = fonte_dep
    escrever(pasta, "deputados.json", {"host": host, "deputados": [dep]})
    escrever(pasta, "votacoes.json", {"votacoes": {}})
    escrever(pasta, "materias_2024.json", {"materias": {"9": {
        "idsDeputados": [1], "tipo": "PL", "tipoDescricao": "Projeto", "numero": 1, "ano": 2024,
        "dataApresentacao": "2024-02-01", "ementa": "x", "situacao": "Em tramitação"}}})


def preparar(tmp_path, monkeypatch):
    monkeypatch.setattr(ge, "BRUTO", tmp_path / "bruto")
    monkeypatch.setattr(ge, "SAIDA", tmp_path / "saida")
    return tmp_path / "bruto"


def test_uf_sapl_sem_arquivos_novos(tmp_path, monkeypatch):
    bruto = preparar(tmp_path, monkeypatch)
    pasta = bruto / "AC"
    base(pasta)
    ge.gerar_assembleia("AC", pasta)
    saida = json.loads((tmp_path / "saida" / "estadual" / "AC" / "1.json").read_text(encoding="utf-8"))
    assert set(saida) == {"id", "host", "foto", "email", "titular", "votos", "proposicoes"}
    assert saida["host"] == "sapl.exemplo.leg.br"
    assert "fonte" not in saida["proposicoes"][0]


def test_uf_com_todos_os_arquivos_novos(tmp_path, monkeypatch):
    bruto = preparar(tmp_path, monkeypatch)
    pasta = bruto / "GO"
    base(pasta, host=None, fonte_dep="https://dep/1")
    escrever(pasta, "verbas_2024.json", {"fonte": "https://verba", "itens": (
        [{"idDeputado": 1, "mes": 1, "categoria": "Combustível", "fornecedor": f"F{i}", "cnpj": f"{i}", "valor": 10 + i, "fonte": "u"} for i in range(12)]
        + [{"idDeputado": 1, "mes": 2, "categoria": "Aluguel", "fornecedor": "F0", "cnpj": "0", "valor": 5, "fonte": "u"}])})
    escrever(pasta, "verbas_2020.json", {"fonte": "https://verba", "itens": [{"idDeputado": 1, "mes": 1, "categoria": "Velho", "valor": 999}]})
    escrever(pasta, "remuneracao_2024.json", {"fonte": "https://rem", "itens": [
        {"idDeputado": 1, "mes": 1, "bruto": 100, "liquido": 80, "componentes": [], "fonte": "a"},
        {"idDeputado": 1, "mes": 3, "bruto": 120, "liquido": 90, "componentes": [], "fonte": "b"}]})
    escrever(pasta, "presenca.json", {"fonte": "https://pres", "itens": [
        {"idDeputado": 1, "periodo": "2024", "presente": 10, "ausente": 2, "licenca": 0, "totalSessoes": 12}]})
    escrever(pasta, "diarias_2024.json", {"fonte": "https://dia", "itens": [
        {"idDeputado": 1, "data": "2024-05-01", "valor": 100}, {"idDeputado": 1, "data": "2024-06-01", "valor": 50}]})
    escrever(pasta, "emendas_2024.json", {"fonte": "https://em", "itens": [
        {"idDeputado": 1, "ano": 2024, "empenhado": 1000, "pago": 400}, {"idDeputado": 1, "ano": 2024, "empenhado": 500, "pago": 100}]})
    ge.gerar_assembleia("GO", pasta)
    s = json.loads((tmp_path / "saida" / "estadual" / "GO" / "1.json").read_text(encoding="utf-8"))
    assert s["host"] is None and s["fonte"] == "https://dep/1"
    verba = s["verba"]
    assert verba["fonte"] == "https://verba"
    assert [a["ano"] for a in verba["anos"]] == [2024]
    a = verba["anos"][0]
    assert len(a["fornecedores"]) == 10 and a["fornecedores"][0]["fornecedor"] == "F11"
    assert a["categorias"][0]["id"] == "combustivel" and a["categorias"][0]["categoria"] == "Combustíveis e lubrificantes"
    assert a["categorias"][0]["originais"][0][0] == "Combustível" and a["categorias"][1]["id"] == "imovel"
    assert [m["mes"] for m in a["meses"]] == [1, 2]
    assert s["remuneracao"]["mes"] == 3 and s["remuneracao"]["bruto"] == 120
    assert s["presenca"]["periodos"][0]["presente"] == 10
    assert s["diarias"]["anos"] == [{"ano": 2024, "total": 150.0, "quantidade": 2}]
    assert s["emendas"]["anos"] == [{"ano": 2024, "empenhado": 1500.0, "pago": 500.0, "quantidade": 2}]
