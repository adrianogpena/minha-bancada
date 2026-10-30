import json
from pathlib import Path

import coletar_leis
import gerar_proposicoes
import leis
from gerar import TIPOS_PROJETO, destino_projeto

PAGINA = (Path(__file__).parent / "fixtures" / "leis" / "lexml_lei_9250.html").read_text(encoding="utf-8")


def test_citacoes_com_data_completa():
    t = ("Altera a Lei nº 9.250 de 26 de dezembro de 1995, o Decreto-Lei nº 2.848, de 7 de dezembro de 1940 (Código Penal), "
         "a Medida Provisória nº 2.200-2, de 24 de agosto de 2001, a Lei nº 8.080/90 e a Constituição Federal; repete a Lei nº 9.250, de 26 de dezembro de 1995.")
    achadas = leis.citacoes(t)
    assert [(l["rotulo"], l["urn"]) for l in achadas] == [
        ("Lei nº 9.250/1995", "br:federal:lei:1995-12-26;9250"),
        ("Decreto-Lei nº 2.848/1940", "br:federal:decreto.lei:1940-12-07;2848"),
        ("Medida Provisória nº 2.200-2/2001", "br:federal:medida.provisoria:2001-08-24;2200-2"),
        ("Constituição Federal de 1988", "br:federal:constituicao:1988-10-05;1988")]   # a Lei 8.080/90 não tem data: não liga
    assert achadas[0]["id"] == leis.citacoes("Lei nº 9.250, de 26 de dezembro de 1995")[0]["id"]   # id só depende da URN
    assert leis.url_lexml(achadas[0]["urn"]) == "https://www.lexml.gov.br/urn/urn:lex:br:federal:lei:1995-12-26;9250"
    assert leis.citacoes(None) == [] and leis.citacoes("Lei de 1º de maio de 2000") == []


def test_ler_pagina_do_lexml():
    assert coletar_leis.ler_pagina(PAGINA) == {
        "ementa": "Altera a legislação do imposto de renda das pessoas físicas e dá outras providências.",
        "planalto": "http://legislacao.planalto.gov.br/legisla/legislacao.nsf/websearch?openagent&tipo=LEI&codigo=9.250&ementa=2&data=19951226"}


class Resp:
    text = PAGINA

    def raise_for_status(self):
        pass


class Sessao:
    def __init__(self):
        self.urls = []

    def get(self, url, **kw):
        self.urls.append(url)
        return Resp()


def test_coletar_so_consulta_lei_nova(tmp_path, monkeypatch):
    monkeypatch.setattr(coletar_leis, "PAUSA", 0)
    (tmp_path / "proposicoes_cadastro").mkdir()
    (tmp_path / "proposicoes_cadastro" / "2026.json").write_text(json.dumps(
        {"1": ["PL", 1, "Altera a Lei nº 9.250, de 26 de dezembro de 1995."], "2": ["PL", 2, "Sem lei."]}), encoding="utf-8")
    s = Sessao()
    cache = coletar_leis.coletar(tmp_path, s)
    [(i, lei)] = cache.items()
    assert lei["rotulo"] == "Lei nº 9.250/1995" and lei["ementa"].startswith("Altera a legislação") and len(s.urls) == 1
    coletar_leis.coletar(tmp_path, s)
    assert len(s.urls) == 1   # já tem ementa: não consulta de novo


def test_ficha_traz_ementa_inteira_e_leis(tmp_path):
    longa = "Altera a Lei nº 9.250, de 26 de dezembro de 1995, " + "para algo muito longo " * 12
    deps = {1: {"nome": "Ana", "partido": "PT", "uf": "SP", "proposicoes": [{"id": 5, "tipo": "PL", "numero": 9, "ano": 2026, "ementa": longa}]}}
    detalhes = {"5": {"regime": ".", "tramitacao": "Apresentação", "dataSituacao": "2026-10-29", "ementaDetalhada": "Detalhe",
                      "inteiroTeor": "https://www.camara.leg.br/x", "apensadoA": "7"}}
    lei = leis.citacoes(longa)[0]
    gerar_proposicoes.gerar(tmp_path, deps, detalhes, {}, {}, {}, [], {}, [], TIPOS_PROJETO, destino_projeto, {},
                            {"5": ["Saúde"]}, {lei["id"]: {"ementa": "Resumo oficial", "planalto": "https://p"}})
    lido = lambda n: json.loads((tmp_path / n).read_text(encoding="utf-8"))
    ficha = lido("proposicao/c-2026.json")["5"]
    assert ficha["em"] == longa.strip() and len(lido("proposicoes.json")[0]["e"]) == gerar_proposicoes.TAMANHO_EMENTA
    assert ficha["ed"] == "Detalhe" and ficha["tm"] == ["Saúde"] and ficha["pr"] == "7" and ficha["tx"] == "https://www.camara.leg.br/x"
    assert "rg" not in ficha   # regime "." é vazio na Câmara
    assert ficha["ls"] == [lei["id"]]
    assert lido("leis.json") == {lei["id"]: {"r": "Lei nº 9.250/1995", "u": leis.url_lexml(lei["urn"]), "e": "Resumo oficial", "p": "https://p"}}
