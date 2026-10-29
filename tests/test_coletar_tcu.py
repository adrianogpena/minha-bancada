import json

import coletar_tcu as tcu


class Resp:
    def __init__(self, corpo):
        self.corpo = corpo

    def raise_for_status(self):
        pass

    def json(self):
        return self.corpo


PAGINA_1 = {"items": [
    {"nome": "ABDALA GOMES SANTOS", "cpf": "215.805.453-00", "processo": "026.615/2020-7", "deliberacao": "AC-000738/2022-PL",
     "data_transito_julgado": "2022-07-16T03:00:00Z", "data_final": "2027-07-16T03:00:00Z", "data_acordao": "2022-04-06T17:30:00Z",
     "uf": "MA", "municipio": "SANTA INES"},
    {"nome": "  ", "cpf": "000.000.000-00", "processo": "1", "uf": "SP"}], "hasMore": True}
PAGINA_2 = {"items": [
    {"nome": "ADAIR SAAR", "cpf": "689.233.927-15", "processo": "000.288/2025-0", "deliberacao": None,
     "data_transito_julgado": None, "data_final": "2031-08-27T03:00:00Z", "data_acordao": None, "uf": "sp", "municipio": None}], "hasMore": False}


def test_coleta_pagina_ate_acabar_e_nao_guarda_cpf(monkeypatch):
    chamadas = []

    def get(s, url, **k):
        chamadas.append(k["params"]["offset"])
        return Resp(PAGINA_1 if k["params"]["offset"] == 0 else PAGINA_2)

    monkeypatch.setattr(tcu.comum, "get", get)
    itens = tcu.coletar(object())
    assert chamadas == [0, 500]
    assert itens == [
        {"nome": "ABDALA GOMES SANTOS", "processo": "026.615/2020-7", "deliberacao": "AC-000738/2022-PL", "acordao": "2022-04-06",
         "transito": "2022-07-16", "fim": "2027-07-16", "uf": "MA", "municipio": "SANTA INES"},
        {"nome": "ADAIR SAAR", "processo": "000.288/2025-0", "fim": "2031-08-27", "uf": "SP"}]
    assert "cpf" not in json.dumps(itens)


def test_inidoneos_guardam_so_cnpj_valido(monkeypatch):
    corpo = {"items": [
        {"nome": "ALB ENGENHARIA EIRELI", "cpf_cnpj": "04.268.324/0001-66", "processo": "005.959/2015-2", "deliberacao": "AC-002216/2018-PL",
         "data_final": "2028-08-17T03:00:00Z", "uf": "DF", "municipio": None},
        {"nome": "PESSOA FISICA", "cpf_cnpj": "111.444.777-35", "processo": "3/2020-1", "uf": "SP"},
        {"nome": "INVALIDO", "cpf_cnpj": "00.000.000/0000-00", "processo": "4/2020-1", "uf": "SP"}], "hasMore": False}
    monkeypatch.setattr(tcu.comum, "get", lambda s, url, **k: Resp(corpo))
    assert tcu.coletar_inidoneos(object()) == [
        {"nome": "ALB ENGENHARIA EIRELI", "processo": "005.959/2015-2", "deliberacao": "AC-002216/2018-PL", "fim": "2028-08-17", "uf": "DF",
         "cnpj": "04268324000166"}]
