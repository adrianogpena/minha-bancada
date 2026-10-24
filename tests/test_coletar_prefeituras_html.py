"""Coletores de Câmaras sem SAPL (SP: webservice JSON; BA e GO: HTML) e de governadores, com respostas simuladas."""
import datetime as dt
import json

import pytest

import coletar_governadores as gov
import coletar_prefeitura_ba as ba
import coletar_prefeitura_go as go
import coletar_prefeitura_sp as sp
from test_coletar_executivo_sapl import SaplFalso  # noqa: F401  (reaproveita o simulador de SAPL)


@pytest.fixture
def saida(tmp_path, monkeypatch):
    for m in (sp, ba, go):
        monkeypatch.setattr(m, "DADOS", tmp_path / "municipais")
    return tmp_path / "municipais"


def ano():
    return dt.date.today().year


# ================================================================ SP (webservice JSON)

def test_sp_link():
    assert sp.link("PL", 5, 2026, 1).endswith("tipo=1&numero=5&ano=2026")
    assert sp.link("PLO", 5, 2026, None) is None


def test_sp_promovente_id(monkeypatch):
    monkeypatch.setattr(sp, "ws", lambda op, **p: [
        {"chave": 1, "nome": "Ricardo Nunes", "tipo": {"nome": "VEREADOR"}},
        {"chave": 2, "nome": "RICARDO NUNES", "tipo": {"nome": "EXECUTIVO"}}])
    assert sp.promovente_id() == 2
    monkeypatch.setattr(sp, "ws", lambda op, **p: [])
    with pytest.raises(RuntimeError, match="promovente"):
        sp.promovente_id()


def test_sp_e_do_prefeito(monkeypatch):
    monkeypatch.setattr(sp, "ws", lambda op, **p: {"Autores": [{"Chave": 7}, {"Chave": 8}]})
    assert sp.e_do_prefeito("PL", 1, 2026, 8) and not sp.e_do_prefeito("PL", 1, 2026, 9)
    for vazio in (None, {}, {"Autores": None}):
        monkeypatch.setattr(sp, "ws", lambda op, v=vazio, **p: v)
        assert not sp.e_do_prefeito("PL", 1, 2026, 8)


def ws_sp(a):

    def proj(t, n):
        return {"tipo": t, "numero": n, "ano": a}

    dados = {
        "PromoventesCMSPJSON": [{"chave": 3, "nome": "Ricardo Nunes", "tipo": {"nome": "EXECUTIVO"}}],
        "ProjetosEmTramitacaoPorPromoventeJSON": [proj("PL", 2)],
        "ProjetosVetadosPorPromoventeJSON": [{**proj("PL", 3), "veto": {"nome": "Veto parcial"}}],
        "LeisAprovadasPorPromoventeJSON": [{"projeto": proj("PL", 1), "numero": 18000, "publicacao": "2026-03-04T00:00:00"}],
        "ProjetosPorAnoJSON": [{**proj("PL", n), "data": f"{a}-02-01T00:00:00", "ementa": f" Ementa {n} "} for n in (1, 2, 3, 4, 5)]
                             + [{**proj("PLO", 1), "data": f"{a}-02-01T00:00:00", "ementa": "Emenda"}, {**proj("REQ", 1), "data": f"{a}-02-01T00:00:00", "ementa": "x"}],
    }

    def ws(op, **p):
        if op == "ProjetoResumoJSON":
            do_prefeito = (p["Tipo"], p["Numero"]) in {("PL", 1), ("PL", 2), ("PL", 3), ("PL", 4)}  # PL 5 e PLO 1 são de vereadores
            return {"Autores": [{"Chave": 3 if do_prefeito else 99}]}
        return dados[op]

    return ws


