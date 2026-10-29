import datetime as dt

import coletar_siconfi_municipios as mun
import estaduais_comum as comum
import gerar_politicos as gp
from test_coletar_siconfi import DCA, Resp

HOJE = dt.date(2026, 10, 29)


class Sessao:
    """Só os municípios de `com_dca` entregaram a DCA de 2024."""

    def __init__(self, com_dca):
        self.com_dca = com_dca
        self.chamadas = []

    def get(self, endereco, timeout=None):
        self.chamadas.append(endereco)
        entregue = "an_exercicio=2024" in endereco and any(f"id_ente={c}&" in endereco + "&" for c in self.com_dca)
        itens = [{**i, "populacao": 5000} for i in DCA] if entregue else []
        return Resp({"items": itens, "hasMore": False})


def test_despesa_camara_pega_a_acao_legislativa_e_a_populacao():
    reg = mun.despesa_camara(Sessao(["1600105"]), "1600105", 2024)
    assert reg["liquidada"] == 1159495141.52 and reg["empenhada"] == 1208171751.48 and reg["populacao"] == 5000
    assert "id_ente=1600105" in reg["fonte"] and "an_exercicio=2024" in reg["fonte"]


def test_despesa_camara_sem_dca_devolve_vazio():
    assert mun.despesa_camara(Sessao([]), "1600105", 2024) == {}


def test_ultimo_ano_cai_para_o_ano_com_dca():
    s = Sessao([str(mun.SAO_PAULO)])
    assert mun.ultimo_ano(s, HOJE) == 2024
    assert mun.ultimo_ano(Sessao([]), HOJE) is None


def test_a_consultar_pula_o_guardado_e_retenta_sem_dca_antigo():
    guardados = {"1": {"liquidada": 1.0}, "2": {"semDca": "2026-10-20"}, "3": {"semDca": "2026-09-01"}}
    assert mun.a_consultar(["1", "2", "3", "4"], guardados, HOJE) == ["3", "4"]


def test_coletar_uf_guarda_o_lido_e_nao_refaz(tmp_path, monkeypatch):
    monkeypatch.setattr(mun, "DADOS", tmp_path)
    mun.coletar_uf(Sessao(["1600105"]), "AP", ["1600105", "1600204"], 2024, HOJE)
    gravado = comum.ler(tmp_path / "AP.json")
    assert gravado["ano"] == 2024 and gravado["municipios"]["1600105"]["liquidada"] == 1159495141.52
    assert gravado["municipios"]["1600204"] == {"semDca": "2026-10-29"}
    s = Sessao(["1600105"])
    mun.coletar_uf(s, "AP", ["1600105", "1600204"], 2024, HOJE)
    assert s.chamadas == []


def test_coletar_uf_de_outro_ano_recomeca(tmp_path, monkeypatch):
    monkeypatch.setattr(mun, "DADOS", tmp_path)
    comum.salvar(tmp_path / "AP.json", {"ano": 2023, "municipios": {"1600105": {"liquidada": 1.0}}})
    s = Sessao(["1600105"])
    mun.coletar_uf(s, "AP", ["1600105"], 2024, HOJE)
    assert comum.ler(tmp_path / "AP.json")["municipios"]["1600105"]["liquidada"] == 1159495141.52


def test_custo_camara_municipal_divide_pelas_cadeiras():
    dca = {"ano": 2024, "municipios": {"1600105": {"liquidada": 900.0, "fonte": "f"}, "1600204": {"semDca": "2026-10-29"}}}
    assert gp.custo_camara_municipal("1600105", 9, dca) == {"ano": 2024, "despesaLiquidada": 900.0, "cadeiras": 9, "porParlamentar": 100.0, "fonte": "f"}
    assert gp.custo_camara_municipal("1600204", 9, dca) == {}
    assert gp.custo_camara_municipal("1600105", 0, dca) == {}
    assert gp.custo_camara_municipal(None, 9, dca) == {}
