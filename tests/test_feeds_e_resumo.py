import xml.etree.ElementTree as ET
from collections import defaultdict


import feeds
import resumo_email as r


def vazio_d(**extra):
    d = {"camara": [], "senado": (0, 0), "detalhe": (0, 0), "executivo": [], "executivo_situacao": [],
         "estaduais": (defaultdict(list), defaultdict(list)), "governo": (defaultdict(list), defaultdict(list)),
         "municipais": (defaultdict(list), defaultdict(list)), "votacoes": [], "tse": []}
    d.update(extra)
    return d


def prop(tipo="PL", n=1, deps=()):
    return {"siglaTipo": tipo, "numero": n, "ano": 2025, "ementa": "Dispõe sobre algo", "idsDeputados": list(deps)}


# ---------------------------------------------------------------- resumo_email

def test_cortar():
    assert r.cortar("a  b\n c") == "a b c"
    assert r.cortar("x" * 200, 10) == "x" * 9 + "…"
    assert r.cortar(None) == ""


def test_linhas_vazio():
    assert r.linhas(vazio_d()) == []


def test_linhas_camara_destaca_tipos_e_resume_resto():
    d = vazio_d(camara=[prop("PL"), prop("PEC", 2), prop("REQ", 3), prop("REQ", 4), prop("INC", 5)])
    secoes = dict(r.linhas(d))
    titulo = "Câmara dos Deputados — 5 proposições novas"
    assert titulo in secoes
    itens = secoes[titulo]
    assert itens[0].startswith("PL 1/2025")
    assert itens[-1] == "Outros: 2 REQ, 1 INC"


def test_linhas_limita_itens_listados():
    d = vazio_d(camara=[prop("PL", i) for i in range(r.LIMITE + 5)])
    (_, itens), = r.linhas(d)
    assert itens[-1] == "…e mais 5 projetos"


def test_linhas_senado_executivo_e_votacoes():
    d = vazio_d(senado=(10, 13), executivo=[{"tipo": "MPV", "numero": 1, "ano": 2025, "ementa": "x"}],
                executivo_situacao=[({"tipo": "PL", "numero": 2, "ano": 2025, "situacao": "Sancionada"}, "Aguardando")],
                votacoes=["SP", "RJ"], tse=["dados/tse/2026/SP.json"])
    titulos = [t for t, _ in r.linhas(d)]
    assert "Senado — 3 matérias novas" in titulos
    assert "Executivo — 1 novo, 1 com nova situação" in titulos
    assert "Votações estaduais atualizadas" in titulos
    assert "TSE — 1 arquivo recoletado" in titulos
    exec_itens = dict(r.linhas(d))["Executivo — 1 novo, 1 com nova situação"]
    assert "PL 2/2025: Aguardando → Sancionada" in exec_itens


def test_montar_sem_novidades():
    h, t = r.montar(vazio_d(), "Título")
    assert t == "Nenhum dado novo nesta execução."


def test_montar_escapa_html_e_inclui_rodape():
    d = vazio_d(camara=[{**prop(), "ementa": "<script>alert(1)</script>"}])
    h, t = r.montar(d, "Resumo <b>", ("<p>rodape</p>", "texto-rodape"))
    assert "<script>" not in h and "&lt;script&gt;" in h
    assert "&lt;b&gt;" in h
    assert "<p>rodape</p>" in h
    assert t.endswith("texto-rodape")


def test_mensagem(monkeypatch):
    monkeypatch.setenv("SMTP_USUARIO", "de@exemplo.org")
    m = r.mensagem("Assunto", "para@exemplo.org", "<p>oi</p>", "oi", {"List-Unsubscribe": "<x>"})
    assert m["Subject"] == "Assunto" and m["To"] == "para@exemplo.org" and m["From"] == "de@exemplo.org"
    assert m["List-Unsubscribe"] == "<x>"
    assert m.get_body(("plain",)).get_content().strip() == "oi"
    assert "<p>oi</p>" in m.get_body(("html",)).get_content()


# ---------------------------------------------------------------- feeds

def dados_estaduais():
    novas = defaultdict(list, {"SP": [{"tipo": "PL", "numero": 1, "ano": 2026, "dataApresentacao": "2026-01-01", "ementa": "e", "idsDeputados": [77]}],
                               "RJ": [{"tipo": "PL", "numero": 2, "ano": 2026, "dataApresentacao": "2026-01-02", "ementa": "e"}]})
    return novas, defaultdict(list)


