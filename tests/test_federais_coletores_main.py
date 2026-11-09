import datetime as dt
import json
import types

import pytest
import requests

import coletar_ministros as mi
import coletar_receita as rec
import coletar_relatorias as rel
import coletar_siconfi as sic
import coletar_tribunais as trib
import coletar_tse as tse
import estaduais_comum as comum
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"


def amostra(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


class Resp:
    def __init__(self, corpo=None, status=200, texto=""):
        self.corpo, self.status_code, self.text = corpo, status, texto

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self.corpo


class Roteador:
    def __init__(self, rotas):
        self.rotas, self.chamadas = rotas, []

    def get(self, url, timeout=None, **kw):
        self.chamadas.append((url, kw))
        for trecho, resp in self.rotas.items():
            if trecho in url:
                return resp(kw) if callable(resp) else resp
        raise AssertionError(f"url inesperada {url}")


# ------------------------------------------------------------ coletar_receita.baixar

class Servidor:
    def __init__(self, conteudo, ignora_range=False, falhas=0, cortado=False):
        self.conteudo, self.ignora_range, self.falhas, self.cortado = conteudo, ignora_range, falhas, cortado
        self.heads, self.gets, self.auth, self.headers = [], [], None, {}

    def Session(self):
        return Sessao(self)


class Sessao:
    def __init__(self, srv):
        self.srv, self.headers = srv, {}

    @property
    def auth(self):
        return self.srv.auth

    @auth.setter
    def auth(self, v):
        self.srv.auth = v

    def head(self, url, allow_redirects=None, timeout=None):
        self.srv.heads.append(url)
        dados = self.srv.conteudo.get(url.rsplit("/", 1)[1])
        if dados is None:
            return types.SimpleNamespace(status_code=404, headers={})
        return types.SimpleNamespace(status_code=200, headers={"Content-Length": str(len(dados))})

    def get(self, url, stream=None, timeout=None, headers=None):
        srv = self.srv
        srv.gets.append(headers or {})
        if srv.falhas:
            srv.falhas -= 1
            raise requests.exceptions.ConnectionError("caiu")
        dados = srv.conteudo[url.rsplit("/", 1)[1]]
        inicio = int((headers or {}).get("Range", "bytes=0-")[6:-1] or 0)
        if inicio and not srv.ignora_range:
            corpo, status = dados[inicio:], 206
        else:
            corpo, status = dados, 200
        if srv.cortado:
            corpo = corpo[:-3]
        return Corpo(corpo, status)


class Corpo:
    def __init__(self, corpo, status):
        self.corpo, self.status_code = corpo, status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, n):
        yield self.corpo[:4]
        yield self.corpo[4:]


@pytest.fixture
def receita(tmp_path, monkeypatch):
    monkeypatch.setattr(rec, "BRUTO", tmp_path / "bruto")
    monkeypatch.setattr(rec, "arquivos", lambda: ["Cnaes.zip", "Socios0.zip"])
    pausas = []
    monkeypatch.setattr(rec.time, "sleep", pausas.append)
    monkeypatch.setattr(rec, "TENTATIVAS", 3)

    def usar(srv):
        monkeypatch.setattr(requests, "Session", srv.Session)
        return pausas

    return usar


def test_receita_baixar_grava_arquivos_com_credencial(receita, tmp_path, capsys):
    srv = Servidor({"Cnaes.zip": b"0123456789", "Socios0.zip": b"abcdef"})
    receita(srv)
    rec.baixar("2026-09")
    pasta = tmp_path / "bruto" / "2026-09"
    assert (pasta / "Cnaes.zip").read_bytes() == b"0123456789"
    assert (pasta / "Socios0.zip").read_bytes() == b"abcdef"
    assert not list(pasta.glob("*.tmp"))
    assert srv.auth == (rec.TOKEN, "")
    assert srv.heads == [f"{rec.BASE}/2026-09/Cnaes.zip", f"{rec.BASE}/2026-09/Socios0.zip"]
    saida = capsys.readouterr().out
    assert "Baixando" in saida and "Cnaes.zip" in saida


