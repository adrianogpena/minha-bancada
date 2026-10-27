import datetime as dt
import json
import zipfile

import pytest

import coletar_tse as t


@pytest.mark.parametrize("v,esperado", [
    ("  texto ", "texto"), ("", None), (None, None), ("#NULO#", None), ("#NULO", None),
    ("-1", None), ("-3", None), ("-4", None), ("#NE", None), ("#NE#", None), ("0", "0"),
])
def test_limpo(v, esperado):
    assert t.limpo(v) == esperado


@pytest.mark.parametrize("v,esperado", [
    ("1.234,56", 1234.56), ("1234.5", 1234.5), ("0,5", 0.5), ("", 0.0), (None, 0.0), ("abc", 0.0), ("12", 12.0),
])
def test_numero(v, esperado):
    assert t.numero(v) == esperado


def test_titulo():
    assert t.titulo("SÃO JOSÉ DOS CAMPOS") == "São José dos Campos"
    assert t.titulo("DE OLHO") == "De Olho"  # preposição na primeira posição fica maiúscula
    assert t.titulo("") == ""
    assert t.titulo(None) is None


def test_frase():
    assert t.frase("SUPERIOR COMPLETO") == "Superior completo"
    assert t.frase("") == ""
    assert t.frase(None) is None


@pytest.mark.parametrize("v,esperado", [
    ("https://instagram.com/fulano", "https://instagram.com/fulano"),
    ("instagram.com/fulano", "https://instagram.com/fulano"),
    ("@fulano.com/x", "https://fulano.com/x"),
    ("@fulano", None),          # sem domínio
    ("#NULO#", None),
    ("", None),
    (None, None),
    ("texto solto", None),
])
def test_url_rede(v, esperado):
    assert t.url_rede(v) == esperado


def zip_com(tmp_path, arquivos: dict[str, str]):
    caminho = tmp_path / "x.zip"
    with zipfile.ZipFile(caminho, "w") as z:
        for nome, conteudo in arquivos.items():
            z.writestr(nome, conteudo.encode("latin-1"))
    return caminho


def test_linhas_csv_le_latin1_com_ponto_e_virgula(tmp_path):
    z = zip_com(tmp_path, {"a_SP.csv": '"NM";"UF"\n"JOSÉ";"SP"\n'})
    assert list(t.linhas_csv(z)) == [{"NM": "JOSÉ", "UF": "SP"}]


def test_linhas_csv_prefere_arquivo_brasil(tmp_path):
    z = zip_com(tmp_path, {"a_SP.csv": '"NM"\n"x"\n', "a_BRASIL.csv": '"NM"\n"y"\n', "leia.txt": "ignorar"})
    assert list(t.linhas_csv(z)) == [{"NM": "y"}]


def marca(tmp_path, monkeypatch, ano, **info):
    monkeypatch.setattr(t, "DADOS", tmp_path)
    (tmp_path / str(ano)).mkdir()
    (tmp_path / str(ano) / "_coleta.json").write_text(json.dumps(info))


def test_precisa_coletar_sem_marca(tmp_path, monkeypatch):
    monkeypatch.setattr(t, "DADOS", tmp_path)
    assert t.precisa_coletar(2022, False)


def test_precisa_coletar_forcar(tmp_path, monkeypatch):
    marca(tmp_path, monkeypatch, 2022, versao=t.VERSAO)
    assert t.precisa_coletar(2022, True)


def test_precisa_coletar_versao_antiga(tmp_path, monkeypatch):
    marca(tmp_path, monkeypatch, 2022, versao=t.VERSAO - 1)
    assert t.precisa_coletar(2022, False)


def test_precisa_coletar_ano_encerrado_em_cache(tmp_path, monkeypatch):
    marca(tmp_path, monkeypatch, 2022, versao=t.VERSAO)
    assert not t.precisa_coletar(2022, False)


def test_precisa_coletar_ano_em_andamento_depende_da_idade(tmp_path, monkeypatch):
    agora = dt.datetime.now(dt.UTC)
    marca(tmp_path, monkeypatch, t.ANO_EM_ANDAMENTO, versao=t.VERSAO, coletadoEm=agora.isoformat())
    assert not t.precisa_coletar(t.ANO_EM_ANDAMENTO, False)
    velho = agora - dt.timedelta(days=t.DIAS_ENTRE_ATUALIZACOES + 1)
    marca_arq = tmp_path / str(t.ANO_EM_ANDAMENTO) / "_coleta.json"
    marca_arq.write_text(json.dumps({"versao": t.VERSAO, "coletadoEm": velho.isoformat()}))
    assert t.precisa_coletar(t.ANO_EM_ANDAMENTO, False)


def test_coletar_ano_falha_com_colunas_ausentes(tmp_path, monkeypatch):
    monkeypatch.setattr(t, "DADOS", tmp_path)
    z = zip_com(tmp_path, {"consulta_cand_2022_BRASIL.csv": '"SQ_CANDIDATO";"DS_CARGO"\n"1";"PREFEITO"\n'})
    monkeypatch.setattr(t, "baixar", lambda url: z)
    with pytest.raises(SystemExit, match="Colunas ausentes"):
        t.coletar_ano(2022)


def test_main_registra_falha_sem_derrubar(monkeypatch, tmp_path):
    monkeypatch.setattr(t, "DADOS", tmp_path)
    monkeypatch.setattr(t, "AVISOS", 0)
    monkeypatch.setattr("sys.argv", ["coletar_tse.py", "--anos", "2022"])

    def explode(ano):
        raise RuntimeError("rede caiu")

    monkeypatch.setattr(t, "coletar_ano", explode)
    t.main()
    assert t.AVISOS == 1


def test_precisa_coletar_ano_em_andamento_olha_o_last_modified(tmp_path, monkeypatch):
    agora = dt.datetime.now(dt.UTC).isoformat()
    datas = {"consulta_cand/consulta_cand_2026.zip": "Sun, 25 Oct 2026 15:37:01 GMT"}
    marca(tmp_path, monkeypatch, t.ANO_EM_ANDAMENTO, versao=t.VERSAO, coletadoEm=agora, modificados=datas)
    assert not t.precisa_coletar(t.ANO_EM_ANDAMENTO, False, datas)
    assert not t.precisa_coletar(t.ANO_EM_ANDAMENTO, False, None)
    assert t.precisa_coletar(t.ANO_EM_ANDAMENTO, False, {"consulta_cand/consulta_cand_2026.zip": "Mon, 26 Oct 2026 20:00:00 GMT"})


def test_modificados_no_cdn_devolve_none_se_falhar(monkeypatch):
    def falha(*a, **k):
        raise t.requests.ConnectionError("sem rede")
    monkeypatch.setattr(t.requests, "head", falha)
    assert t.modificados_no_cdn(2026) is None