def test_sp_coletar_classifica_situacao(saida, monkeypatch):
    a = ano()
    monkeypatch.setattr(sp, "ANO_INICIAL", a)
    monkeypatch.setattr(sp, "ws", ws_sp(a))
    sp.coletar()
    r = json.loads((saida / "SP" / f"prefeitura_{a}.json").read_text(encoding="utf-8"))
    m = r["materias"]
    assert m[f"PL-1-{a}"]["situacao"] == "Virou lei (Lei 18.000, publicada em 2026-03-04)"
    assert m[f"PL-2-{a}"]["situacao"] == "Em tramitação" and m[f"PL-2-{a}"]["emTramitacao"] is True
    assert m[f"PL-3-{a}"]["situacao"] == "Veto parcial"
    assert m[f"VET-PL-3-{a}"]["tipo"] == "VET" and m[f"VET-PL-3-{a}"]["situacao"] == "Veto parcial do prefeito"
    assert m[f"PL-4-{a}"]["situacao"].startswith("Fora de tramitação")
    assert f"PL-5-{a}" not in m and f"PLO-1-{a}" not in m          # autoria de outro promovente
    assert not any("REQ" in k for k in m)                         # tipo não monitorado
    assert m[f"PL-1-{a}"]["ementa"] == "Ementa 1" and m[f"PL-1-{a}"]["dataApresentacao"] == f"{a}-02-01"
    assert len(r["vistos"]) == 6  # PL 1-5 e PLO 1 já consultados; REQ nunca


def test_sp_segunda_execucao_so_consulta_projetos_novos(saida, monkeypatch):
    a = ano()
    monkeypatch.setattr(sp, "ANO_INICIAL", a)
    ws = ws_sp(a)
    monkeypatch.setattr(sp, "ws", ws)
    sp.coletar()
    consultas = []

    def ws2(op, **p):
        if op == "ProjetoResumoJSON":
            consultas.append((p["Tipo"], p["Numero"]))
        return ws(op, **p)

    monkeypatch.setattr(sp, "ws", ws2)
    sp.coletar()
    assert consultas == []   # nada novo: tudo veio de "vistos"


# ================================================================ BA (Scriptcase)

def linha_html(prop, ementa, sit, par="PARM123"):
    return (f'<TR  class="scGridFieldOdd"><td><span id="id_sc_field_proposicao_1">{prop}</span></td>'
            f'<td><span id="id_sc_field_pro_ementa_1">{ementa}</span></td><td><span id="id_sc_field_sit_nome_futuro_1">{sit}</span></td>'
            f"<td><a onclick=\"nm_gp_submit5('/cl/prop_interna_tram/', '/cl/prop_interna/', '{par}', 'x')\">h</a></td></TR>")


def resp_grade(*linhas):
    return {"setValue": [{"field": "sc_grid_body", "value": "".join(linhas)}]}


def test_ba_limpar_e_campo():
    assert ba.limpar("<b>A&amp;B</b>\n  c") == "A&B c"
    assert ba.campo('x id="id_sc_field_pro_ementa_9">Ementa <i>y</i></span>', "pro_ementa") == "Ementa y"
    assert ba.campo("sem campo", "x") == ""


def test_ba_linhas():
    r = ba.linhas(resp_grade(linha_html("PLE-12/2025", "Dispõe &amp; tal", "Em tramitação"), linha_html("VTO-1/2025", "Veto", "Armazenado", par="P2")))
    assert r == [{"prop": "PLE-12/2025", "ementa": "Dispõe & tal", "situacao": "Em tramitação", "parametros": "PARM123"},
                 {"prop": "VTO-1/2025", "ementa": "Veto", "situacao": "Armazenado", "parametros": "P2"}]


def test_ba_iso():
    assert ba.iso("05/03/2025") == "2025-03-05"


def movs(*itens):
    return [{"data": "01/01/2025", "situacao": s, "observacao": o, "link": None} for s, o in itens]


def test_ba_situacao_sancionado_com_numero_da_lei():
    m = movs(("Arquivado", ""), ("Sancionado", "LEI Nº 9.800/2025 PUBLICADO NO DOM"), ("Aprovado", ""))
    assert ba.situacao("PL", m, "Armazenado") == "Sancionado (Lei 9.800/2025)"


def test_ba_situacao_demais_casos():
    assert ba.situacao("PL", movs(("Sancionado", "sem número")), "Armazenado") == "Sancionado"
    assert ba.situacao("PL", movs(("Retirado pelo autor", "")), "Armazenado") == "Retirado pelo prefeito"
    assert ba.situacao("PL", movs(("Arquivado", "")), "Armazenado") == "Arquivado"
    assert ba.situacao("PL", movs(("Protocolado", "")), "Em comissão") == "Em comissão"
    assert ba.situacao("PL", movs(("Protocolado", "")), "") == "Protocolado"
    assert ba.situacao("PL", [], "") == ""
    assert ba.situacao("VET", movs(("Arquivado", "")), "Armazenado") == "Armazenado"   # veto: usa a grade