def test_receita_baixar_pula_http_diferente_de_200(receita, tmp_path, capsys):
    srv = Servidor({"Socios0.zip": b"abcdef"})
    receita(srv)
    rec.baixar("2026-09")
    pasta = tmp_path / "bruto" / "2026-09"
    assert not (pasta / "Cnaes.zip").exists() and (pasta / "Socios0.zip").exists()
    assert "Cnaes.zip: HTTP 404" in capsys.readouterr().err


def test_receita_baixar_ja_baixado_nao_baixa_de_novo(receita, tmp_path, capsys):
    pasta = tmp_path / "bruto" / "2026-09"
    pasta.mkdir(parents=True)
    (pasta / "Cnaes.zip").write_bytes(b"0123456789")
    srv = Servidor({"Cnaes.zip": b"0123456789", "Socios0.zip": b"abcdef"})
    receita(srv)
    rec.baixar("2026-09")
    assert "já baixado: Cnaes.zip" in capsys.readouterr().out
    assert len(srv.gets) == 1


def test_receita_baixar_retoma_download_parcial(receita, tmp_path):
    pasta = tmp_path / "bruto" / "2026-09"
    pasta.mkdir(parents=True)
    (pasta / "Cnaes.tmp").write_bytes(b"0123")
    srv = Servidor({"Cnaes.zip": b"0123456789", "Socios0.zip": b"abcdef"})
    receita(srv)
    rec.baixar("2026-09")
    assert srv.gets[0] == {"Range": "bytes=4-"}
    assert (pasta / "Cnaes.zip").read_bytes() == b"0123456789"
    assert not (pasta / "Cnaes.tmp").exists()


def test_receita_baixar_servidor_ignora_range_recomeca(receita, tmp_path):
    pasta = tmp_path / "bruto" / "2026-09"
    pasta.mkdir(parents=True)
    (pasta / "Cnaes.tmp").write_bytes(b"0123")
    srv = Servidor({"Cnaes.zip": b"0123456789", "Socios0.zip": b"abcdef"}, ignora_range=True)
    receita(srv)
    rec.baixar("2026-09")
    assert (pasta / "Cnaes.zip").read_bytes() == b"0123456789"


def test_receita_baixar_parcial_maior_que_esperado_e_descartado(receita, tmp_path):
    pasta = tmp_path / "bruto" / "2026-09"
    pasta.mkdir(parents=True)
    (pasta / "Cnaes.tmp").write_bytes(b"x" * 50)
    srv = Servidor({"Cnaes.zip": b"0123456789", "Socios0.zip": b"abcdef"})
    receita(srv)
    rec.baixar("2026-09")
    assert srv.gets[0] == {}
    assert (pasta / "Cnaes.zip").read_bytes() == b"0123456789"


def test_receita_baixar_parcial_completo_so_renomeia(receita, tmp_path):
    pasta = tmp_path / "bruto" / "2026-09"
    pasta.mkdir(parents=True)
    (pasta / "Cnaes.tmp").write_bytes(b"0123456789")
    srv = Servidor({"Cnaes.zip": b"0123456789", "Socios0.zip": b"abcdef"})
    receita(srv)
    rec.baixar("2026-09")
    assert (pasta / "Cnaes.zip").read_bytes() == b"0123456789"
    assert len(srv.gets) == 1


def test_receita_baixar_conexao_cai_e_tenta_de_novo(receita, tmp_path, capsys):
    srv = Servidor({"Cnaes.zip": b"0123456789", "Socios0.zip": b"abcdef"}, falhas=2)
    pausas = receita(srv)
    rec.baixar("2026-09")
    assert (tmp_path / "bruto" / "2026-09" / "Cnaes.zip").read_bytes() == b"0123456789"
    assert pausas == [5, 10]
    err = capsys.readouterr().err
    assert "conexão caiu (ConnectionError), tentativa 1/3" in err and "tentativa 2/3" in err


def test_receita_baixar_esgota_tentativas(receita, tmp_path):
    srv = Servidor({"Cnaes.zip": b"0123456789", "Socios0.zip": b"abcdef"}, falhas=99)
    pausas = receita(srv)
    with pytest.raises(OSError, match="Cnaes.zip: não baixou após 3 tentativas"):
        rec.baixar("2026-09")
    assert pausas == [5, 10, 15]
    assert not (tmp_path / "bruto" / "2026-09" / "Cnaes.zip").exists()


