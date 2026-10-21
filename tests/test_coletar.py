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

@pytest.mark.parametrize("sigla,desc,esperado", [
    ("Sim", None, "sim"),
    ("Não", "Não", "nao"),
    ("Abstenção", None, "abstencao"),
    ("Presidente (art. 51 RISF)", None, "art17"),
    ("Votou", None, "secreto"),                     # votação secreta
    ("NCom", "Não Compareceu", "ausente"),          # "Não compareceu" não é voto contra
    ("P-NRV", "Presente – Não registrou voto", "ausente"),   # estava presente, mas não votou "Não"
    ("NA", "Dispositivo não citado", "ausente"),
    ("AP", "Atividade parlamentar", "ausente"),
    ("LS", "Licença saúde", "ausente"),
    ("LP", "Licença Particular", "ausente"),
    ("LAP", "Licença paternidade ou ao adotante", "ausente"),
    ("MIS", "Missão da Casa no País/exterior", "ausente"),
    # siglas que o Senado ainda não usava: cai na descrição
    (None, "Voto contrário", "nao"),
    (None, "Voto a favor", "sim"),
    (None, "Licença", "ausente"),
    (None, "Obstrução", "obstrucao"),
    ("XX", "Presente sem voto", "ausente"),
    (None, "Xyz", "outro"),
    (None, None, "outro"),
])
def test_tipo_voto_senado(sigla, desc, esperado):
    assert coletar.tipo_voto_senado(sigla, desc) == esperado


@pytest.mark.parametrize("texto,esperado", [
    ("Aprovado", 1), ("APROVADA", 1), ("A", 1), ("Rejeitada", 0), ("Prejudicado", 0), ("R", 0), ("P", 0), ("Retirado", None), (None, None), ("", None),
])
def test_resultado_senado(texto, esperado):
    assert coletar.resultado_senado(texto) == esperado


def votacao_senado(**extra):
    """Formato do endpoint /votacao."""
    base = {
        "codigoSessaoVotacao": 7106, "dataSessao": "2026-10-14", "codigoMateria": 174386, "idProcesso": 9056435,
        "identificacao": "PEC 221/2019", "sigla": "PEC", "numero": "221", "ano": 2019, "ementa": " Altera o art. 7º ",
        "descricaoVotacao": " Votação nominal da PEC 221/2019. ", "resultadoVotacao": "A", "votacaoSecreta": "N",
        "votos": [
            {"codigoParlamentar": 5672, "siglaVotoParlamentar": "Sim", "descricaoVotoParlamentar": None},
            {"codigoParlamentar": 5982, "siglaVotoParlamentar": "Não", "descricaoVotoParlamentar": None},
            {"codigoParlamentar": 6358, "siglaVotoParlamentar": "P-NRV", "descricaoVotoParlamentar": "Presente – Não registrou voto"},
            {"codigoParlamentar": 1, "siglaVotoParlamentar": "Abstenção", "descricaoVotoParlamentar": None},
            {"siglaVotoParlamentar": "Sim"},  # sem código: ignorado
        ],
    }
    return {**base, **extra}


def test_normalizar_votacao_senado():
    v = coletar.normalizar_votacao_senado(votacao_senado())
    assert v["id"] == "7106" and v["data"] == "2026-10-14" and v["hora"] is None
    assert v["proposicao"] == "PEC 221/2019" and v["propId"] == 174386
    assert v["ementa"] == "Altera o art. 7º" and v["descricao"] == "Votação nominal da PEC 221/2019."
    assert v["aprovada"] == 1 and v["resultadoTexto"] == "A"
    assert v["secreta"] is False and v["totais"] is None and v["sessao"] is None and v["processo"] == 9056435
    assert v["votos"] == [["5672", "sim", "Sim|"], ["5982", "nao", "Não|"],
                          ["6358", "ausente", "P-NRV|Presente – Não registrou voto"], ["1", "abstencao", "Abstenção|"]]