def test_ba_coletar_ponta_a_ponta(saida, monkeypatch):
    a = ano()
    monkeypatch.setattr(ba, "ANO_INICIAL", a)
    grade = resp_grade(linha_html(f"PLE-10/{a}", "Ementa dez", "Armazenado", "A"), linha_html(f"PLE-9/{a - 5}", "antigo", "x", "B"),
                       linha_html(f"XYZ-1/{a}", "tipo desconhecido", "x", "C"))
    grade["setValue"].append({"field": "sc_grid_toobar_bot", "value": "sm_counter_total'>3<"})
    monkeypatch.setattr(ba.S, "get", lambda url, **k: type("R", (), {"text": 'name="script_case_init" value="42"', "raise_for_status": lambda s: None})())
    monkeypatch.setattr(ba, "ajax", lambda url, sci, opc, parm: grade)
    chamados = []
    monkeypatch.setattr(ba, "historico", lambda par: chamados.append(par) or [
        {"data": "03/02/2025", "situacao": "Anexado integra", "observacao": "", "link": "http://pdf"}, {"data": "01/02/2025", "situacao": "Protocolado", "observacao": "", "link": None},
        {"data": "01/02/2025", "situacao": "Sancionado", "observacao": "LEI Nº 100/2025 PUBLICADO", "link": None}][::-1])
    ba.coletar()
    assert chamados == ["A"]   # só projetos de ANO_INICIAL em diante e de tipos conhecidos
    m = json.loads((saida / "BA" / f"prefeitura_{a}.json").read_text(encoding="utf-8"))["materias"][f"PLE-10/{a}"]
    assert m["tipo"] == "PL" and m["numero"] == 10 and m["dataApresentacao"] == "2025-02-01" and m["linkTexto"] == "http://pdf"
    assert m["situacao"] == "Sancionado (Lei 100/2025)" and m["emTramitacao"] is False


def test_ba_coletar_total_divergente_levanta(saida, monkeypatch):
    grade = resp_grade(linha_html("PLE-1/2000", "x", "x"))
    grade["setValue"].append({"field": "sc_grid_toobar_bot", "value": "sm_counter_total'>5<"})
    monkeypatch.setattr(ba.S, "get", lambda url, **k: type("R", (), {"text": 'name="script_case_init" value="42"'})())
    monkeypatch.setattr(ba, "ajax", lambda *a: grade if a[2] != "rec" else resp_grade())
    with pytest.raises(RuntimeError, match="lidos 1 de 5"):
        ba.coletar()


# ================================================================ GO (SUAP, HTML)

def bloco_go(uuid, assunto, interessados, criado, situacao):
    return (f'<div class="general-box"><a href="/processo_eletronico/visualizar_processo/{uuid}/">p</a>'
            f"<dt>Assunto:</dt><dd>{assunto}</dd><dt>Interessados:</dt><dd>{interessados}</dd>"
            f"<dt>Data de criação:</dt><dd>{criado}</dd><span class=\"status status-publico\">Público</span>"
            f'<span class="status status-ok">{situacao}</span></div>')


def pagina_go(total, *blocos):
    return f"<p>Total de {total} itens</p>" + "".join(blocos)


def falso_get_go(monkeypatch, paginas):
    class R:
        def __init__(self, t):
            self.text = t

        def raise_for_status(self):
            pass

    monkeypatch.setattr(go.S, "get", lambda url, params=None, **k: R(paginas[(params["ano"], params["page"])]))
    monkeypatch.setattr(go, "confiar", lambda: None)


def test_go_pagina_extrai_campos(monkeypatch):
    falso_get_go(monkeypatch, {(2026, 1): pagina_go(7, bloco_go("ab-12", "Projeto  de Lei nº 463/2026 -\n ementa &amp; mais", "Prefeito de Goiânia", "04/03/2026 10:00", "Finalizado"))})
    total, itens = go.pagina(2026, 1)
    assert total == 7
    assert itens == [{"uuid": "ab-12", "assunto": "Projeto de Lei nº 463/2026 - ementa & mais", "interessados": "Prefeito de Goiânia",
                      "criado": "04/03/2026 10:00", "situacao": "Finalizado"}]


@pytest.mark.parametrize("s,esperado", [("Finalizado", "Processo finalizado na Câmara"), ("Anexado", "Anexado a outro processo"), ("", "Em trâmite"), ("Em análise", "Em análise")])
def test_go_situacao(s, esperado):
    assert go.situacao(s) == esperado