def test_receita_baixar_tamanho_diferente_apaga_e_levanta(receita, tmp_path):
    srv = Servidor({"Cnaes.zip": b"0123456789", "Socios0.zip": b"abcdef"}, cortado=True)
    receita(srv)
    with pytest.raises(OSError, match="tamanho diferente do esperado \\(10\\)"):
        rec.baixar("2026-09")
    pasta = tmp_path / "bruto" / "2026-09"
    assert not (pasta / "Cnaes.zip").exists() and not (pasta / "Cnaes.tmp").exists()


# ------------------------------------------------------------ coletar_tse.baixar

class RespZip:
    def __init__(self, status=200):
        self.status, self.pedido = status, None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(f"HTTP {self.status}")

    def iter_content(self, n):
        self.pedido = n
        yield b"PK\x03\x04"
        yield b"dados"


def test_tse_baixar_grava_zip_temporario(monkeypatch, capsys):
    pedidos = []
    resp = RespZip()
    monkeypatch.setattr(tse.requests, "get", lambda url, **kw: pedidos.append((url, kw)) or resp)
    caminho = tse.baixar("https://cdn.exemplo/bem_candidato_2024.zip")
    try:
        assert caminho.suffix == ".zip" and caminho.read_bytes() == b"PK\x03\x04dados"
        url, kw = pedidos[0]
        assert url == "https://cdn.exemplo/bem_candidato_2024.zip"
        assert kw["stream"] is True and kw["timeout"] == 300 and "User-Agent" in kw["headers"]
        assert resp.pedido == 1 << 20
        saida = capsys.readouterr().out
        assert "Baixando https://cdn.exemplo/bem_candidato_2024.zip" in saida and "MB" in saida
    finally:
        caminho.unlink()


def test_tse_baixar_http_erro_propaga(monkeypatch):
    monkeypatch.setattr(tse.requests, "get", lambda url, **kw: RespZip(status=404))
    with pytest.raises(requests.HTTPError, match="404"):
        tse.baixar("https://cdn.exemplo/nao_existe.zip")


# ------------------------------------------------------------ coletar_tribunais.coletar_tribunal

def linha_tse(nome, posse, por):
    return (f'<tr><td><a href="/wiki/{nome.replace(" ", "_")}" title="x">{nome}</a></td><td>{posse}</td><td>{por}</td></tr>')


def pagina_wiki(nomes):
    cab = "<tr><th>Nome</th><th>Posse</th><th>Nomeação</th></tr>"
    linhas = "".join(linha_tse(n, "3 de agosto de 2023", "Lula") for n in nomes)
    return {"parse": {"text": f'<table class="wikitable">{cab}{linhas}</table>'}}


NOMES_TSE = ["Ana Souza Lima", "Bruno Costa Reis", "Carla Dias Melo", "Diego Alves Neto", "Elisa Rocha Prado"]


def test_coletar_tribunal_monta_composicao(monkeypatch, capsys):
    s = Roteador({"Tribunal_Superior_Eleitoral": Resp(pagina_wiki(NOMES_TSE))})
    monkeypatch.setattr(comum, "sessao", lambda *a, **k: s)
    r = trib.coletar_tribunal("TSE", None, "2026-11-03")
    assert r["nome"] == "Tribunal Superior Eleitoral"
    assert r["fonte"] == "https://www.tse.jus.br/institucional/composicao-do-tse"
    assert r["wikipedia"] == "https://pt.wikipedia.org/wiki/Tribunal_Superior_Eleitoral"
    assert r["anteriores"] == [] and len(r["atuais"]) == 5
    primeiro = r["atuais"][0]
    assert primeiro == {"nome": "Ana Souza Lima", "wiki": "Ana_Souza_Lima", "posse": "2023-08-03", "posseTexto": "3 de agosto de 2023",
                        "nomeadoPor": "Lula", "vistoDesde": "2026-11-03"}
    assert s.chamadas[0][0] == trib.WIKI + "Tribunal_Superior_Eleitoral"
    assert "TSE: 5 ministros" in capsys.readouterr().out


