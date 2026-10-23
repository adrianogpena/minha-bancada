import json
from datetime import date

import coletar_estadual_pa as pa
import estaduais_comum as comum
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"

DEPUTADOS = [
    {"id": "1024", "nome": "Adriano Coelho", "nomeCivil": "Marco Adriano Alburquerque Coelho"},
    {"id": "1011", "nome": "Ana Cunha", "nomeCivil": "Ana Cunha da Silva"},
    {"id": "1030", "nome": "Delegado Nilton Neves", "nomeCivil": "Nilton Neves"},
    {"id": "1040", "nome": "Dr Wanderlan", "nomeCivil": "Wanderlan Quaresma"},
]


def amostra(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


def test_parse_cartoes_do_contrato():
    pagina = pa.parse_cartoes(amostra("estadual_pa_frequencia")["trecho"])
    assert pagina["totalSessoes"] == 4
    assert pagina["deputados"][0] == {
        "id": "1024", "nome": "Adriano Coelho", "partido": "MDB",
        "foto": "https://alepa.quartertec.com.br/Content/Portal/PerfilAgentePolitico/DEPUTADO_Adriano%20Coelho.png",
        "ficha": "https://alepa.pa.gov.br/Institucional/Deputado/1024", "presente": 3, "licenciado": 1, "ausente": 0}
    assert pa._conferir_frequencia(amostra("estadual_pa_frequencia")) == ([], [])


def test_parse_cartoes_deputado_sem_ficha():
    html = ("card-frequencia-deputados\"><div><img src=\"x.png\" /><h3><b>Fulano (PL)</b></h3>"
            "<p><b>Presente: </b>1</p><p><b>Licenciado: </b>0</p><p><b>Ausente: </b>2</p></div>")
    d = pa.parse_cartoes(html)["deputados"][0]
    assert d["id"] is None and d["ficha"] is None and d["ausente"] == 2
    assert pa.id_deputado(d) == "sem-fulano"


def test_parse_ficha_do_contrato():
    a = amostra("estadual_pa_ficha")
    assert pa.parse_ficha(a["trecho"] + a["email"]) == {"nomeCivil": "Marco Adriano Alburquerque Coelho", "email": "dep.adrianocoelho@alepa.pa.gov.br"}
    assert pa._conferir_ficha(a) == ([], [])


def test_itens_presenca():
    pagina = {"totalSessoes": 4, "deputados": [{"id": "1024", "nome": "Adriano Coelho", "presente": 3, "licenciado": 1, "ausente": 0}]}
    assert pa.itens_presenca(pagina, 2026, 9) == [{"idDeputado": "1024", "periodo": "2026-09", "presente": 3, "ausente": 0, "licenca": 1,
                                                   "totalSessoes": 4, "fonte": pa.FREQUENCIA_URL}]


def test_linhas_dashboard_do_contrato():
    a = amostra("estadual_pa_verba_indenizatoria")
    linhas = pa.linhas_dashboard(a["DataStorageDTO"])
    assert linhas[0]["deputado"] == "Ana Cunha" and linhas[0]["data"] == "2026-10-21" and linhas[0]["conta"] == "INDENIZACAO DE TRANSPORTE"
    assert sorted(linha["valor"] for linha in linhas) == [1607.86, 4238.89]
    assert pa._conferir_dashboard(a) == ([], [])


def test_recortar_dto_mantem_so_celulas_pedidas():
    dto = {"EncodeMaps": {"DataItem1": ["2026-01-02T00:00:00", "2026-01-03T00:00:00"], "DataItem0": ["A", "B"]},
           "Slices": [{"KeyIds": ["DataItem1", "DataItem0"], "ValueIds": {"DataItem3": 0}, "Data": {"[1,1]": {"0": 5.0}, "[0,0]": {"0": 7.0}, "[1,0]": {"0": 9.0}}}]}
    menor = pa.recortar_dto(dto, 2)
    assert pa.linhas_dashboard(menor) == [{"data": "2026-01-02", "deputado": "A", "conta": None, "descricao": None, "valor": 7.0},
                                          {"data": "2026-01-03", "deputado": "B", "conta": None, "descricao": None, "valor": 5.0}]


def test_itens_verba_e_diarias_filtram_ano_e_deputado():
    linhas = [{"data": "2026-03-05", "deputado": "Ana Cunha", "conta": "INDENIZACOES", "descricao": "X", "valor": 10.0},
              {"data": "2025-03-05", "deputado": "Ana Cunha", "conta": "INDENIZACOES", "descricao": "Y", "valor": 20.0},
              {"data": "2026-03-05", "deputado": "Desconhecido", "conta": "INDENIZACOES", "descricao": "Z", "valor": 30.0}]
    ids = pa.ligar({linha["deputado"] for linha in linhas}, DEPUTADOS)
    verba = pa.itens_verba(linhas, ids, 2026)
    assert [(i["idDeputado"], i["mes"], i["valor"], i["fonte"]) for i in verba] == [("1011", 3, 10.0, pa.VERBA_PAGINA)]
    diarias = pa.itens_diarias(linhas, ids, 2026)
    assert [(i["idDeputado"], i["data"], i["motivo"], i["fonte"]) for i in diarias] == [("1011", "2026-03-05", "X", pa.DIARIAS_PAGINA)]


def test_ligar_casa_abreviaturas_e_titulos():
    ligados = pa.ligar(["ADRIANO COELHO", "DELEG. NILTON NEVES", "DR. WANDERLAN", "SEM PAR"], DEPUTADOS)
    assert ligados == {"ADRIANO COELHO": "1024", "DELEG. NILTON NEVES": "1030", "DR. WANDERLAN": "1040"}


def test_parse_gabinetes_do_contrato():
    a = amostra("estadual_pa_verba_gabinete")
    gabinetes = pa.parse_gabinetes(a["html"])
    assert gabinetes[0] == {"gabinete": "ADRIANO COELHO", "referencia": "Setembro/2026", "assessores": 48, "total": 122069.17}
    itens = pa.itens_gabinete(gabinetes, pa.ligar({g["gabinete"] for g in gabinetes}, DEPUTADOS), 2026, 9)
    assert itens[0]["idDeputado"] == "1024" and itens[0]["valor"] == 122069.17 and itens[0]["fonte"] == pa.GABINETE_PAGINA
    assert pa._conferir_gabinete(a) == ([], [])


def test_meses_ate():
    assert list(pa.meses_ate(date(2023, 4, 10))) == [(2023, 2), (2023, 3), (2023, 4)]


class Resposta:
    def __init__(self, texto="", dados=None, ok=True):
        self.text, self._dados, self.ok = texto, dados, ok

    def raise_for_status(self):
        pass

    def json(self):
        return self._dados


class Sessao:
    def __init__(self, tabela_presenca, dto, gabinete_html):
        self.tabela_presenca, self.dto, self.gabinete_html = tabela_presenca, dto, gabinete_html

    def get(self, url, params=None, timeout=None):
        if url == pa.FREQUENCIA_URL:
            return Resposta(self.tabela_presenca)
        if url == pa.DASHBOARD_URL:
            return Resposta(dados={"ItemData": {"DataStorageDTO": self.dto}})
        return Resposta("<span>Nome completo: <b>Marco Adriano</b></span>mailto:a@b.c")

    def post(self, url, data=None, timeout=None):
        if url == pa.FREQUENCIA_URL:
            return Resposta(self.tabela_presenca)
        return Resposta(self.gabinete_html)


def test_coletar_grava_arquivos(tmp_path, monkeypatch):
    trecho = amostra("estadual_pa_frequencia")["trecho"]
    dto = amostra("estadual_pa_verba_indenizatoria")["DataStorageDTO"]
    gabinete = amostra("estadual_pa_verba_gabinete")["html"]
    sessao = Sessao(trecho, dto, f"<table>{gabinete}</table>")
    monkeypatch.setattr(comum, "DADOS", tmp_path)
    monkeypatch.setattr(comum, "sessao", lambda: sessao)
    monkeypatch.setattr(pa, "PRIMEIRO_MES", (date.today().year, date.today().month))
    monkeypatch.setattr(pa, "PRIMEIRO_ANO", date.today().year)
    pa.coletar()
    pasta = tmp_path / "PA"
    deputados = json.loads((pasta / "deputados.json").read_text(encoding="utf-8"))["deputados"]
    assert [d["id"] for d in deputados] == ["1024", "1011"] and deputados[0]["nomeCivil"] == "Marco Adriano"
    presenca = json.loads((pasta / "presenca.json").read_text(encoding="utf-8"))["itens"]
    assert {i["idDeputado"] for i in presenca} == {"1024", "1011"} and presenca[0]["totalSessoes"] == 4
    ano = date.today().year
    verbas = json.loads((pasta / f"verbas_{ano}.json").read_text(encoding="utf-8"))["itens"]
    assert any(i["idDeputado"] == "1011" and i["valor"] == 4238.89 for i in verbas)
    assert (pasta / f"diarias_{ano}.json").exists()
