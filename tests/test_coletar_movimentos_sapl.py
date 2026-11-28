import coletar_estaduais as c

STATUS = {1: "Despachada", 2: "."}
UNIDADES = {7: "Plenário"}


def tramitacao(i, data, status, texto, destino=7):
    return {"id": i, "data_tramitacao": data, "status": status, "texto": texto, "unidade_tramitacao_destino": destino,
            "unidade_tramitacao_local": None, "materia": 10}


def test_movimento_junta_status_texto_e_orgao():
    m = c.movimento(tramitacao(1, "2025-03-11", 1, "Lei nº 1"), STATUS, UNIDADES)
    assert m == {"data": "2025-03-11", "texto": "Despachada - Lei nº 1", "orgao": "Plenário"}
    assert c.movimento(tramitacao(2, "2025-03-11", 2, ""), STATUS, UNIDADES) is None


def test_coletar_movimentos_le_so_o_que_falta(monkeypatch):
    chamadas = []

    def get(host, caminho, **p):
        chamadas.append(p["materia"])
        return {"results": [tramitacao(2, "2025-04-01", 1, "b"), tramitacao(1, "2025-03-01", 1, "a")]}

    monkeypatch.setattr(c, "get", get)
    itens = {"10": {}, "11": {"movimentos": []}}
    antigo = {"coletadoEm": "2025-01-01", "vistas": {"11": "2025-01-01"}, "materias": {"11": {"movimentos": [{"data": "2025-01-01", "texto": "x"}]}}}
    monkeypatch.setattr(c, "paginar", lambda *a, **k: [])
    vistas = c.coletar_movimentos("h", "PB", itens, antigo, (STATUS, UNIDADES), "2025-01-01")
    assert chamadas == ["10"]
    assert [m["texto"] for m in itens["10"]["movimentos"]] == ["Despachada - a", "Despachada - b"]
    assert itens["11"]["movimentos"][0]["texto"] == "x"
    assert set(vistas) == {"10", "11"}