def test_coletar_tribunal_fecha_quem_saiu_e_mantem_vistodesde(monkeypatch):
    s = Roteador({"Tribunal_Superior_Eleitoral": Resp(pagina_wiki(NOMES_TSE))})
    monkeypatch.setattr(comum, "sessao", lambda *a, **k: s)
    anterior = {"atuais": [{"nome": "Ana Souza Lima", "vistoDesde": "2025-01-01"}, {"nome": "Zeca Saiu Antes", "vistoDesde": "2025-01-01"}],
                "anteriores": [{"nome": "Velho Ministro", "vistoAte": "2024-01-01"}]}
    r = trib.coletar_tribunal("TSE", anterior, "2026-11-03")
    assert r["atuais"][0]["vistoDesde"] == "2025-01-01" and r["atuais"][1]["vistoDesde"] == "2026-11-03"
    assert [x["nome"] for x in r["anteriores"]] == ["Velho Ministro", "Zeca Saiu Antes"]
    assert r["anteriores"][-1]["vistoAte"] == "2026-11-03"


def test_coletar_tribunal_poucos_ministros_levanta(monkeypatch):
    s = Roteador({"Tribunal_Superior_Eleitoral": Resp(pagina_wiki(NOMES_TSE[:3]))})
    monkeypatch.setattr(comum, "sessao", lambda *a, **k: s)
    with pytest.raises(RuntimeError, match="TSE: só 3 ministros reconhecidos"):
        trib.coletar_tribunal("TSE", None, "2026-11-03")


def test_coletar_tribunal_pagina_sem_tabela_levanta(monkeypatch):
    s = Roteador({"Tribunal_Superior_Eleitoral": Resp({"parse": {"text": "<p>nada</p>"}})})
    monkeypatch.setattr(comum, "sessao", lambda *a, **k: s)
    with pytest.raises(RuntimeError, match="só 0 ministros"):
        trib.coletar_tribunal("TSE", None, "2026-11-03")


def test_coletar_tribunal_http_erro_propaga(monkeypatch):
    s = Roteador({"Tribunal_Superior_Eleitoral": Resp(status=503)})
    monkeypatch.setattr(comum, "sessao", lambda *a, **k: s)
    with pytest.raises(requests.HTTPError):
        trib.coletar_tribunal("TSE", None, "2026-11-03")


# ------------------------------------------------------------ coletar_relatorias.coletar_tcu

def acordao(numero, dia, relator="Ministro A", tipo="Relação", ano=2025):
    return {"numeroAcordao": numero, "anoAcordao": ano, "tipo": tipo, "colegiado": "Plenário", "dataSessao": dia, "relator": relator,
            "urlAcordao": f"https://tcu/{numero}"}


class TcuApi:
    def __init__(self, paginas, status=200):
        self.paginas, self.status, self.pedidos = paginas, status, []

    def get(self, url, timeout=None, params=None, **kw):
        self.pedidos.append(dict(params))
        if self.status != 200:
            return Resp(status=self.status)
        i = params["inicio"] // params["quantidade"]
        return Resp(self.paginas[i] if i < len(self.paginas) else [])


@pytest.fixture
def tcu(tmp_path, monkeypatch):
    monkeypatch.setattr(rel, "PASTA", tmp_path)
    monkeypatch.setattr(rel, "PAGINA_TCU", 2)

    def usar(api):
        monkeypatch.setattr(comum, "sessao", lambda *a, **k: api)
        return api

    return usar


def test_coletar_tcu_primeira_coleta(tcu, tmp_path, capsys):
    api = tcu(TcuApi([
        [acordao(10, "20/06/2025"), acordao(11, "20/06/2025", tipo="Acórdão")],
        [acordao(9, "19/06/2025", relator="Ministro B"), acordao(1, "10/12/2024"), acordao(2, "01/06/2025", relator=" ")],
        [acordao(0, "05/12/2024")],
    ]))
    rel.coletar_tcu("2026-11-03", float("inf"))
    saida = json.loads((tmp_path / "relatorias_tcu.json").read_text(encoding="utf-8"))
    assert saida["coletadoEm"] == "2026-11-03" and saida["fonte"] == rel.TCU_API
    assert saida["dias"] == {"2025-06-19": {"Ministro B": {"Relação": 1}}, "2025-06-20": {"Ministro A": {"Relação": 1, "Acórdão": 1}}}
    assert [x["numero"] for x in saida["recentes"]["Ministro A"]] == [11, 10]
    assert saida["recentes"]["Ministro B"] == [{"numero": 9, "ano": 2025, "tipo": "Relação", "colegiado": "Plenário", "data": "2025-06-19",
                                                 "url": "https://tcu/9"}]
    assert [p["inicio"] for p in api.pedidos] == [0, 2, 4]
    assert "TCU: 6 acórdãos lidos, 2 dias de sessão" in capsys.readouterr().out


