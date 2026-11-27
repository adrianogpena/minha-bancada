import datetime as dt
import json

import coletar_transferegov_especiais as tg


class Resp:
    def __init__(self, corpo):
        self.corpo = corpo

    def json(self):
        return self.corpo


def amostra():
    return json.loads(tg.AMOSTRA.read_text(encoding="utf-8"))["amostra"]


def test_amostra_real_vira_itens_compactos():
    a = amostra()
    planos = [tg.compactar_plano(p) for p in a["planos"]]
    assert all(planos) and all(len(p["emenda"]) == 12 and p["emenda"].isdigit() for p in planos)   # = codigoEmenda do Portal da Transparência
    assert all(isinstance(p["ano"], int) and p["beneficiario"] for p in planos)
    assert "nome_parlamentar_emenda_plano_acao" not in json.dumps(planos)   # o nome vive em dados/emendas, não aqui
    exs = [tg.compactar_executor(e) for e in a["executores"]]
    assert all(exs) and all(len(e["cnpj"]) == 14 and e["nome"] and e["plano"] for e in exs)
    bens = [tg.compactar_beneficiario(b) for b in a["beneficiarios"]]
    assert all(bens) and all(len(b["uf"]) == 2 and b["nome"] for b in bens)


def test_documento_invalido_ou_mascarado_vale_ausente():
    assert tg.cnpj("00000000000000") is None and tg.cnpj("***.123.456-**") is None and tg.cnpj(None) is None
    assert tg.cnpj("01.613.028/0001-67") == "01613028000167"
    assert "cnpj" not in tg.compactar_beneficiario({"id_beneficiario": 1, "nome_beneficiario": "X", "uf_beneficiario": "MG", "cnpj_beneficiario": "123"})


def test_sem_id_descarta():
    assert tg.compactar_plano({"codigo_plano_acao": "x"}) is None
    assert tg.compactar_executor({"id_executor": 1}) is None
    assert tg.compactar_beneficiario({"nome_beneficiario": "X"}) is None


def test_montar_junta_executores_ao_plano_por_ano_e_descarta_orfaos():
    planos = [{"id": 2, "ano": 2021}, {"id": 1, "ano": 2020}, {"id": 3, "ano": 2021}, {"id": 4}]
    execs = [{"id": 11, "plano": 1}, {"id": 10, "plano": 2}, {"id": 9, "plano": 2}, {"id": 99, "plano": 77}]
    assert tg.montar(planos, execs) == {
        2020: [{"id": 1, "ano": 2020, "executores": [{"id": 11}]}],
        2021: [{"id": 2, "ano": 2021, "executores": [{"id": 9}, {"id": 10}]}, {"id": 3, "ano": 2021}]}


def fake_get(paginas_por_recurso, atualizacao="2026-11-25T00:00:00", chamadas=None):
    def get(s, url, **k):
        if chamadas is not None:
            chamadas.append(url)
        if url.endswith("/data-atualizacao"):
            return Resp({"data_ultima_atualizacao": atualizacao})
        pg = paginas_por_recurso[url.rsplit("/", 1)[1]]
        i = k["params"]["pagina"]
        return Resp({"data": pg[i - 1], "total_pages": len(pg)})
    return get


def servidor():
    a = amostra()
    return {"planos-acao-especiais": [a["planos"][:2], a["planos"][2:]], "beneficiarios-especiais": [a["beneficiarios"]],
            "executores-especiais": [a["executores"]], "relatorios-gestao-novos-especiais": [a["relatorios"]],
            "relatorios-gestao-documento-liquidacao-especiais": [a["liquidacoes"]]}


def test_coleta_pagina_ate_total_e_grava_por_ano(monkeypatch, tmp_path):
    monkeypatch.setattr(tg, "DADOS", tmp_path)
    monkeypatch.setattr(tg.comum, "get", fake_get(servidor()))
    assert tg.coletar(hoje=dt.date(2026, 11, 27), s=object(), pausa=0)
    arquivos = {p.name for p in (tmp_path / "especiais").iterdir()}
    assert arquivos and all(n.endswith(".json") for n in arquivos)
    planos = [p for n in arquivos for p in json.loads((tmp_path / "especiais" / n).read_text(encoding="utf-8"))["planos"]]
    assert len(planos) == 3
    assert json.loads((tmp_path / "atualizacao.json").read_text(encoding="utf-8"))["atualizadoEm"] == "2026-11-25T00:00:00"
    assert json.loads((tmp_path / "beneficiarios.json").read_text(encoding="utf-8"))["itens"]


def test_api_sem_renovacao_nao_baixa_de_novo(monkeypatch, tmp_path):
    monkeypatch.setattr(tg, "DADOS", tmp_path)
    (tmp_path / "atualizacao.json").write_text(json.dumps({"atualizadoEm": "2026-11-25T00:00:00"}))
    chamadas = []
    monkeypatch.setattr(tg.comum, "get", fake_get(servidor(), chamadas=chamadas))
    assert not tg.coletar(hoje=dt.date(2026, 11, 27), s=object(), pausa=0)
    assert len(chamadas) == 1 and chamadas[0].endswith("/data-atualizacao")
    assert tg.coletar(forcar=True, hoje=dt.date(2026, 11, 27), s=object(), pausa=0)


