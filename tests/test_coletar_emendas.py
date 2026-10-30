import datetime as dt

import coletar_emendas as em


class Resp:
    def __init__(self, corpo):
        self.corpo = corpo

    def raise_for_status(self):
        pass

    def json(self):
        return self.corpo


PAGINAS = {
    1: [{"codigoEmenda": "202339910001", "ano": 2023, "tipoEmenda": "Emenda Individual - Transferências com Finalidade Definida",
         "autor": "FULANO DE TAL", "numeroEmenda": "0001", "localidadeDoGasto": "CAMPINAS (SP)", "funcao": "Saúde", "subfuncao": "Atenção básica",
         "valorEmpenhado": "1.500.000,00", "valorLiquidado": "0,00", "valorPago": "750.000,50"},
        {"codigoEmenda": "202339910002", "ano": 2023, "tipoEmenda": "Emenda de Bancada", "autor": "BANCADA DO CEARÁ", "numeroEmenda": "0002",
         "localidadeDoGasto": "CEARÁ", "funcao": "Educação", "subfuncao": "Ensino superior", "valorEmpenhado": "10,00", "valorLiquidado": "10,00", "valorPago": "10,00"},
        {"codigoEmenda": "", "autor": "SEM CÓDIGO"}],
    2: [{"codigoEmenda": "202339910001", "ano": 2023, "autor": "FULANO DE TAL", "numeroEmenda": "0001", "localidadeDoGasto": "CAMPINAS (SP)",
         "funcao": "Saúde", "subfuncao": "Atenção básica", "valorEmpenhado": "1.500.000,00", "valorPago": "800.000,00", "tipoEmenda": "Emenda Individual - Transferências com Finalidade Definida"}],
    3: [],
}


def test_pagina_ate_vazia_junta_repetidas_e_converte_valores(monkeypatch):
    pedidas = []

    def get(s, url, **k):
        pedidas.append((k["params"], k["headers"]["chave-api-dados"]))
        return Resp(PAGINAS[k["params"]["pagina"]])

    monkeypatch.setattr(em.comum, "get", get)
    itens = em.coletar_ano(2023, "segredo", object(), pausa=0)
    assert pedidas == [({"ano": 2023, "pagina": p}, "segredo") for p in (1, 2, 3)]
    assert itens == [
        {"codigo": "202339910001", "ano": 2023, "tipo": "Emenda Individual - Transferências com Finalidade Definida", "numero": "0001",
         "autor": "FULANO DE TAL", "local": "CAMPINAS (SP)", "municipio": "CAMPINAS", "uf": "SP", "funcao": "Saúde", "subfuncao": "Atenção básica",
         "empenhado": 1500000.0, "pago": 800000.0},
        {"codigo": "202339910002", "ano": 2023, "tipo": "Emenda de Bancada", "numero": "0002", "autor": "BANCADA DO CEARÁ", "local": "CEARÁ",
         "funcao": "Educação", "subfuncao": "Ensino superior", "empenhado": 10.0, "liquidado": 10.0, "pago": 10.0}]


def test_ano_encerrado_nao_e_baixado_de_novo(monkeypatch, tmp_path):
    monkeypatch.setattr(em, "DADOS", tmp_path)
    (tmp_path / "2019.json").write_text("{}")
    baixados = []
    monkeypatch.setattr(em, "coletar_ano", lambda ano, chave, s, pausa: baixados.append(ano) or [{"codigo": "1", "autor": "A"}])
    em.coletar("k", hoje=dt.date(2026, 10, 30))
    assert baixados == [2020, 2021, 2022, 2023, 2024, 2025, 2026]
    assert (tmp_path / "2026.json").exists()
    assert (tmp_path / "2019.json").read_text() == "{}"


def test_ano_vazio_ou_com_erro_mantem_o_arquivo_anterior(monkeypatch, tmp_path):
    monkeypatch.setattr(em, "DADOS", tmp_path)
    (tmp_path / "2026.json").write_text("antigo")

    def coletar_ano(ano, chave, s, pausa):
        if ano == 2025:
            raise RuntimeError("falhou")
        return []

    monkeypatch.setattr(em, "coletar_ano", coletar_ano)
    em.coletar("k", [2025, 2026], hoje=dt.date(2026, 10, 30))
    assert (tmp_path / "2026.json").read_text() == "antigo"
    assert not (tmp_path / "2025.json").exists()


def test_sem_chave_nao_coleta(monkeypatch):
    monkeypatch.delenv(em.VARIAVEL, raising=False)
    monkeypatch.setattr(em, "coletar", lambda *a, **k: (_ for _ in ()).throw(AssertionError("coletou sem chave")))
    em.main()