def test_normalizar_votacao_senado_guarda_secreta_placar_oficial_e_sessao():
    v = coletar.normalizar_votacao_senado(votacao_senado(
        votacaoSecreta="S", totalVotosSim=40, totalVotosNao=3, totalVotosAbstencao=None, numeroSessao=113, siglaTipoSessao="DOR", sequencialVotacao=4415,
        votos=[{"codigoParlamentar": 1, "siglaVotoParlamentar": "Votou", "descricaoVotoParlamentar": "Votou"}]))
    assert v["secreta"] is True and v["totais"] == {"sim": 40, "nao": 3}
    assert v["sessao"] == {"numero": 113, "tipo": "DOR", "votacao": 4415}
    assert v["votos"] == [["1", "secreto", "Votou|Votou"]]


def test_normalizar_votacao_senado_rejeitada_e_sem_ementa():
    v = coletar.normalizar_votacao_senado(votacao_senado(resultadoVotacao="R", ementa=None))
    assert v["aprovada"] == 0 and v["ementa"] is None


def test_normalizar_votacao_senado_sem_votos_nominais_e_ignorada():
    assert coletar.normalizar_votacao_senado(votacao_senado(votos=[])) is None
    assert coletar.normalizar_votacao_senado(votacao_senado(votos=None)) is None


def test_normalizar_votacao_senado_sem_data_e_ignorada():
    assert coletar.normalizar_votacao_senado(votacao_senado(dataSessao=None)) is None


def test_reclassificar_votos_senado_usa_o_rotulo_original(tmp_path):
    coletar.salvar(tmp_path / "2025.json", {"1": {"id": "1", "votos": [
        ["1", "nao", "P-NRV|Presente – Não registrou voto"], ["2", "nao", "Não|Não"], ["3", "outro", "AP|Atividade parlamentar"], ["4", "sim"]]}})
    assert coletar.reclassificar_votos_senado(tmp_path) == 2
    votos = coletar.ler(tmp_path / "2025.json", {})["1"]["votos"]
    assert [x[1] for x in votos] == ["ausente", "nao", "ausente", "sim"]
    assert coletar.reclassificar_votos_senado(tmp_path) == 0   # idempotente


@pytest.mark.parametrize("autoria,nome,esperado", [
    ("Senador Alan Rick (UNIÃO/AC), Senador Flávio Arns (PSB/PR)", "Alan Rick", True),
    ("Senador Alan Rick (UNIÃO/AC), Senador Flávio Arns (PSB/PR)", "Flávio Arns", False),   # só o primeiro é principal
    ("Senadora Damares Alves (REPUBLICANOS/DF)", "damares alves", True),
    ("Líder do PL Carlos Portinho (PL/RJ)", "Carlos Portinho", False),
    ("Câmara dos Deputados", "Alan Rick", False),
    (None, "Alan Rick", False),
    ("Senador Alan Rick (UNIÃO/AC)", None, False),
])
def test_primeiro_autor_senado(autoria, nome, esperado):
    assert coletar.primeiro_autor_senado(autoria, nome) is esperado


def processo(**extra):
    base = {"id": 9056435, "codigoMateria": 174386, "identificacao": "PEC 221/2019", "ementa": " Altera o art. 7º ", "autoria": "Senador Alan Rick (UNIÃO/AC)",
            "dataApresentacao": "2026-05-28", "situacaoAtual": "AGUARDANDO DESPACHO", "dataSituacaoAtual": "2026-06-01", "tramitando": "Sim"}
    return {**base, **extra}


def test_autoria_senado():
    a = coletar.autoria_senado(processo(), "Alan Rick")
    assert a == {"id": "174386", "processo": 9056435, "tipo": "PEC", "numero": "221", "ano": 2019, "ementa": "Altera o art. 7º", "principal": True,
                 "dataApresentacao": "2026-05-28", "situacao": "AGUARDANDO DESPACHO", "dataSituacao": "2026-06-01"}


def test_autoria_senado_numero_com_ponto_e_tipo_com_ponto():
    a = coletar.autoria_senado(processo(identificacao="R.S 1.234/2024"), "x")
    assert a["tipo"] == "R.S" and a["numero"] == "1234"


@pytest.mark.parametrize("extra", [{"identificacao": "PL 1/2018"}, {"identificacao": "sem numero"}, {"codigoMateria": None}, {"identificacao": None}])
def test_autoria_senado_descarta_o_que_o_site_nao_mostra(extra):
    assert coletar.autoria_senado(processo(**extra), "x") is None