def test_coletar_tcu_incremental_releitura_e_mescla(tcu, tmp_path):
    comum.salvar(tmp_path / "relatorias_tcu.json", {
        "dias": {"2025-01-05": {"Ministro A": {"Relação": 3}}, "2025-06-10": {"Ministro A": {"Relação": 9}}},
        "recentes": {"Ministro A": [{"numero": 5, "ano": 2025, "tipo": "Relação", "colegiado": "Plenário", "data": "2025-06-10", "url": "u5"},
                                    {"numero": 10, "ano": 2025, "tipo": "Relação", "colegiado": "Plenário", "data": "2025-06-12", "url": "velha"}]}})
    tcu(TcuApi([
        [acordao(10, "12/06/2025"), acordao(12, "13/06/2025")],
        [acordao(3, "01/05/2025")],
    ]))
    rel.coletar_tcu("2026-11-03", float("inf"))
    saida = json.loads((tmp_path / "relatorias_tcu.json").read_text(encoding="utf-8"))
    assert saida["dias"] == {"2025-01-05": {"Ministro A": {"Relação": 3}}, "2025-06-12": {"Ministro A": {"Relação": 1}},
                             "2025-06-13": {"Ministro A": {"Relação": 1}}}
    nums = [x["numero"] for x in saida["recentes"]["Ministro A"]]
    assert nums == [12, 10, 5]
    assert next(x for x in saida["recentes"]["Ministro A"] if x["numero"] == 10)["url"] == "https://tcu/10"


def test_coletar_tcu_prazo_esgotado_descarta_dia_parcial_e_avisa(tcu, tmp_path, monkeypatch, capsys):
    tcu(TcuApi([[acordao(10, "20/06/2025"), acordao(11, "19/06/2025")], [acordao(12, "18/06/2025")]]))
    relogio = iter([0, 100, 100])
    monkeypatch.setattr(rel, "time", types.SimpleNamespace(monotonic=lambda: next(relogio)))
    rel.coletar_tcu("2026-11-03", 50)
    saida = json.loads((tmp_path / "relatorias_tcu.json").read_text(encoding="utf-8"))
    assert list(saida["dias"]) == ["2025-06-20"]
    assert "prazo esgotado em 2 acórdãos; só as sessões depois de 2025-06-19 foram gravadas" in capsys.readouterr().err


def test_coletar_tcu_sem_tempo_nao_le_nada_e_grava_vazio(tcu, tmp_path, capsys):
    api = tcu(TcuApi([[acordao(10, "20/06/2025")]]))
    rel.coletar_tcu("2026-11-03", -1)
    assert api.pedidos == []
    saida = json.loads((tmp_path / "relatorias_tcu.json").read_text(encoding="utf-8"))
    assert saida["dias"] == {} and saida["recentes"] == {}
    assert "prazo esgotado" in capsys.readouterr().err


def test_coletar_tcu_http_erro_nao_grava(tcu, tmp_path):
    tcu(TcuApi([], status=500))
    with pytest.raises(requests.HTTPError):
        rel.coletar_tcu("2026-11-03", float("inf"))
    assert not (tmp_path / "relatorias_tcu.json").exists()


# ------------------------------------------------------------ coletar_relatorias.coletar_stj

def recurso(id_, nome, mod, formato="JSON"):
    return {"id": id_, "name": nome, "format": formato, "last_modified": mod, "url": f"https://stj/{id_}.json"}


def espelho(relator, dia):
    return {"ministroRelator": relator, "dataDecisao": dia}


@pytest.fixture
def stj(tmp_path, monkeypatch):
    monkeypatch.setattr(rel, "PASTA", tmp_path)
    monkeypatch.setattr(rel, "STJ_ORGAOS", ["corte-especial", "primeira-turma"])

    def usar(rotas):
        r = Roteador(rotas)
        monkeypatch.setattr(comum, "sessao", lambda *a, **k: r)
        return r

    return usar


def pacote(*recursos):
    return Resp({"result": {"resources": list(recursos)}})


