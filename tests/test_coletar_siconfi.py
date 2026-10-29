import datetime as dt

import coletar_siconfi as sic
import estaduais_comum as comum


def item(conta, coluna, valor, poder="L", instituicao="Assembleia Legislativa do Estado do Amapá"):
    return {"instituicao": instituicao, "co_poder": poder, "cod_conta": conta, "coluna": coluna, "valor": valor}


AMOSTRA = [
    item("DespesaComPessoalBruta", "<MR>", 21400677.58),
    item("DespesaComPessoalBruta", "TOTAL (ÚLTIMOS 12 MESES) (a)", 169549626.85),
    item("DespesaComPessoalLiquida", "TOTAL (ÚLTIMOS 12 MESES) (a)", 153592169.43),
    item("ReceitaCorrenteLiquidaLimiteLegal", "Valor", 9704126943.38),
    item("DespesaComPessoalTotal", "Valor", 153592169.43),
    item("DespesaComPessoalTotal", "% sobre a RCL Ajustada", 1.58),
    item("LimiteMaximoDespesaComPessoalTotal", "Valor", 178338131.37),
    item("LimiteMaximoDespesaComPessoalTotal", "% sobre a RCL Ajustada", 1.84),
    item("DespesaComPessoalAtivoBruta", "TOTAL (ÚLTIMOS 12 MESES) (a)", 1.0),
]


def test_resumir_pega_so_as_contas_e_colunas_usadas():
    linhas = sic.resumir(AMOSTRA, "https://fonte")
    assert linhas == [{"poder": "L", "instituicao": "Assembleia Legislativa do Estado do Amapá", "fonte": "https://fonte",
                       "despesaBruta": 169549626.85, "despesaLiquida": 153592169.43, "rcl": 9704126943.38, "dtp": 153592169.43,
                       "pctDtp": 1.58, "limiteMaximo": 178338131.37, "pctLimiteMaximo": 1.84}]


def test_resumir_separa_instituicoes_e_ignora_item_sem_valor():
    outro = [item("DespesaComPessoalTotal", "Valor", 5.0, instituicao="Tribunal de Contas"), item("DespesaComPessoalTotal", "Valor", None)]
    linhas = sic.resumir(AMOSTRA + outro, "f")
    assert [lin["instituicao"] for lin in linhas] == ["Assembleia Legislativa do Estado do Amapá", "Tribunal de Contas"]
    assert linhas[1]["dtp"] == 5.0


def test_resumir_sem_conta_conhecida_devolve_vazio():
    assert sic.resumir([item("Outra", "Valor", 1.0)], "f") == []


def conta_dca(conta, coluna, valor):
    return {"cod_conta": "TotalDespesas", "conta": conta, "coluna": coluna, "valor": valor}


DCA = [
    conta_dca("01 - Legislativa", "Despesas Liquidadas", 3075127995.18),
    conta_dca("01.031 - Ação Legislativa", "Despesas Empenhadas", 1208171751.48),
    conta_dca("01.031 - Ação Legislativa", "Despesas Liquidadas", 1159495141.52),
    conta_dca("01.032 - Controle Externo", "Despesas Pagas", 865874902.48),
    conta_dca("01.032 - Controle Externo", "Inscrição de Restos a Pagar Processados", 1.0),
    conta_dca("04 - Administração", "Despesas Liquidadas", 9.0),
    {**conta_dca("01.031 - Ação Legislativa", "Despesas Pagas", 5.0), "cod_conta": "Outra"},
]


def test_resumir_legislativa_pega_a_funcao_e_as_subfuncoes():
    assert sic.resumir_legislativa(DCA, "https://dca") == {
        "fonte": "https://dca", "legislativa": {"liquidada": 3075127995.18},
        "acaoLegislativa": {"empenhada": 1208171751.48, "liquidada": 1159495141.52}, "controleExterno": {"paga": 865874902.48}}


def test_resumir_legislativa_sem_a_funcao_devolve_vazio():
    assert sic.resumir_legislativa([conta_dca("04 - Administração", "Despesas Pagas", 1.0)], "f") == {}


def test_url_dca_leva_o_ente_e_o_anexo():
    u = sic.url_dca("SP", 2024)
    assert "id_ente=35" in u and "an_exercicio=2024" in u and "DCA-Anexo+I-E" in u


def test_url_leva_o_ente_e_o_poder():
    u = sic.url("AP", 2025, "Q", 3, "L")
    assert "id_ente=16" in u and "co_poder=L" in u and "an_exercicio=2025" in u and "RGF-Anexo+01" in u


class Resp:
    def __init__(self, corpo):
        self.corpo = corpo

    def raise_for_status(self):
        pass

    def json(self):
        return self.corpo


class Sessao:
    """Só o 2.º quadrimestre de 2025 está publicado; o ano corrente (2026) não tem nada."""

    def __init__(self):
        self.chamadas = []

    def get(self, endereco, timeout=None):
        self.chamadas.append(endereco)
        if "/dca?" in endereco:
            return Resp({"items": DCA if "an_exercicio=2025" in endereco else [], "hasMore": False})
        publicado = "an_exercicio=2025" in endereco and "in_periodicidade=Q" in endereco and "nr_periodo=2" in endereco and "co_poder=L" in endereco
        return Resp({"items": AMOSTRA if publicado else [], "hasMore": False})


def test_coletar_uf_usa_o_ultimo_periodo_publicado(tmp_path, monkeypatch):
    monkeypatch.setattr(sic, "DADOS", tmp_path)
    s = Sessao()
    sic.coletar_uf(s, "AP", dt.date(2026, 3, 1))
    gravado = comum.ler(tmp_path / "AP.json")
    assert gravado["uf"] == "AP" and list(gravado["anos"]) == ["2025"]
    linha = gravado["anos"]["2025"]["poderes"][0]
    assert (linha["periodicidade"], linha["periodo"], linha["dtp"]) == ("Q", 2, 153592169.43)
    assert "nr_periodo=2" in linha["fonte"] and "co_poder=L" in linha["fonte"]
    assert gravado["anos"]["2025"]["legislativa"]["acaoLegislativa"]["liquidada"] == 1159495141.52


def test_ano_encerrado_nao_e_baixado_de_novo(tmp_path, monkeypatch):
    monkeypatch.setattr(sic, "DADOS", tmp_path)
    antigo = {"2023": {"poderes": [{"poder": "L", "instituicao": "Antiga", "dtp": 1.0}], "legislativa": {"fonte": "f"}}}
    comum.salvar(tmp_path / "AP.json", {"coletadoEm": "2026-01-01", "uf": "AP", "anos": antigo})
    s = Sessao()
    sic.coletar_uf(s, "AP", dt.date(2026, 3, 1))
    assert comum.ler(tmp_path / "AP.json")["anos"]["2023"] == antigo["2023"]
    assert not any("an_exercicio=2023" in c for c in s.chamadas)


def test_paginacao_junta_as_paginas():
    class Paginada:
        def get(self, endereco, timeout=None):
            primeira = "offset=0" in endereco
            return Resp({"items": [{"n": 1}] if primeira else [{"n": 2}], "hasMore": primeira})

    assert sic.baixar(Paginada(), "AP", 2025, "Q", 3, "L") == [{"n": 1}, {"n": 2}]
