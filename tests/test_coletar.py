import datetime as dt

import pytest

import coletar


class RespostaFalsa:
    def __init__(self, dados, ok=True, status=200, url="http://x"):
        self._dados, self.ok, self.status_code, self.url, self.text = dados, ok, status, url, "corpo"

    def json(self):
        return self._dados


# ---------------------------------------------------------------- HTTP

def test_get_monta_url_e_devolve_json(monkeypatch):
    chamadas = []
    monkeypatch.setattr(coletar.S, "get", lambda url, params=None, timeout=None: chamadas.append((url, params)) or RespostaFalsa({"dados": [1]}))
    assert coletar.get("/deputados", ano=2024) == {"dados": [1]}
    assert chamadas == [(f"{coletar.API}/deputados", {"ano": 2024})]


def test_get_url_absoluta_nao_recebe_prefixo(monkeypatch):
    chamadas = []
    monkeypatch.setattr(coletar.S, "get", lambda url, params=None, timeout=None: chamadas.append(url) or RespostaFalsa({}))
    coletar.get("https://outro.org/pagina2")
    assert chamadas == ["https://outro.org/pagina2"]


def test_get_erro_http_levanta(monkeypatch):
    monkeypatch.setattr(coletar.S, "get", lambda *a, **k: RespostaFalsa({}, ok=False, status=503))
    with pytest.raises(RuntimeError, match="HTTP 503"):
        coletar.get("/x")


def test_get_todos_segue_paginacao(monkeypatch):
    paginas = {
        "/lista": {"dados": [1, 2], "links": [{"rel": "next", "href": "http://p2"}]},
        "http://p2": {"dados": [3], "links": [{"rel": "next", "href": "http://p3"}]},
        "http://p3": {"dados": [4], "links": [{"rel": "self", "href": "http://p3"}]},
    }
    visitados = []

    def falso(caminho, **params):
        visitados.append((caminho, params))
        return paginas[caminho]

    monkeypatch.setattr(coletar, "get", falso)
    assert coletar.get_todos("/lista") == [1, 2, 3, 4]
    assert visitados[0][1] == {"itens": 100}


def test_avisar_registra(monkeypatch, capsys):
    monkeypatch.setattr(coletar, "AVISOS", [])
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    coletar.avisar("deu ruim")
    assert coletar.AVISOS == ["deu ruim"]
    assert "deu ruim" in capsys.readouterr().err


def test_avisar_anotacao_do_actions_limitada_a_8(monkeypatch, capsys):
    monkeypatch.setattr(coletar, "AVISOS", [])
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    for i in range(12):
        coletar.avisar(f"m{i}")
    assert capsys.readouterr().out.count("::warning::") == 8


# ---------------------------------------------------------------- arquivos

def test_salvar_e_ler_roundtrip(tmp_path):
    destino = tmp_path / "a" / "b.json"
    coletar.salvar(destino, {"nome": "João", "n": [1, 2]})
    assert coletar.ler(destino, None) == {"nome": "João", "n": [1, 2]}
    assert "João" in destino.read_text(encoding="utf-8")  # sem escape ASCII
    assert not destino.with_suffix(".tmp").exists()


def test_ler_arquivo_inexistente_devolve_padrao(tmp_path):
    assert coletar.ler(tmp_path / "nada.json", []) == []


# ---------------------------------------------------------------- janelas

def test_janelas_cobrem_periodo_sem_buracos_nem_sobreposicao():
    ini, fim = dt.date(2024, 1, 1), dt.date(2024, 4, 15)
    js = list(coletar.janelas(ini, fim))
    assert js[0][0] == ini and js[-1][1] == fim
    for (_, f1), (i2, _) in zip(js, js[1:]):
        assert i2 == f1 + dt.timedelta(days=1)
    assert all((f - i).days <= 29 for i, f in js)


def test_janelas_nao_atravessam_ano():
    js = list(coletar.janelas(dt.date(2023, 12, 20), dt.date(2024, 1, 10)))
    assert js == [(dt.date(2023, 12, 20), dt.date(2023, 12, 31)), (dt.date(2024, 1, 1), dt.date(2024, 1, 10))]


def test_janelas_inicio_depois_do_fim_e_vazio():
    assert list(coletar.janelas(dt.date(2024, 2, 1), dt.date(2024, 1, 1))) == []


# ---------------------------------------------------------------- situação

@pytest.mark.parametrize("sit", ["Arquivada", "Transformado em Norma Jurídica", "Retirado pelo Autor", "Vetado totalmente",
                                 "Perdeu a Eficácia", "Sancionada"])
def test_situacao_final_verdadeira(sit):
    assert coletar.situacao_final(sit)