def test_coletar_stj_le_recursos_novos_e_filtra_nome_formato_e_ano(stj, tmp_path, capsys):
    api = stj({
        "espelhos-de-acordaos-corte-especial": pacote(
            recurso("r1", "20230115.json", "m1"), recurso("r2", "20220101.json", "m"), recurso("r3", "20230201.csv", "m", "CSV"),
            recurso("r4", "dicionario.json", "m")),
        "espelhos-de-acordaos-primeira-turma": pacote(recurso("r5", "20240301.json", "m5")),
        "https://stj/r1.json": Resp([espelho("Min X", "20230110"), espelho("Min X", "20230111"), espelho("Min Y", "20230112"),
                                      espelho("", "20230112"), espelho("Min Z", "2023")]),
        "https://stj/r5.json": Resp([espelho("Min X", "20240301")]),
    })
    rel.coletar_stj("2026-11-03", float("inf"))
    saida = json.loads((tmp_path / "relatorias_stj.json").read_text(encoding="utf-8"))
    assert saida["coletadoEm"] == "2026-11-03" and saida["fonte"].endswith("espelhos-de-acordaos-<órgão julgador>")
    assert saida["recursos"] == {
        "r1": {"modificado": "m1", "nome": "20230115.json", "orgao": "corte-especial", "contagem": {"Min X": {"2023": 2}, "Min Y": {"2023": 1}}},
        "r5": {"modificado": "m5", "nome": "20240301.json", "orgao": "primeira-turma", "contagem": {"Min X": {"2024": 1}}}}
    assert sorted(u for u, _ in api.chamadas if u.startswith("https://stj/r")) == ["https://stj/r1.json", "https://stj/r5.json"]
    assert "STJ: 2 arquivos lidos, 2 no total" in capsys.readouterr().out


def test_coletar_stj_so_rele_recurso_modificado(stj, tmp_path, capsys):
    comum.salvar(tmp_path / "relatorias_stj.json", {"recursos": {
        "r1": {"modificado": "m1", "nome": "20230115.json", "orgao": "corte-especial", "contagem": {"Antigo": {"2023": 7}}},
        "r5": {"modificado": "velho", "nome": "20240301.json", "orgao": "primeira-turma", "contagem": {"Antigo": {"2024": 7}}}}})
    api = stj({
        "espelhos-de-acordaos-corte-especial": pacote(recurso("r1", "20230115.json", "m1")),
        "espelhos-de-acordaos-primeira-turma": pacote(recurso("r5", "20240301.json", "m5-novo")),
        "https://stj/r5.json": Resp([espelho("Min X", "20240301")]),
    })
    rel.coletar_stj("2026-11-03", float("inf"))
    recursos = json.loads((tmp_path / "relatorias_stj.json").read_text(encoding="utf-8"))["recursos"]
    assert recursos["r1"]["contagem"] == {"Antigo": {"2023": 7}}
    assert recursos["r5"]["modificado"] == "m5-novo" and recursos["r5"]["contagem"] == {"Min X": {"2024": 1}}
    assert not any(u == "https://stj/r1.json" for u, _ in api.chamadas)
    assert "STJ: 1 arquivos lidos, 2 no total" in capsys.readouterr().out


def test_coletar_stj_erro_em_orgao_e_em_arquivo_so_avisa(stj, tmp_path, capsys):
    stj({
        "espelhos-de-acordaos-corte-especial": Resp(status=500),
        "espelhos-de-acordaos-primeira-turma": pacote(recurso("r5", "20240301.json", "m5"), recurso("r6", "20240401.json", "m6")),
        "https://stj/r5.json": Resp(status=502),
        "https://stj/r6.json": Resp([espelho("Min X", "20240401")]),
    })
    rel.coletar_stj("2026-11-03", float("inf"))
    recursos = json.loads((tmp_path / "relatorias_stj.json").read_text(encoding="utf-8"))["recursos"]
    assert list(recursos) == ["r6"]
    err = capsys.readouterr().err
    assert "relatorias: STJ corte-especial:" in err and "relatorias: STJ primeira-turma 20240301.json:" in err


