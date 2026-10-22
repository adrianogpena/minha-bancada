import json

import coletar_estadual_mt as mt
import estaduais_comum as comum
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"

ELEITOS = [{"sequencial": "1", "urna": "Beto Dois A Um", "nome": "Alberto Machado", "partido": "PL", "email": "beto@x.com"}]


def amostra(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


def servidor(matricula, nome, lotacao, situacao="ATIVO", cargo="DEPUTADO ESTADUAL"):
    return {"matricula": matricula, "nome": nome, "descricaoLotacao": lotacao, "situacao": situacao, "descricaoCargo": cargo}


def test_deputados_ativos_filtra_cargo_e_situacao():
    lista = [servidor(1, "A", "x"), servidor(2, "B", "x", situacao="EXONERADO"), servidor(3, "C", "x", cargo="ASSESSOR PARLAMENTAR")]
    assert [s["matricula"] for s in mt.deputados_ativos(lista)] == [1]


def test_deputados_ativos_do_contrato():
    assert mt.deputados_ativos(amostra("estadual_mt_servidores")["content"])
    assert mt._conferir_servidores(amostra("estadual_mt_servidores")) == ([], [])


def test_nome_do_gabinete():
    assert mt.nome_do_gabinete('GAB DEP FABIO TARDIN "FABINHO"') == "Fabio Tardin Fabinho"
    assert mt.nome_do_gabinete("WILSON SANTOS") == "Wilson Santos"
    assert mt.nome_do_gabinete("GAB DEP JULIO DE CAMPOS") == "Julio de Campos"


def test_montar_deputados_usa_tse_quando_o_nome_civil_casa():
    servidores = [servidor(100176, "ALBERTO MACHADO", "GAB DEP BETO DOIS A UM"), servidor(100213, "FRANCISCO GUARNIERI DE LIMA", "GAB DEP CHICO GUARNIERI")]
    a, b = mt.montar_deputados(servidores, ELEITOS)
    assert a["nome"] == "Beto Dois A Um" and a["partido"] == "PL" and a["email"] == "beto@x.com" and a["id"] == "100176"
    assert a["nomeCivil"] == "Alberto Machado" and a["fonte"].endswith("/MT/1")
    assert b["nome"] == "Chico Guarnieri" and b["nomeCivil"] == "Francisco Guarnieri de Lima" and b["partido"] is None and b["fonte"].endswith("/servidores")


def test_itens_remuneracao_do_contrato():
    r = amostra("estadual_mt_remuneracao")
    itens = mt.itens_remuneracao({"dadosFinanceiros": r["dadosFinanceiros"]}, "7", r["ano"])
    assert itens and all(i["idDeputado"] == "7" and 1 <= i["mes"] <= 12 for i in itens)
    assert itens[0]["liquido"] == round(itens[0]["bruto"] - itens[0]["componentes"]["descontos"], 2)
    assert mt._conferir_remuneracao(r) == ([], [])


def test_itens_remuneracao_ignora_outro_ano():
    detalhe = {"dadosFinanceiros": [{"anoCompetencia": 2025, "mesCompetencia": 1, "vencimentos": 10.0, "descontos": 2.0}]}
    assert mt.itens_remuneracao(detalhe, "1", 2026) == []
    assert mt.itens_remuneracao({}, "1", 2026) == []


def test_itens_diarias_so_de_deputados():
    registros = amostra("estadual_mt_diarias")["content"]
    nome = registros[0]["nome"]
    deputados = [{"id": "9", "nome": "X", "nomeCivil": nome.title()}]
    itens = mt.itens_diarias(registros, deputados)
    assert itens and all(i["idDeputado"] == "9" for i in itens)
    primeiro = itens[0]
    assert primeiro["fonte"] == f"{mt.PORTAL}diarias" and primeiro["data"] and primeiro["valor"] is not None
    assert "\n" not in (primeiro["motivo"] or "")
    assert mt.itens_diarias(registros, [{"id": "9", "nome": "Y", "nomeCivil": "Outra Pessoa"}]) == []
    assert mt._conferir_diarias(amostra("estadual_mt_diarias")) == ([], [])


def test_coletar_grava_deputados_remuneracao_e_diarias(tmp_path, monkeypatch):
    ano = mt.date.today().year
    sv = servidor(100176, "ALBERTO MACHADO", "GAB DEP BETO DOIS A UM")
    detalhe = {"dadosFinanceiros": [{"anoCompetencia": ano, "mesCompetencia": 1, "vencimentos": 100.0, "descontos": 20.0, "salarioBase": 80.0,
                                      "outrosProventos": 20.0, "descricaoTipoFolha": "Folha Normal"}]}
    diaria = {"nome": "ALBERTO MACHADO", "dataSaida": f"{ano}-02-01", "dataRetorno": f"{ano}-02-02", "destino": "BRASILIA / DF", "valorDiarias": 500.0,
              "valorPassagem": 0.0, "quantidadeDiarias": 2.0, "motivo": "REUNIAO", "displayEmpenho": "1/2026", "valorAnulado": 0.0}

    class Resp:
        def __init__(self, dados, status=200):
            self.dados, self.status_code = dados, status

        def raise_for_status(self):
            pass

        def json(self):
            return self.dados

    class Sessao:
        def get(self, url, params=None, headers=None, timeout=None):
            if url.endswith("/servidores"):
                return Resp({"content": [sv], "last": True})
            if url.endswith("/diarias"):
                return Resp({"content": [diaria], "last": True})
            if url.endswith("/servidores/100176"):
                return Resp({}, 404) if headers["exercicio"] == "2023" else Resp(detalhe)
            raise AssertionError(url)

    arquivo = tmp_path / "MT.json"
    arquivo.write_text(json.dumps([{"cargo": "DEPUTADO ESTADUAL", "situacao": "eleito", **ELEITOS[0]}]), encoding="utf-8")
    monkeypatch.setattr(mt, "TSE_ARQUIVO", arquivo)
    monkeypatch.setattr(comum, "DADOS", tmp_path / "estaduais")
    monkeypatch.setattr(comum, "sessao", lambda: Sessao())
    mt.coletar()
    pasta = tmp_path / "estaduais" / "MT"
    deps = json.loads((pasta / "deputados.json").read_text(encoding="utf-8"))
    assert deps["host"] is None and [d["nome"] for d in deps["deputados"]] == ["Beto Dois A Um"]
    rem = json.loads((pasta / f"remuneracao_{ano}.json").read_text(encoding="utf-8"))
    assert rem["itens"][0]["liquido"] == 80.0
    assert json.loads((pasta / "remuneracao_2023.json").read_text(encoding="utf-8"))["itens"] == []
    dia = json.loads((pasta / f"diarias_{ano}.json").read_text(encoding="utf-8"))
    assert dia["itens"][0]["idDeputado"] == "100176" and dia["itens"][0]["valor"] == 500.0