def test_falha_no_meio_mantem_arquivos_anteriores(monkeypatch, tmp_path):
    monkeypatch.setattr(tg, "DADOS", tmp_path)
    (tmp_path / "atualizacao.json").write_text(json.dumps({"atualizadoEm": "antiga"}))
    base = fake_get(servidor())

    def get(s, url, **k):
        if "executores" in url:
            raise RuntimeError("caiu")
        return base(s, url, **k)

    monkeypatch.setattr(tg.comum, "get", get)
    assert not tg.coletar(hoje=dt.date(2026, 11, 27), s=object(), pausa=0)
    assert json.loads((tmp_path / "atualizacao.json").read_text())["atualizadoEm"] == "antiga"
    assert not (tmp_path / "especiais").exists()


def test_gravar_amostra_guarda_a_resposta_crua(monkeypatch, tmp_path):
    monkeypatch.setattr(tg, "AMOSTRA", tmp_path / "a.json")
    crua = {"planos-acao-especiais": [[{"id_plano_acao": n} for n in range(5)]], "beneficiarios-especiais": [[{"id_beneficiario": 1}]],
            "executores-especiais": [[{"id_executor": 1}]], "relatorios-gestao-novos-especiais": [[{"id_relatorio_gestao_novo": 1}]],
            "relatorios-gestao-documento-liquidacao-especiais": [[{"id_relatorio_gestao_dl": 1}]]}
    monkeypatch.setattr(tg.comum, "get", fake_get(crua))
    tg.gravar_amostra(dt.date(2026, 11, 27), object())
    d = json.loads((tmp_path / "a.json").read_text(encoding="utf-8"))
    assert d["capturadoEm"] == "2026-11-27" and len(d["amostra"]["planos"]) == 3


def test_amostra_real_de_relatorio_e_pagamento_vira_itens_compactos():
    a = amostra()
    rels = [tg.compactar_relatorio(r) for r in a["relatorios"]]
    assert all(rels) and all(r["plano"] and r["tipo"] and isinstance(r["executado"], float) for r in rels)
    pags = [tg.compactar_liquidacao(x) for x in a["liquidacoes"]]
    assert all(pags) and all(len(p["cnpj"]) == 14 and p["nome"] and p["valor"] > 0 and p["data"] for p in pags)
    assert all(p["natureza"] in ("custeio", "investimento") for p in pags)


def test_recebedor_pessoa_fisica_nao_guarda_nome_nem_documento():
    bruto = {"id_relatorio_gestao_dl": 5, "id_relatorio_gestao_novo": 9, "tp_doc_recebedor_relatorio_gestao_dl": "CPF",
             "tx_identificacao_recebedor_mascarado_relatorio_gestao_dl": "***944066**", "tx_nome_recebedor_relatorio_gestao_dl": "FULANO DE TAL",
             "vl_pagamento_relatorio_gestao_dl": 5599.09, "dt_pagamento_relatorio_gestao_dl": "2025-07-04", "tx_natureza_relatorio_gestao_dl": "CUSTEIO",
             "tx_descricao_relatorio_gestao_dl": "RPA - MAIO"}
    p = tg.compactar_liquidacao(bruto)
    assert p == {"id": 5, "relatorio": 9, "pf": True, "valor": 5599.09, "data": "2025-07-04", "natureza": "custeio"}
    assert "FULANO" not in json.dumps(p) and "944066" not in json.dumps(p)
    assert tg.compactar_liquidacao({"id_relatorio_gestao_dl": 1}) is None and tg.compactar_relatorio({"id_relatorio_gestao_novo": 1}) is None


def test_montar_gestao_agrupa_pelo_ano_do_plano_e_descarta_orfaos():
    planos = [{"id": 1, "ano": 2020}, {"id": 2, "ano": 2021}]
    rels = [{"id": 11, "plano": 1}, {"id": 12, "plano": 2}, {"id": 13, "plano": 99}]
    pags = [{"id": 7, "relatorio": 11}, {"id": 6, "relatorio": 11}, {"id": 8, "relatorio": 55}]
    assert tg.montar_gestao(rels, pags, planos) == {
        2020: [{"id": 11, "plano": 1, "pagamentos": [{"id": 6}, {"id": 7}]}], 2021: [{"id": 12, "plano": 2}]}


def test_coleta_grava_a_gestao_por_ano(monkeypatch, tmp_path):
    monkeypatch.setattr(tg, "DADOS", tmp_path)
    srv = servidor()
    planos = [tg.compactar_plano(p) for p in amostra()["planos"]]
    for r in srv["relatorios-gestao-novos-especiais"][0]:
        r["id_plano_acao"] = planos[0]["id"]   # a amostra de relatório é de outro plano: aponta para um da coleta
    for x in srv["relatorios-gestao-documento-liquidacao-especiais"][0]:
        x["id_relatorio_gestao_novo"] = srv["relatorios-gestao-novos-especiais"][0][0]["id_relatorio_gestao_novo"]
    monkeypatch.setattr(tg.comum, "get", fake_get(srv))
    assert tg.coletar(hoje=dt.date(2026, 11, 27), s=object(), pausa=0)
    arq = json.loads((tmp_path / "gestao" / f"{planos[0]['ano']}.json").read_text(encoding="utf-8"))
    assert arq["relatorios"] and any(r.get("pagamentos") for r in arq["relatorios"])