def test_coletar_stj_prazo_esgotado_deixa_pendentes(stj, tmp_path, capsys):
    api = stj({
        "espelhos-de-acordaos-corte-especial": pacote(recurso("r1", "20230115.json", "m1")),
        "espelhos-de-acordaos-primeira-turma": pacote(recurso("r5", "20240301.json", "m5")),
    })
    rel.coletar_stj("2026-11-03", -1)
    assert json.loads((tmp_path / "relatorias_stj.json").read_text(encoding="utf-8"))["recursos"] == {}
    assert not any(u.startswith("https://stj/r") for u, _ in api.chamadas)
    cap = capsys.readouterr()
    assert "STJ: 0 arquivos lidos, 0 no total" in cap.out
    assert "relatorias: STJ: 2 arquivos ficaram para a próxima coleta" in cap.err


# ------------------------------------------------------------ coletar_ministros.coletar_senado e coletar_licencas

@pytest.fixture
def ministros(tmp_path, monkeypatch):
    monkeypatch.setattr(mi, "PASTA", tmp_path)

    def usar(rotas):
        r = Roteador(rotas)
        monkeypatch.setattr(mi, "S", r)
        return r

    return usar


def test_coletar_senado_filtra_e_grava(ministros, tmp_path, capsys):
    processos = amostra("senado_requerimentos")
    outro = {**processos[0], "id": 999999, "tipoConteudo": "Homenagem de pesar"}
    api = ministros({"processo?sigla=RQS&ano=2026": Resp(processos + [outro])})
    mi.coletar_senado(2026, "2026-11-03")
    saida = json.loads((tmp_path / "senado_2026.json").read_text(encoding="utf-8"))
    url = f"{mi.SENADO}/processo?sigla=RQS&ano=2026"
    assert api.chamadas[0][0] == url
    assert saida["coletadoEm"] == "2026-11-03" and saida["fonte"] == url
    assert set(saida["itens"]) == {str(p["id"]) for p in processos} and "999999" not in saida["itens"]
    assert f"Senado 2026: {len(saida['itens'])} requerimentos a ministro" in capsys.readouterr().out


def test_coletar_senado_ano_encerrado_com_arquivo_nao_baixa(ministros, tmp_path):
    comum.salvar(tmp_path / "senado_2023.json", {"itens": {"1": {}}})
    api = ministros({})
    mi.coletar_senado(2023, "2026-11-03")
    assert api.chamadas == []
    assert json.loads((tmp_path / "senado_2023.json").read_text(encoding="utf-8")) == {"itens": {"1": {}}}


def test_coletar_senado_ano_encerrado_sem_arquivo_baixa(ministros, tmp_path):
    ministros({"ano=2023": Resp([])})
    mi.coletar_senado(2023, "2026-11-03")
    assert json.loads((tmp_path / "senado_2023.json").read_text(encoding="utf-8"))["itens"] == {}


def test_coletar_senado_http_erro_nao_grava(ministros, tmp_path):
    ministros({"processo": Resp(status=500)})
    with pytest.raises(requests.HTTPError):
        mi.coletar_senado(2026, "2026-11-03")
    assert not (tmp_path / "senado_2026.json").exists()


def test_coletar_licencas_junta_senado_e_camara(ministros, tmp_path, monkeypatch, capsys):
    afastados = amostra("senado_afastados")
    esperado = mi.afastamentos_senado(afastados)
    assert esperado
    vazia = {"ListaParlamentarEmExercicio": {"Parlamentares": {"Parlamentar": []}}}
    api = ministros({"senador/lista/atual.json": Resp(vazia), "senador/lista/afastados.json": Resp(afastados)})
    camara = {"2": {"nome": "Min", "historico": [{"data": "2025-03-10"}]}}
    monkeypatch.setattr(mi, "licencas_camara", lambda: camara)
    mi.coletar_licencas("2026-11-03")
    saida = json.loads((tmp_path / "licencas.json").read_text(encoding="utf-8"))
    assert [u for u, _ in api.chamadas] == [f"{mi.SENADO}/senador/lista/atual.json", f"{mi.SENADO}/senador/lista/afastados.json"]
    assert saida["coletadoEm"] == "2026-11-03" and saida["camara"] == camara and saida["senado"] == esperado
    assert saida["fonte"] == {"camara": f"{mi.API}/deputados/{{id}}/historico", "senado": f"{mi.SENADO}/senador/lista/afastados.json"}
    assert f"Licenças: 1 deputados e {len(esperado)} senadores afastados" in capsys.readouterr().out