def test_arquivo_troca_dois_pontos():
    assert feeds.arquivo("UF:SP") == "UF-SP.xml"
    assert feeds.arquivo("dep:123") == "dep-123.xml"


def test_vazio():
    assert feeds.vazio(vazio_d())
    assert not feeds.vazio(vazio_d(votacoes=["SP"]))


def test_selecionar_federal_leva_camara_e_senado():
    d = vazio_d(camara=[prop(deps=[1]), prop(n=2, deps=[2])], senado=(0, 5))
    parte = feeds.selecionar(d, {"FEDERAL"}, {})
    assert len(parte["camara"]) == 2 and parte["senado"] == (0, 5)


def test_selecionar_deputado_especifico():
    d = vazio_d(camara=[prop(deps=[1]), prop(n=2, deps=[2])], senado=(0, 5))
    parte = feeds.selecionar(d, {"dep:2"}, {})
    assert [i["numero"] for i in parte["camara"]] == [2]
    assert parte["senado"] == (0, 0)


def test_selecionar_uf_inclui_bancada_federal_do_estado():
    d = vazio_d(camara=[prop(deps=[1]), prop(n=2, deps=[2])])
    parte = feeds.selecionar(d, {"UF:SP"}, {"SP": {1}, "RJ": {2}})
    assert [i["numero"] for i in parte["camara"]] == [1]


def test_selecionar_br_junta_federal_e_todos_os_estados():
    d = vazio_d(camara=[prop(deps=[1]), prop(n=2, deps=[2])], senado=(0, 5), votacoes=["SP", "RJ"])
    parte = feeds.selecionar(d, {"BR"}, {"SP": {1}, "RJ": {2}})
    assert len(parte["camara"]) == 2 and parte["senado"] == (0, 5) and parte["votacoes"] == ["SP", "RJ"]


def test_link_historico_de_br_nao_filtra_local_e_federal_filtra_br():
    assert "locais" not in r.link_historico("2026-10-25", {"BR"})
    assert r.link_historico("2026-10-25", {"FEDERAL"}).endswith("&locais=BR")


def test_selecionar_estado_e_deputado_estadual():
    d = vazio_d(estaduais=dados_estaduais(), votacoes=["SP", "RJ"])
    parte = feeds.selecionar(d, {"UF:SP"}, {})
    assert list(parte["estaduais"][0]) == ["SP"]
    assert parte["votacoes"] == ["SP"]
    so_dep = feeds.selecionar(d, {"est:SP:77"}, {})
    assert list(so_dep["estaduais"][0]) == ["SP"]
    assert "SP" not in feeds.selecionar(d, {"est:SP:99"}, {})["estaduais"][0]
    assert "RJ" not in so_dep["estaduais"][0]


def test_selecionar_presidencia_so_com_pres_ou_br():
    d = vazio_d(executivo=[{"id": 1}])
    assert feeds.selecionar(d, {"pres"}, {})["executivo"] == [{"id": 1}]
    assert feeds.selecionar(d, {"UF:SP"}, {})["executivo"] == []


def test_item_e_feed_sao_xml_valido_e_escapam():
    it = feeds.item("A & B", "2026-01-02", "UF:SP", "corpo <x>")
    xml = feeds.feed("UF:SP", "Estado: <SP>", [it])
    raiz = ET.fromstring(xml)
    assert raiz.tag == "rss"
    titulo_item = raiz.find("channel/item/title").text
    assert titulo_item == "A & B"
    assert raiz.find("channel/item/guid").text == "minha-bancada-UF:SP-2026-01-02"
    assert "<SP>" in raiz.find("channel/title").text
    assert "2026" in raiz.find("channel/item/pubDate").text


def test_ministerios_no_resumo_e_so_nos_feeds_federais():
    d = vazio_d(ministerios=[("RIC 3/2026", "Solicita informações ao Ministro da Saúde", "Saúde")])
    secoes = r.linhas(d)
    assert secoes[0][0] == "Ministérios — 1 pedido novo" and "Saúde" in secoes[0][1][0]
    assert "Ministérios 1" in r.resumo_curto(d)
    deps = {"SP": {1}}
    assert feeds.selecionar(d, {"FEDERAL"}, deps)["ministerios"] == d["ministerios"]
    assert feeds.selecionar(d, {"BR"}, deps)["ministerios"] == d["ministerios"]
    assert feeds.selecionar(d, {"UF:SP"}, deps)["ministerios"] == []
