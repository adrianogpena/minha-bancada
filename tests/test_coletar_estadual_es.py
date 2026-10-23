import json
from datetime import date

import coletar_estadual_es as es
import estaduais_comum as comum
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"


def amostra(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


def linhas_do_contrato():
    return es.linhas_da_assembleia(amostra("estadual_es_despesas")["csv"].split("\n"))


def deputados_do_contrato(filtro):
    nomes = sorted({l["Favorecido"] for l in linhas_do_contrato() if filtro(l)})
    return [{"id": str(i), "nome": n.title(), "nomeCivil": n} for i, n in enumerate(nomes, 1)]


def test_arquivos_por_ano_do_contrato():
    achados = es.arquivos_por_ano(amostra("estadual_es_ckan"))
    assert achados and all(2004 <= a <= 2100 for a in achados)


def test_arquivos_por_ano_ignora_semestres_e_outros():
    pacote = {"result": {"resources": [{"name": "Despesas-2024.csv", "url": "https://x/24.csv"},
                                       {"name": "Despesas-2024_1Semestre.csv", "url": "https://x/24s.csv"},
                                       {"name": "Despesas-2013.csv", "url": "https://x/13a.csv"}, {"name": "Despesas-2013.csv", "url": "https://x/13b.csv"},
                                       {"name": "RestosAPagar-2024.csv", "url": "https://x/rap.csv"}, {"name": "Dicionario de Dados", "url": "https://x/d.pdf"}]}}
    assert {a: r["url"] for a, r in es.arquivos_por_ano(pacote).items()} == {2024: "https://x/24.csv", 2013: "https://x/13a.csv"}


def test_linhas_da_assembleia_filtra_unidade_gestora():
    linhas = ["﻿UnidadeGestora;Favorecido;HistoricoDocumento",
              "ASSEMBLEIA LEGISLATIVA DO ESTADO DO ESPÍRITO SANTO;A;x".encode("utf-8"),
              "SECRETARIA DA SAUDE;B;PAGO A ASSEMBLEIA LEGISLATIVA",
              "ASSEMBLEIA LEGISLATIVA;C"]
    assert [l["Favorecido"] for l in es.linhas_da_assembleia(linhas)] == ["A"]


def test_referencia_e_periodo():
    assert es.referencia("REFERENTE À COTA PARLAMENTAR DO MÊS DE MARÇO", "2026-04-09") == "2026-03"
    assert es.referencia("COTA PARLAMENTAR DO MÊS DE DEZEMBRO", "2026-01-15") == "2025-12"
    assert es.referencia("sem mês", "2026-01-15") is None
    assert es.periodo("REFERENTE AO PERÍODO DE 02/07/2026 a 03/07/2026, PARA") == ("2026-07-02", "2026-07-03")
    assert es.periodo("") == (None, None)


def test_itens_cota_so_pagamentos_de_deputados_do_contrato():
    deps = deputados_do_contrato(es.e_cota)
    itens = es.itens_cota(linhas_do_contrato(), deps)
    assert itens and {i["idDeputado"] for i in itens} <= {d["id"] for d in deps}
    assert all(i["valor"] and i["mes"] and i["data"] and i["fonte"] == es.PAGINA for i in itens)
    assert all(i["documento"][4:6] == "OB" for i in itens)
    assert es.itens_cota(linhas_do_contrato(), [{"id": "1", "nome": "Ninguém", "nomeCivil": "Ninguém"}]) == []


def test_itens_cota_ignora_empenho_e_liquidacao():
    base = {"UnidadeGestora": "ASSEMBLEIA LEGISLATIVA", "SubelementoDespesa": "Reembolso de Despesas – Cotas Parlamentares", "Favorecido": "FULANO DE TAL",
            "Data": "12/02/2026 00:00:00", "HistoricoDocumento": "COTA PARLAMENTAR DO MÊS DE JANEIRO"}
    linhas = [{**base, "Documento": "2026NE1", "ValorPago": "0,0000"}, {**base, "Documento": "2026NL1", "ValorPago": "0,0000"},
              {**base, "Documento": "2026OB1", "ValorPago": "1524,0000"}, {**base, "Documento": "2026OB2", "ValorPago": "-200,0000"}]
    itens = es.itens_cota(linhas, [{"id": "7", "nome": "Fulano", "nomeCivil": "Fulano de Tal"}])
    assert [(i["documento"], i["valor"], i["mes"], i["referencia"]) for i in itens] == [("2026OB1", 1524.0, 2, "2026-01"), ("2026OB2", -200.0, 2, "2026-01")]


def test_itens_diarias_do_contrato():
    deps = deputados_do_contrato(es.e_diaria)
    itens = es.itens_diarias(linhas_do_contrato(), deps)
    assert itens and all(i["valor"] and i["data"] and i["motivo"] for i in itens)


def test_conferir_contrato_despesas():
    assert es._conferir_despesas(amostra("estadual_es_despesas")) == ([], [])
    falhas, _ = es._conferir_despesas({"csv": "Data;UnidadeGestora\n01/01/2026;ASSEMBLEIA LEGISLATIVA"})
    assert any("ValorPago" in f for f in falhas)


def test_ano_fechado(tmp_path):
    hoje = date(2026, 10, 23)
    assert not es.ano_fechado(2024, hoje, tmp_path)
    (tmp_path / "verbas_2024.json").write_text("{}", encoding="utf-8")
    assert es.ano_fechado(2024, hoje, tmp_path)
    (tmp_path / "verbas_2025.json").write_text(json.dumps({"coletadoEm": "2026-02-20"}), encoding="utf-8")
    assert not es.ano_fechado(2025, hoje, tmp_path)
    assert not es.ano_fechado(2025, date(2026, 2, 21), tmp_path)
    (tmp_path / "verbas_2025.json").write_text(json.dumps({"coletadoEm": "2026-03-02"}), encoding="utf-8")
    assert es.ano_fechado(2025, hoje, tmp_path)
    assert not es.ano_fechado(2026, hoje, tmp_path)




def csv_bytes():
    return ("﻿" + amostra("estadual_es_despesas")["csv"].replace("\n", "\r\n") + "\r\n").encode("utf-8")


class Resp:
    def __init__(self, dados=None, conteudo=b"", status=200, falhar_em=None):
        self._dados, self.conteudo, self.status_code, self.falhar_em = dados, conteudo, status, falhar_em

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    def json(self):
        return self._dados

    def iter_content(self, tamanho):
        for i in range(0, len(self.conteudo), 1000):
            if self.falhar_em is not None and i >= self.falhar_em:
                raise comum.PrazoEsgotado("prazo de coleta esgotado")
            yield self.conteudo[i:i + 1000]


class Sessao:
    def __init__(self, pacote, falhar_em=None):
        self.pacote, self.falhar_em, self.pedidos = pacote, falhar_em, []

    def get(self, url, timeout=None, stream=False, headers=None):
        if "package_show" in url:
            return Resp(dados=self.pacote)
        inicio = int(headers["Range"][6:-1]) if headers and "Range" in headers else 0
        self.pedidos.append((url, inicio))
        return Resp(conteudo=csv_bytes()[inicio:], status=206 if inicio else 200, falhar_em=self.falhar_em)


def preparar(tmp_path, monkeypatch, sessao):
    nome = next(l["Favorecido"] for l in linhas_do_contrato() if es.e_cota(l))
    tse = [{"cargo": "DEPUTADO ESTADUAL", "situacao": "eleito", "sequencial": "80", "urna": "Fulano", "nome": nome, "partido": "PDT", "email": None},
           {"cargo": "DEPUTADO FEDERAL", "situacao": "eleito", "sequencial": "9", "urna": "X", "nome": "X"}]
    arquivo = tmp_path / "ES.json"
    arquivo.write_text(json.dumps(tse), encoding="utf-8")
    monkeypatch.setattr(es, "TSE_ARQUIVO", arquivo)
    monkeypatch.setattr(comum, "DADOS", tmp_path / "estaduais")
    monkeypatch.setattr(comum, "sessao", lambda: sessao)
    pasta = tmp_path / "estaduais" / "ES"
    pasta.mkdir(parents=True)
    return pasta


PACOTE = {"result": {"resources": [{"name": "Despesas-2026.csv", "url": "https://dados.es.gov.br/26.csv", "last_modified": "2026-10-22T10:56:36"},
                                   {"name": "Despesas-2023.csv", "url": "https://dados.es.gov.br/23.csv", "last_modified": "2026-10-17T23:10:32"},
                                   {"name": "Despesas-2020.csv", "url": "https://dados.es.gov.br/20.csv", "last_modified": "2026-10-17T19:25:27"}]}}


def test_coletar_grava_e_pula_anos_fechados_e_sem_mudanca(tmp_path, monkeypatch):
    sessao = Sessao(PACOTE)
    pasta = preparar(tmp_path, monkeypatch, sessao)
    (pasta / "verbas_2023.json").write_text(json.dumps({"coletadoEm": "2024-01-01", "itens": []}), encoding="utf-8")
    es.coletar()
    assert sessao.pedidos == [("https://dados.es.gov.br/26.csv", 0)]
    deps = json.loads((pasta / "deputados.json").read_text(encoding="utf-8"))
    assert [d["id"] for d in deps["deputados"]] == ["80"] and deps["host"] is None
    verbas = json.loads((pasta / "verbas_2026.json").read_text(encoding="utf-8"))
    assert verbas["itens"] and all(i["idDeputado"] == "80" for i in verbas["itens"])
    assert verbas["recursoModificadoEm"] == "2026-10-22T10:56:36"
    assert (pasta / "diarias_2026.json").exists() and not (pasta / "parcial_2026.json").exists()
    sessao.pedidos.clear()
    es.coletar()
    assert sessao.pedidos == []


def test_coletar_prazo_guarda_parcial_e_continua_com_range(tmp_path, monkeypatch):
    completo = Sessao(PACOTE)
    pasta = preparar(tmp_path, monkeypatch, completo)
    (pasta / "verbas_2023.json").write_text("{}", encoding="utf-8")
    es.coletar()
    esperado = json.loads((pasta / "verbas_2026.json").read_text(encoding="utf-8"))["itens"]
    (pasta / "verbas_2026.json").unlink()

    cortada = Sessao(PACOTE, falhar_em=len(csv_bytes()) // 2)
    monkeypatch.setattr(comum, "sessao", lambda: cortada)
    es.coletar()
    parcial = json.loads((pasta / "parcial_2026.json").read_text(encoding="utf-8"))
    assert 0 < parcial["offset"] < len(csv_bytes()) and not (pasta / "verbas_2026.json").exists()
    assert csv_bytes()[parcial["offset"] - 1:parcial["offset"]] == b"\n"

    retomada = Sessao(PACOTE)
    monkeypatch.setattr(comum, "sessao", lambda: retomada)
    es.coletar()
    assert retomada.pedidos == [("https://dados.es.gov.br/26.csv", parcial["offset"])]
    assert json.loads((pasta / "verbas_2026.json").read_text(encoding="utf-8"))["itens"] == esperado
    assert not (pasta / "parcial_2026.json").exists()