def test_coletar_licencas_http_erro_nao_grava(ministros, tmp_path, monkeypatch):
    ministros({"senador/lista": Resp(status=503)})
    monkeypatch.setattr(mi, "licencas_camara", lambda: pytest.fail("não deveria chegar na Câmara"))
    with pytest.raises(requests.HTTPError):
        mi.coletar_licencas("2026-11-03")
    assert not (tmp_path / "licencas.json").exists()


# ------------------------------------------------------------ coletar_siconfi.main

RGF = [{"instituicao": "Assembleia Legislativa do Estado do Amapá", "co_poder": "L", "cod_conta": "DespesaComPessoalTotal", "coluna": "Valor",
        "valor": 153592169.43}]
DCA = [{"cod_conta": "TotalDespesas", "coluna": "Despesas Liquidadas", "conta": "01 - Legislativa", "valor": 100.5}]


class SiconfiApi:
    def __init__(self, status=200):
        self.chamadas, self.status = [], status

    def get(self, endereco, timeout=None):
        self.chamadas.append(endereco)
        if self.status != 200:
            return Resp(status=self.status)
        if "/dca?" in endereco:
            itens = DCA if "an_exercicio=2025" in endereco else []
        else:
            itens = RGF if ("an_exercicio=2025" in endereco and "in_periodicidade=Q" in endereco and "nr_periodo=3" in endereco
                            and "co_poder=L" in endereco) else []
        return Resp({"items": itens, "hasMore": False})


@pytest.fixture
def siconfi(tmp_path, monkeypatch):
    monkeypatch.setattr(sic, "DADOS", tmp_path)
    monkeypatch.setattr(sic, "dt", types.SimpleNamespace(date=type("D", (dt.date,), {"today": classmethod(lambda cls: dt.date(2026, 3, 1))})))

    def usar(argv, api):
        monkeypatch.setattr(sic.sys, "argv", ["coletar_siconfi.py", *argv])
        monkeypatch.setattr(comum, "sessao", lambda *a, **k: api)
        return api

    return usar


def test_siconfi_main_uf_pelo_argumento_em_minusculas(siconfi, tmp_path, capsys):
    api = siconfi(["ap"], SiconfiApi())
    sic.main()
    gravado = json.loads((tmp_path / "AP.json").read_text(encoding="utf-8"))
    assert gravado["uf"] == "AP" and gravado["coletadoEm"] == "2026-03-01" and list(gravado["anos"]) == ["2025"]
    assert gravado["anos"]["2025"]["poderes"][0]["dtp"] == 153592169.43
    assert gravado["anos"]["2025"]["legislativa"]["legislativa"]["liquidada"] == 100.5
    assert [p.name for p in tmp_path.glob("*.json")] == ["AP.json"]
    assert all("id_ente=16" in c for c in api.chamadas)
    assert "AP: 2025 (1)" in capsys.readouterr().out


def test_siconfi_main_uf_invalida_avisa_e_segue(siconfi, tmp_path, capsys):
    siconfi(["xx", "AP"], SiconfiApi())
    sic.main()
    cap = capsys.readouterr()
    assert "AVISO: SICONFI XX:" in cap.err
    assert [p.name for p in tmp_path.glob("*.json")] == ["AP.json"]
    assert "AP: 2025 (1)" in cap.out


def test_siconfi_main_sem_argumento_percorre_todas_as_ufs(siconfi, tmp_path, capsys):
    api = siconfi([], SiconfiApi())
    sic.main()
    saida = capsys.readouterr().out.splitlines()
    assert len(saida) == len(sic.UFS) == 27
    assert saida[0].startswith("RO: ") and saida[-1].startswith("DF: ")
    ente_ap = f"id_ente={sic.UFS['AP']}"
    assert any(ente_ap in c for c in api.chamadas)
    assert len(list(tmp_path.glob("*.json"))) == len(sic.UFS)


def test_siconfi_main_erro_de_rede_avisa_e_nao_grava(siconfi, tmp_path, capsys):
    siconfi(["AP", "SP"], SiconfiApi(status=500))
    sic.main()
    cap = capsys.readouterr()
    assert cap.err.count("AVISO: SICONFI ") == 2 and "SICONFI AP:" in cap.err and "SICONFI SP:" in cap.err
    assert not list(tmp_path.glob("*.json"))