@pytest.mark.parametrize("sit", ["Aguardando Parecer", "Pronta para Pauta", "", None])
def test_situacao_final_falsa(sit):
    assert not coletar.situacao_final(sit)


# ---------------------------------------------------------------- Senado

def test_achar_em_qualquer_nivel():
    obj = {"a": [{"b": {"alvo": 5}}]}
    assert coletar.achar(obj, "alvo") == 5
    assert coletar.achar(obj, "nada") is None
    assert coletar.achar([{"x": 1}, {"alvo": 2}], "alvo") == 2


def test_como_lista():
    assert coletar.como_lista(None) == []
    assert coletar.como_lista({"a": 1}) == [{"a": 1}]
    assert coletar.como_lista([1, 2]) == [1, 2]


@pytest.mark.parametrize("sigla,desc,esperado", [
    ("Sim", None, "sim"),
    ("Não", "Não", "nao"),
    (None, "Voto contrário", "nao"),
    (None, "Voto a favor", "sim"),
    ("NCom", "Não compareceu", "ausente"),  # "Não compareceu" não é voto contra
    (None, "Licença", "ausente"),
    ("Abstenção", None, "abstencao"),
    (None, "Obstrução", "obstrucao"),
    (None, "Presidente (art. 51 RISF)", "art17"),
    (None, "Xyz", "outro"),
    (None, None, "outro"),
])
def test_tipo_voto_senado(sigla, desc, esperado):
    assert coletar.tipo_voto_senado(sigla, desc) == esperado


@pytest.mark.parametrize("texto,esperado", [
    ("Aprovado", 1), ("APROVADA", 1), ("A", 1), ("Rejeitada", 0), ("Prejudicado", 0), ("P", 0), ("Retirado", None), (None, None), ("", None),
])
def test_resultado_senado(texto, esperado):
    assert coletar.resultado_senado(texto, 0, 0) == esperado


def test_pegar_ignora_caixa_e_vazios():
    assert coletar.pegar({"CodigoX": 7}, "codigox") == 7
    assert coletar.pegar({"a": "", "b": 2}, "a", "b") == 2
    assert coletar.pegar({"a": None}, "a") is None
    assert coletar.pegar("nao-dict", "a") is None


def votacao_senado(**extra):
    base = {
        "codigoSessaoVotacao": 123, "dataSessao": "2024-05-10T10:00:00", "horaInicio": "14:35:10",
        "siglaMateria": "PL", "numeroMateria": "10", "anoMateria": "2024", "codigoMateria": 999,
        "descricaoVotacao": " Votação do PL ", "resultadoVotacao": "Aprovado",
        "votos": [
            {"codigoParlamentar": 1, "siglaVotoParlamentar": "Sim", "descricaoVotoParlamentar": "Sim"},
            {"codigoParlamentar": 2, "siglaVotoParlamentar": "Não", "descricaoVotoParlamentar": "Não"},
            {"codigoParlamentar": 3, "siglaVotoParlamentar": "Sim", "descricaoVotoParlamentar": "Sim"},
            {"parlamentar": {"codigoParlamentar": 4}, "descricaoVotoParlamentar": "Abstenção"},
            {"siglaVotoParlamentar": "Sim"},  # sem código: ignorado
        ],
    }
    return {**base, **extra}


def test_normalizar_votacao_senado():
    v = coletar.normalizar_votacao_senado(votacao_senado())
    assert v["id"] == "123"
    assert v["data"] == "2024-05-10"
    assert v["hora"] == "14:35"
    assert v["proposicao"] == "PL 10/2024"
    assert v["propId"] == 999
    assert v["aprovada"] == 1
    assert v["descricao"] == "Votação do PL"
    assert [x[:2] for x in v["votos"]] == [["1", "sim"], ["2", "nao"], ["3", "sim"], ["4", "abstencao"]]


def test_normalizar_votacao_senado_votos_em_dict_e_data_compacta():
    bruto = votacao_senado(dataSessao="20240510", votos={"VotoParlamentar": [{"codigoParlamentar": 1, "siglaVotoParlamentar": "Sim"}]})
    v = coletar.normalizar_votacao_senado(bruto)
    assert v["data"] == "2024-05-10"
    assert len(v["votos"]) == 1


def test_normalizar_votacao_senado_sem_votos_nominais_e_ignorada():
    assert coletar.normalizar_votacao_senado(votacao_senado(votos=[])) is None


def test_normalizar_votacao_senado_sem_data_e_ignorada():
    assert coletar.normalizar_votacao_senado(votacao_senado(dataSessao=None)) is None


def test_normalizar_votacao_senado_data_na_sessao_plenaria():
    bruto = votacao_senado(dataSessao=None, sessaoPlenaria={"dataSessao": "2024-06-01"})
    assert coletar.normalizar_votacao_senado(bruto)["data"] == "2024-06-01"
