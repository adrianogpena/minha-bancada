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


def test_emendas_trazem_pagamentos_ligados_pelo_numero(tmp_path, monkeypatch):
    bruto = preparar(tmp_path, monkeypatch)
    pasta = bruto / "BA"
    base(pasta, host=None)
    escrever(pasta, "emendas_2025.json", {"fonte": "https://em", "itens": [
        {"idDeputado": 1, "ano": 2025, "numero": "N1", "empenhado": 1000, "pago": 400}]})
    escrever(pasta, "pagamentos_2026.json", {"fonte": "https://em", "itens": [
        {"numero": "N1", "data": "2026-01-20", "credor": "A", "objeto": "o1", "valor": 10.5, "empenho": "E1", "efetivado": False},
        {"numero": "N1", "data": "2026-02-23", "credor": "B", "objeto": "o2", "valor": 20, "empenho": "E1", "efetivado": True},
        {"numero": "N9", "data": "2026-03-01", "credor": "C", "objeto": "o3", "valor": 1, "empenho": "E2", "efetivado": True}]})
    ge.gerar_assembleia("BA", pasta)
    s = json.loads((tmp_path / "saida" / "estadual" / "BA" / "1.json").read_text(encoding="utf-8"))
    assert [p["credor"] for p in s["emendas"]["pagamentos"]] == ["B", "A"]
    assert s["emendas"]["pagamentos"][0] == {"data": "2026-02-23", "credor": "B", "objeto": "o2", "valor": 20, "empenho": "E1", "efetivado": True}


def test_verba_de_ce_e_ms_traz_lancamentos_so_do_ano_atual(tmp_path, monkeypatch):
    bruto = preparar(tmp_path, monkeypatch)
    item = {"idDeputado": 1, "mes": 2, "categoria": "Combustível", "fornecedor": "F", "cnpj": "1", "valor": 10, "documento": "NF-1",
            "emissao": "2026-02-03", "fonte": "https://comprovante"}
    for uf in ("MS", "GO"):
        pasta = bruto / uf
        base(pasta, host=None)
        escrever(pasta, "verbas_2026.json", {"fonte": "https://verba", "itens": [item, {**item, "mes": 3, "documento": None, "emissao": None, "empenho": "2026NE1", "descricao": "d"}]})
        escrever(pasta, "verbas_2025.json", {"fonte": "https://verba", "itens": [item]})
        ge.gerar_assembleia(uf, pasta)
    ms = json.loads((tmp_path / "saida" / "estadual" / "MS" / "1.json").read_text(encoding="utf-8"))["verba"]["anos"]
    assert "lancamentos" not in ms[0] and len(ms[1]["lancamentos"]) == 2
    assert ms[1]["lancamentos"][0]["documento"] == "NF-1" and ms[1]["lancamentos"][0]["emissao"] == "2026-02-03"
    assert ms[1]["lancamentos"][1] == {"mes": 3, "categoria": "Combustível", "fornecedor": "F", "cnpj": "1", "valor": 10, "empenho": "2026NE1", "descricao": "d", "fonte": "https://comprovante"}
    go = json.loads((tmp_path / "saida" / "estadual" / "GO" / "1.json").read_text(encoding="utf-8"))["verba"]["anos"]
    assert all("lancamentos" not in a for a in go)
