import json
from datetime import date
from pathlib import Path

import coletar_vereadores_sapl as s

FIX = Path(__file__).parent / "fixtures" / "contratos"
API = json.loads((FIX / "sapl_camara_vereadores.json").read_text(encoding="utf-8"))
HTML = (FIX / "interlegis_sapl_cm.html").read_text(encoding="utf-8")
CAMARA = {"nome": "Câmara Municipal de Alfenas", "cnpj": "1", "municipio": "Alfenas", "url": "https://sapl.alfenas.mg.leg.br"}


def test_camaras_da_pagina_le_cards_com_sapl():
    achadas, total = s.camaras_da_pagina(HTML)
    assert total == 3
    assert achadas and all(c["url"].startswith("https://sapl.") and not c["url"].endswith("/") for c in achadas)
    abre = next(c for c in achadas if c["municipio"] == "Abre Campo")
    assert abre["cnpj"] == "00.492.087/0001-61" and abre["url"] == "https://sapl.abrecampo.mg.leg.br"


def test_legislatura_atual_escolhe_a_que_contem_2025():
    assert s.legislatura_atual(API["legislatura"])["data_inicio"] == "2025-01-01"
    assert s.legislatura_atual([l for l in API["legislatura"] if l["data_inicio"] < "2025"]) is None


def test_itens_camara_titular_suplente_e_afastamento():
    leg = s.legislatura_atual(API["legislatura"])
    itens = s.itens_camara(CAMARA, leg, API["mandato"], API["parlamentar"])
    assert len(itens) == 4 and {i["cargo"] for i in itens} == {"VEREADOR"}
    assert {i["municipio"] for i in itens} == {"Alfenas"} and {i["camara"] for i in itens} == {CAMARA["url"]}
    assert [i["afastamento"] for i in itens].count(None) == 3
    assert any(i["afastamento"] == "2025-08-10" for i in itens)
    assert all("cpf" not in i and i["nome"] for i in itens)


def test_itens_camara_descarta_mandato_de_outra_legislatura():
    leg = s.legislatura_atual(API["legislatura"])
    antigo = {"parlamentar": API["mandato"][0]["parlamentar"], "titular": True,
              "data_inicio_mandato": "2009-01-01", "data_fim_mandato": "2012-12-31"}
    itens = s.itens_camara(CAMARA, leg, API["mandato"] + [antigo], API["parlamentar"])
    assert len(itens) == 4 and all(i["ingresso"] >= "2025-01-01" for i in itens)


def test_vencida_respeita_revisita_e_escalonamento():
    hoje = date(2026, 11, 28)
    assert s.vencida(None, "u", hoje)
    assert s.vencida({"lidoEm": "2026-11-01", "itens": [1]}, "u", hoje)
    assert not s.vencida({"lidoEm": "2026-11-28", "itens": [1]}, "u", hoje)
    assert not s.vencida({"lidoEm": "2026-11-28", "itens": []}, "u", hoje)
    assert s.vencida({"lidoEm": "2026-10-01", "itens": []}, "u", hoje)
    assert not s.vencida({"lidoEm": "2026-11-28", "erro": "x"}, "u", hoje)
    assert s.vencida({"lidoEm": "2026-11-27", "erro": "x"}, "u", hoje)


class Resposta:
    def __init__(self, dados):
        self.dados = dados

    def json(self):
        return self.dados

    def raise_for_status(self):
        pass


class SessaoFalsa:
    def __init__(self, falhar=()):
        self.falhar, self.chamadas = falhar, []

    def get(self, url, timeout=None, params=None, **kw):
        self.chamadas.append(url)
        if any(f in url for f in self.falhar):
            raise RuntimeError("fora do ar")
        if url.endswith("/legislatura/"):
            lista = API["legislatura"]
        elif url.endswith("/mandato/"):
            lista = API["mandato"]
        else:
            lista = API["parlamentar"]
        return Resposta({"results": lista, "pagination": {"next_page": None}})


def test_coletar_uf_cache_e_falha_isolada(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "DADOS", tmp_path)
    outra = {"nome": "Câmara Municipal de Outra", "cnpj": "2", "municipio": "Outra", "url": "https://sapl.outra.mg.leg.br"}
    comum_salvar = s.comum.salvar
    comum_salvar(tmp_path / "MG" / "camaras_sapl.json", {"coletadoEm": "2026-11-28", "camaras": [CAMARA, outra]})
    sessao = SessaoFalsa(falhar=("outra",))
    s.coletar_uf("MG", sessao, date(2026, 11, 28))
    dados = json.loads((tmp_path / "MG" / "vereadores_sapl.json").read_text(encoding="utf-8"))["camaras"]
    assert len(dados[CAMARA["url"]]["itens"]) == 4
    assert dados[outra["url"]]["itens"] == [] and "erro" in dados[outra["url"]]
    antes = len(sessao.chamadas)
    s.coletar_uf("MG", sessao, date(2026, 11, 28))
    assert len(sessao.chamadas) == antes
    s.coletar_uf("MG", sessao, date(2026, 11, 29))
    assert sessao.chamadas[antes:] == ["https://sapl.outra.mg.leg.br/api/parlamentares/legislatura/"]