@pytest.mark.parametrize("assunto,esperado", [
    ("Projeto de Lei nº 463/2026 - Dispõe", ("Projeto de Lei", "463", "2026", "Dispõe")),
    ("Projeto de Lei Complementar n. 5/26 - X", ("Projeto de Lei Complementar", "5", "26", "X")),
    ("Projeto de Emenda à Lei Orgânica nº 1/2025 - Y", ("Projeto de Emenda à Lei Orgânica", "1", "2025", "Y")),
])
def test_go_regex_assunto(assunto, esperado):
    assert go.ASSUNTO.match(assunto).groups() == esperado


def test_go_coletar(saida, monkeypatch):
    a = ano()
    monkeypatch.setattr(go, "ANO_INICIAL", a)
    falso_get_go(monkeypatch, {
        (a, 1): pagina_go(4,
                          bloco_go("a1", f"Projeto de Lei nº 10/{a} - Ementa A", "Prefeito de Goiânia", "10/03/2026", "Finalizado"),
                          bloco_go("a2", f"Projeto de Lei nº 11/{a} - de vereador", "Vereador X", "10/03/2026", "")),
        (a, 2): pagina_go(4,
                          bloco_go("a3", f"Projeto de Lei Complementar nº 2/{str(a)[2:]} - Ementa C", "Prefeito de Goiânia", "11/03/2026", ""),
                          bloco_go("a4", f"Projeto de Lei nº 10/{a} - Ementa A (reapresentado)", "Prefeito de Goiânia", "01/03/2026", "Anexado")),
        (a, 3): pagina_go(4)})
    go.coletar()
    m = json.loads((saida / "GO" / f"prefeitura_{a}.json").read_text(encoding="utf-8"))["materias"]
    assert sorted(m) == [f"PL-10-{a}", f"PLC-2-{a}"]
    assert m[f"PL-10-{a}"]["dataApresentacao"] == "2026-03-01" and m[f"PL-10-{a}"]["situacao"] == "Anexado a outro processo"   # fica o mais antigo
    assert m[f"PLC-2-{a}"]["emTramitacao"] is True and m[f"PLC-2-{a}"]["linkTexto"].endswith("/a3/")


def test_go_coletar_leitura_incompleta_levanta(saida, monkeypatch):
    a = ano()
    monkeypatch.setattr(go, "ANO_INICIAL", a)
    falso_get_go(monkeypatch, {(a, 1): pagina_go(3, bloco_go("a1", f"Projeto de Lei nº 1/{a} - X", "Prefeito de Goiânia", "10/03/2026", "")), (a, 2): pagina_go(3)})
    with pytest.raises(RuntimeError, match="lidos 1 de 3"):
        go.coletar()


# ================================================================ Governadores (SAPL)

def test_governo_autor(monkeypatch):
    s = SaplFalso(**{"base/autor": [{"id": 1, "nome": "Dep. X"}, {"id": 2, "nome": "Governador do Estado"}]})
    import coletar_estaduais as est
    monkeypatch.setattr(est, "get", s.get)
    assert gov.autor_governo("h") == 2
    s.colecoes["base/autor"] = [{"id": 1, "nome": "Dep. X"}]
    with pytest.raises(RuntimeError, match="governador"):
        gov.autor_governo("h")


def test_governo_coletar(tmp_path, monkeypatch):
    import coletar_estaduais as est
    a = ano()
    monkeypatch.setattr(gov, "DADOS", tmp_path)
    monkeypatch.setattr(gov, "ANO_INICIAL", a)
    mats = [{"id": 1, "tipo": 1, "ano": a, "numero": 1, "autores": [2], "em_tramitacao": False, "resultado": "Aprovado"},
            {"id": 2, "tipo": 1, "ano": a, "numero": 2, "autores": [9]},
            {"id": 3, "tipo": 2, "ano": a, "numero": 3, "autores": [2]}]
    s = SaplFalso(**{"base/autor": [{"id": 2, "nome": "Governador"}],
                     "materia/tipomaterialegislativa": [{"id": 1, "sigla": "PL", "descricao": "Projeto de Lei"}, {"id": 2, "sigla": "IND", "descricao": "Indicação"}],
                     "materia/materialegislativa": mats})
    monkeypatch.setattr(est, "get", s.get)
    gov.coletar("PB", "h")
    r = json.loads((tmp_path / "PB" / f"governo_{a}.json").read_text(encoding="utf-8"))["materias"]
    assert list(r) == ["1"] and r["1"]["situacao"] == "Aprovado"
