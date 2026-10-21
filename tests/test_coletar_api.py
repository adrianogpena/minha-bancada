"""Testes com respostas simuladas das APIs da Câmara e do Senado (formatos como as APIs devolvem),
para garantir que os dados são lidos, normalizados e salvos corretamente e que falhas não derrubam a coleta."""
import datetime as dt
import json

import pytest

import coletar


class Resp:
    def __init__(self, dados, status=200):
        self._d, self.status_code, self.ok, self.url, self.text = dados, status, status < 400, "http://fake", str(dados)[:100]

    def json(self):
        return self._d

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture
def dados(tmp_path, monkeypatch):
    monkeypatch.setattr(coletar, "DADOS", tmp_path)
    monkeypatch.setattr(coletar, "AVISOS", [])
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    return tmp_path


def roteador(monkeypatch, rotas: dict):
    """Troca coletar.get: rotas = {caminho: dict | callable(**params) | Exception}. Registra as chamadas."""
    chamadas = []

    def falso(caminho, **params):
        chamadas.append((caminho, params))
        r = rotas[caminho]
        if isinstance(r, Exception):
            raise r
        return r(**params) if callable(r) else r

    monkeypatch.setattr(coletar, "get", falso)
    return chamadas


# ---------------------------------------------------------------- Câmara: deputado

DETALHE_DEP = {"dados": {
    "nomeCivil": "FULANO DA SILVA", "dataNascimento": "1980-02-03", "municipioNascimento": "Recife",
    "ufNascimento": "PE", "escolaridade": "Superior", "redeSocial": ["https://x.com/fulano"],
    "ultimoStatus": {"nomeEleitoral": "Fulano", "siglaPartido": "ABC", "siglaUf": "PE", "urlFoto": "http://foto",
                     "email": "dep@camara.leg.br", "situacao": "Exercício", "condicaoEleitoral": "Titular",
                     "gabinete": {"predio": "4", "sala": "", "andar": "2", "telefone": None, "email": "g@x", "extra": "x"}}}}


def test_coletar_deputado_normaliza_campos(dados, monkeypatch):
    monkeypatch.setattr(coletar, "coletar_proposicoes", lambda dep: [{"id": 9, "siglaTipo": "PL", "numero": 1, "ano": 2024, "ementa": " e "}])
    roteador(monkeypatch, {
        "/deputados/7": DETALHE_DEP,
        "/deputados/7/despesas": {"dados": [
            {"mes": 3, "tipoDespesa": "Passagens", "valorLiquido": 120.5, "nomeFornecedor": "Cia", "dataDocumento": "2025-03-01", "urlDocumento": "http://nf"},
            {"mes": 4, "tipoDespesa": "Outros", "valorLiquido": None},
        ], "links": []},
    })
    d = coletar.coletar_deputado({"id": 7, "nome": "Fulano (lista)"}, 2025)
    assert d["nome"] == "Fulano" and d["partido"] == "ABC" and d["uf"] == "PE" and d["situacao"] == "Exercício"
    assert d["gabinete"] == {"predio": "4", "andar": "2", "email": "g@x"}  # só chaves conhecidas e não vazias
    assert d["proposicoes"] == [{"id": 9, "tipo": "PL", "numero": 1, "ano": 2024, "ementa": "e"}]
    assert d["despesas"]["ano"] == 2025
    assert d["despesas"]["itens"][0] == {"mes": 3, "tipo": "Passagens", "valor": 120.5, "fornecedor": "Cia", "data": "2025-03-01", "documento": "http://nf"}
    assert d["despesas"]["itens"][1]["valor"] == 0  # valor nulo vira 0
    assert d["redesSociais"] == ["https://x.com/fulano"]


def test_coletar_deputado_usa_dados_da_lista_se_faltar_status(dados, monkeypatch):
    monkeypatch.setattr(coletar, "coletar_proposicoes", lambda dep: [])
    roteador(monkeypatch, {"/deputados/7": {"dados": {"ultimoStatus": None}}, "/deputados/7/despesas": {"dados": []}})
    d = coletar.coletar_deputado({"id": 7, "nome": "Lista", "siglaPartido": "XYZ", "siglaUf": "SP"}, 2025)
    assert (d["nome"], d["partido"], d["uf"]) == ("Lista", "XYZ", "SP")
    assert d["gabinete"] == {} and d["redesSociais"] == []


def test_coletar_deputado_despesas_falham_sem_derrubar(dados, monkeypatch):
    monkeypatch.setattr(coletar, "coletar_proposicoes", lambda dep: [])
    roteador(monkeypatch, {"/deputados/7": DETALHE_DEP, "/deputados/7/despesas": RuntimeError("HTTP 503")})
    d = coletar.coletar_deputado({"id": 7, "nome": "F"}, 2025)
    assert d["despesas"]["itens"] == []
    assert any("despesas de F" in a for a in coletar.AVISOS)


def test_coletar_deputados_salva_arquivos_e_resume(dados, monkeypatch):
    monkeypatch.setattr(coletar, "get_todos", lambda c, **p: [{"id": 1, "nome": "A"}, {"id": 2, "nome": "B"}, {"id": 3, "nome": "C"}])
    monkeypatch.setattr(coletar, "coletar_deputado", lambda dep, ano: {"id": dep["id"], "nome": dep["nome"]})
    assert sorted(coletar.coletar_deputados(2)) == [1, 2]
    assert json.loads((dados / "deputados.json").read_text()) == [1, 2]
    assert json.loads((dados / "deputados" / "1.json").read_text())["nome"] == "A"


def test_coletar_deputados_aborta_com_muitas_falhas(dados, monkeypatch):
    monkeypatch.setattr(coletar, "get_todos", lambda c, **p: [{"id": i, "nome": str(i)} for i in range(10)])

    def quebra(dep, ano):
        if dep["id"] < 5:
            raise RuntimeError("API fora")
        return {"id": dep["id"]}

    monkeypatch.setattr(coletar, "coletar_deputado", quebra)
    with pytest.raises(SystemExit, match="Muitas falhas"):
        coletar.coletar_deputados(None)


def test_coletar_deputados_tolera_poucas_falhas(dados, monkeypatch):
    monkeypatch.setattr(coletar, "get_todos", lambda c, **p: [{"id": i, "nome": str(i)} for i in range(10)])

    def quebra(dep, ano):
        if dep["id"] == 0:
            raise RuntimeError("API fora")
        return {"id": dep["id"]}

    monkeypatch.setattr(coletar, "coletar_deputado", quebra)
    assert sorted(coletar.coletar_deputados(None)) == list(range(1, 10))


# ---------------------------------------------------------------- Câmara: proposições (cache incremental)

def test_coletar_proposicoes_mescla_com_cache_e_avanca_data(dados, monkeypatch):
    hoje = dt.date.today()
    coletar.salvar(dados / "proposicoes" / "7.json", {"ate": (hoje - dt.timedelta(days=20)).isoformat(),
                                                      "itens": [{"id": 1, "siglaTipo": "PL", "numero": 1, "ano": 2024, "ementa": "velha"}]})
    chamadas = []

    def get_todos(caminho, **params):
        chamadas.append(params)
        return [{"id": 2, "siglaTipo": "PEC", "numero": 5, "ano": 2025, "ementa": "  nova \n"},
                {"id": 1, "siglaTipo": "PL", "numero": 1, "ano": 2024, "ementa": "atualizada"}]

    monkeypatch.setattr(coletar, "get_todos", get_todos)
    itens = coletar.coletar_proposicoes({"id": 7, "nome": "F"})
    assert [p["id"] for p in itens] == [2, 1]  # mais novas primeiro
    assert itens[0]["ementa"] == "nova"
    assert itens[1]["ementa"] == "atualizada"  # sem duplicar
    # busca reinicia 10 dias antes da última data coletada
    assert chamadas[0]["dataApresentacaoInicio"] == (hoje - dt.timedelta(days=30)).isoformat()
    assert json.loads((dados / "proposicoes" / "7.json").read_text())["ate"] == hoje.isoformat()


def test_coletar_proposicoes_falha_nao_avanca_data(dados, monkeypatch):
    coletar.salvar(dados / "proposicoes" / "7.json", {"ate": "2025-01-01", "itens": []})

    def falha(caminho, **params):
        raise RuntimeError("HTTP 500")

    monkeypatch.setattr(coletar, "get_todos", falha)
    coletar.coletar_proposicoes({"id": 7, "nome": "F"})
    assert json.loads((dados / "proposicoes" / "7.json").read_text())["ate"] == "2025-01-01"
    assert coletar.AVISOS


def test_coletar_proposicoes_primeira_vez_comeca_na_legislatura(dados, monkeypatch):
    chamadas = []
    monkeypatch.setattr(coletar, "get_todos", lambda c, **p: chamadas.append(p) or [])
    coletar.coletar_proposicoes({"id": 8, "nome": "F"})
    assert chamadas[0]["dataApresentacaoInicio"] == coletar.INICIO_LEGISLATURA
    # cada janela cobre no máximo 3 meses
    for p in chamadas:
        ini, fim = dt.date.fromisoformat(p["dataApresentacaoInicio"]), dt.date.fromisoformat(p["dataApresentacaoFim"])
        assert (fim - ini).days <= 88


# ---------------------------------------------------------------- Câmara: detalhes das proposições

def test_detalhes_proposicoes_prioriza_novas_e_marca_situacao_final(dados, monkeypatch):
    coletar.salvar(dados / "proposicoes" / "1.json", {"ate": "x", "itens": [
        {"id": 10, "siglaTipo": "PL"}, {"id": 11, "siglaTipo": "REQ"}, {"id": 12, "siglaTipo": "PEC"}]})
    monkeypatch.setattr(coletar, "ORCAMENTO_DETALHES", 10)
    resp = {
        "/proposicoes/10": {"dados": {"dataApresentacao": "2025-01-02T10:00", "ementaDetalhada": " det ", "keywords": "a, b",
                                       "urlInteiroTeor": "http://pdf",
                                       "statusProposicao": {"descricaoSituacao": "Arquivada", "descricaoTramitacao": "Arquivamento",
                                                            "despacho": " Arquive-se ", "siglaOrgao": "MESA", "dataHora": "2025-02-03T09:00", "regime": "Ordinário"}}},
        "/proposicoes/12": {"dados": {"dataApresentacao": "2025-03-04", "statusProposicao": {"descricaoSituacao": "Aguardando Parecer"}}},
    }
    chamadas = roteador(monkeypatch, resp)
    coletar.coletar_detalhes_proposicoes()
    assert sorted(c[0] for c in chamadas) == ["/proposicoes/10", "/proposicoes/12"]  # REQ não é projeto principal
    cache = json.loads((dados / "proposicoes_detalhe.json").read_text())
    assert cache["10"]["fim"] is True and cache["10"]["sit"] == "Arquivada"
    assert cache["10"]["apres"] == "2025-01-02" and cache["10"]["data"] == "2025-02-03"
    assert cache["10"]["desp"] == "Arquive-se" and cache["10"]["detalhada"] == "det"
    assert cache["12"]["fim"] is False and cache["12"]["desp"] is None


def test_detalhes_proposicoes_respeita_orcamento_e_renova_so_o_que_tramita(dados, monkeypatch):
    hoje = dt.date.today()
    velho = (hoje - dt.timedelta(days=30)).isoformat()
    coletar.salvar(dados / "proposicoes" / "1.json", {"itens": [{"id": i, "siglaTipo": "PL"} for i in (1, 2, 3)]})
    coletar.salvar(dados / "proposicoes_detalhe.json", {"1": {"em": velho, "fim": True}, "2": {"em": velho, "fim": False}, "3": {"em": hoje.isoformat(), "fim": False}})
    chamadas = roteador(monkeypatch, {"/proposicoes/2": {"dados": {"statusProposicao": {"descricaoSituacao": "Em tramitação"}}}})
    coletar.coletar_detalhes_proposicoes()
    assert [c[0] for c in chamadas] == ["/proposicoes/2"]  # 1 é final, 3 é recente


def test_detalhes_proposicoes_erro_individual_nao_perde_o_resto(dados, monkeypatch):
    coletar.salvar(dados / "proposicoes" / "1.json", {"itens": [{"id": 1, "siglaTipo": "PL"}, {"id": 2, "siglaTipo": "PL"}]})
    roteador(monkeypatch, {"/proposicoes/1": RuntimeError("HTTP 500"), "/proposicoes/2": {"dados": {}}})
    coletar.coletar_detalhes_proposicoes()
    cache = json.loads((dados / "proposicoes_detalhe.json").read_text())
    assert list(cache) == ["2"] and coletar.AVISOS


# ---------------------------------------------------------------- Câmara: votações

def test_coletar_votos_nominal_busca_proposicao(dados, monkeypatch):
    roteador(monkeypatch, {
        "/votacoes/55/votos": {"dados": [{"deputado_": {"id": 1}, "tipoVoto": "Sim"}, {"deputado_": {"id": 2}, "tipoVoto": "Não"}, {"tipoVoto": "Sim"}]},
        "/votacoes/55": {"dados": {"proposicoesAfetadas": [{"id": 99, "siglaTipo": "PL", "numero": 3, "ano": 2025, "ementa": " Ementa "}]}},
    })
    v = coletar.coletar_votos({"id": "55", "data": "2025-04-01", "dataHoraRegistro": "2025-04-01T15:30:00", "siglaOrgao": "PLEN",
                               "descricao": " Aprovado ", "aprovacao": 1})
    assert v["votos"] == [[1, "Sim"], [2, "Não"]]  # voto sem deputado é ignorado
    assert (v["proposicao"], v["propId"], v["ementa"]) == ("PL 3/2025", 99, "Ementa")
    assert (v["data"], v["hora"], v["aprovada"], v["descricao"]) == ("2025-04-01", "15:30", 1, "Aprovado")


def test_coletar_votos_simbolica_nao_consulta_detalhe(dados, monkeypatch):
    chamadas = roteador(monkeypatch, {"/votacoes/55/votos": {"dados": []}})
    v = coletar.coletar_votos({"id": "55", "dataHoraRegistro": "2025-04-01T15:30:00", "proposicaoObjeto": "PL 1/2025"})
    assert v["votos"] == [] and v["proposicao"] == "PL 1/2025"
    assert len(chamadas) == 1


def test_coletar_votos_erro_no_detalhe_mantem_votos(dados, monkeypatch):
    roteador(monkeypatch, {"/votacoes/55/votos": {"dados": [{"deputado_": {"id": 1}, "tipoVoto": "Sim"}]}, "/votacoes/55": RuntimeError("HTTP 500")})
    v = coletar.coletar_votos({"id": "55", "dataHoraRegistro": "2025-04-01T15:30:00"})
    assert v["votos"] == [[1, "Sim"]] and v["propId"] is None and coletar.AVISOS


def test_coletar_votacoes_so_plenario_agrupa_por_ano(dados, monkeypatch):
    hoje = dt.date.today()
    lista = [{"id": "1", "siglaOrgao": "PLEN", "dataHoraRegistro": f"{hoje}T10:00:00"},
             {"id": "2", "siglaOrgao": "CCJC", "dataHoraRegistro": f"{hoje}T11:00:00"}]
    monkeypatch.setattr(coletar, "get_todos", lambda c, **p: lista)
    monkeypatch.setattr(coletar, "coletar_votos", lambda v: {"id": v["id"], "data": str(hoje), "votos": []})
    coletar.coletar_votacoes(5)
    salvo = json.loads((dados / "votacoes" / f"{hoje.year}.json").read_text())
    assert list(salvo) == ["1"]  # a votação da comissão não entra


def test_coletar_votacoes_janela_com_erro_nao_para(dados, monkeypatch):
    def falha(c, **p):
        raise RuntimeError("HTTP 500")

    monkeypatch.setattr(coletar, "get_todos", falha)
    coletar.coletar_votacoes(5)
    assert coletar.AVISOS


# ---------------------------------------------------------------- Senado

LISTA_SENADORES = {"ListaParlamentarEmExercicio": {"Parlamentares": {"Parlamentar": [
    {"IdentificacaoParlamentar": {"CodigoParlamentar": "5001", "NomeParlamentar": "Sena Dor", "NomeCompletoParlamentar": "Sena Dor Completo",
                                  "SiglaPartidoParlamentar": "ABC", "UfParlamentar": "PE", "UrlFotoParlamentar": "http://f", "UrlPaginaParlamentar": "http://p",
                                  "EmailParlamentar": "s@senado.leg.br", "SexoParlamentar": "Feminino"},
     "Mandato": {"DescricaoParticipacao": "Titular", "PrimeiraLegislaturaDoMandato": {"DataFim": "2027-01-31"},
                 "SegundaLegislaturaDoMandato": {"DataFim": "2031-01-31"},
                 "Titular": {"NomeParlamentar": "Titular X"},
                 "Exercicios": {"Exercicio": [{"DataInicio": "2019-02-01", "DataFim": "2020-01-01"}, {"DataInicio": "2021-05-05"}]}}},
    {"IdentificacaoParlamentar": {"CodigoParlamentar": "5002", "NomeParlamentar": "Outro"}, "Mandato": {"UfParlamentar": "SP"}},
]}}}


def senado_resp(monkeypatch, dados_json):
    monkeypatch.setattr(coletar.S, "get", lambda url, **k: Resp(dados_json))


def test_coletar_senado_normaliza(dados, monkeypatch):
    senado_resp(monkeypatch, LISTA_SENADORES)
    coletar.coletar_senado()
    s = json.loads((dados / "senado.json").read_text())
    assert s[0]["id"] == "5001" and s[0]["partido"] == "ABC" and s[0]["uf"] == "PE" and s[0]["genero"] == "Feminino"
    assert s[0]["fimMandato"] == "2031-01-31" and s[0]["exercicioDesde"] == "2021-05-05" and s[0]["titular"] == "Titular X"
    assert s[1]["uf"] == "SP" and s[1]["fimMandato"] is None and s[1]["exercicioDesde"] is None


def test_coletar_senado_um_so_senador_vem_como_dict(dados, monkeypatch):
    unico = {"ListaParlamentarEmExercicio": {"Parlamentares": {"Parlamentar": LISTA_SENADORES["ListaParlamentarEmExercicio"]["Parlamentares"]["Parlamentar"][1]}}}
    senado_resp(monkeypatch, unico)
    coletar.coletar_senado()
    assert len(json.loads((dados / "senado.json").read_text())) == 1


def test_coletar_senado_http_erro_propaga(dados, monkeypatch):
    monkeypatch.setattr(coletar.S, "get", lambda url, **k: Resp({}, 503))
    with pytest.raises(RuntimeError):
        coletar.coletar_senado()


def test_ceaps_agrupa_por_senador_ordena_e_ignora_sem_codigo(dados, monkeypatch):
    senado_resp(monkeypatch, [
        {"codSenador": 1, "mes": 1, "tipoDespesa": "Aluguel", "valorReembolsado": 100, "fornecedor": "A", "data": "2025-01-05"},
        {"codSenador": 1, "mes": 3, "tipoDespesa": "Passagem", "valorReembolsado": None, "fornecedor": "B", "data": "2025-03-05"},
        {"codSenador": None, "valorReembolsado": 5},
    ])
    coletar.coletar_ceaps_senado()
    r = json.loads((dados / "senado_ceaps.json").read_text())
    assert list(r["itens"]) == ["1"]
    assert [i["data"] for i in r["itens"]["1"]] == ["2025-03-05", "2025-01-05"]
    assert r["itens"]["1"][0]["valor"] == 0


def votacao_s(codigo, data, voto="Sim"):
    return {"codigoSessaoVotacao": codigo, "dataSessao": data, "siglaMateria": "PL", "numeroMateria": "1", "anoMateria": "2025",
            "votos": [{"codigoParlamentar": 1, "siglaVotoParlamentar": voto, "descricaoVotoParlamentar": voto}]}


def test_votacoes_senado_usa_endpoint_alternativo_quando_o_primeiro_falha(dados, monkeypatch):
    ano = dt.date.today().year
    monkeypatch.setattr(coletar, "INICIO_LEGISLATURA", f"{ano}-01-01")

    def get_senado(caminho, **p):
        if caminho.startswith("/plenario"):
            raise RuntimeError("HTTP 404")
        return {"Votacoes": {"Votacao": [votacao_s(1, f"{ano}-01-10"), {"semVotos": True}]}}

    monkeypatch.setattr(coletar, "get_senado", get_senado)
    coletar.coletar_votacoes_senado()
    salvo = json.loads((dados / "senado_votacoes" / f"{ano}.json").read_text())
    assert list(salvo) == ["1"] and salvo["1"]["votos"][0][:2] == ["1", "sim"]
    assert "sim" in json.loads((dados / "senado_votacoes" / "_rotulos.json").read_text())


def test_votacoes_senado_so_guarda_votacoes_do_proprio_ano(dados, monkeypatch):
    ano = dt.date.today().year
    monkeypatch.setattr(coletar, "INICIO_LEGISLATURA", f"{ano}-01-01")
    monkeypatch.setattr(coletar, "get_senado", lambda c, **p: [votacao_s(1, f"{ano}-02-01"), votacao_s(2, f"{ano - 1}-12-31")])
    coletar.coletar_votacoes_senado()
    assert list(json.loads((dados / "senado_votacoes" / f"{ano}.json").read_text())) == ["1"]


def test_votacoes_senado_sem_resultado_avisa(dados, monkeypatch):
    ano = dt.date.today().year
    monkeypatch.setattr(coletar, "INICIO_LEGISLATURA", f"{ano}-01-01")
    monkeypatch.setattr(coletar, "get_senado", lambda c, **p: [])
    coletar.coletar_votacoes_senado()
    assert any(str(ano) in a for a in coletar.AVISOS)


def test_autorias_senado_e_situacao_das_materias(dados, monkeypatch):
    coletar.salvar(dados / "senado.json", [{"id": "5001"}])

    def get_senado(caminho, **p):
        if caminho == "/senador/5001/autorias":
            return {"MateriasAutoriaParlamentar": {"Parlamentar": {"Autorias": {"Autoria": [
                {"IndicadorAutorPrincipal": "Sim", "Materia": {"Codigo": "111", "Sigla": "PL", "Numero": "0010", "Ano": "2024", "Ementa": " Ementa ", "Data": "2024-03-04T00:00"}},
                {"IndicadorAutorPrincipal": "Não", "Materia": {"Codigo": "112", "Sigla": "REQ", "Numero": "5", "Ano": "2025"}},
                {"Materia": {"Codigo": "113", "Sigla": "PL", "Numero": "1", "Ano": "2018"}},  # antes de 2019: ignorada
            ]}}}}
        if caminho == "/materia/111":
            return {"DetalheMateria": {"Materia": {"SituacaoAtual": {"Autuacoes": {"Autuacao": {"Situacao": {"DescricaoSituacao": "Arquivada", "DataSituacao": "2025-01-02"}}}},
                                                   "DadosBasicosMateria": {"DataApresentacao": "2024-03-04", "IndexacaoMateria": "tema"}}}}
        raise AssertionError(caminho)

    monkeypatch.setattr(coletar, "get_senado", get_senado)
    coletar.coletar_autorias_senado()
    aut = json.loads((dados / "senado_autorias.json").read_text())["5001"]
    assert [a["id"] for a in aut] == ["112", "111"]  # 2025 antes de 2024
    pl = next(a for a in aut if a["id"] == "111")
    assert pl["principal"] is True and pl["ementa"] == "Ementa" and pl["ap"] == "2024-03-04"
    cache = json.loads((dados / "senado_materias.json").read_text())
    assert list(cache) == ["111"]  # REQ não é projeto
    assert cache["111"]["sit"] == "Arquivada" and cache["111"]["fim"] is True and cache["111"]["kw"] == "tema"


def test_autorias_senado_falha_individual_nao_derruba(dados, monkeypatch):
    coletar.salvar(dados / "senado.json", [{"id": "1"}, {"id": "2"}])

    def get_senado(caminho, **p):
        if caminho == "/senador/1/autorias":
            raise RuntimeError("HTTP 503")
        return {"Autoria": []}

    monkeypatch.setattr(coletar, "get_senado", get_senado)
    coletar.coletar_autorias_senado()
    assert list(json.loads((dados / "senado_autorias.json").read_text())) == ["2"]
    assert coletar.AVISOS


# ---------------------------------------------------------------- main

def test_main_etapa_complementar_com_erro_nao_aborta(dados, monkeypatch):
    chamadas = []
    monkeypatch.setattr(coletar, "coletar_deputados", lambda limite: chamadas.append("dep"))
    monkeypatch.setattr(coletar, "coletar_votacoes", lambda d: chamadas.append("vot"))
    monkeypatch.setattr(coletar, "coletar_detalhes_proposicoes", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(coletar, "coletar_senado", lambda: chamadas.append("sen"))
    for n in ("coletar_votacoes_senado", "coletar_autorias_senado", "coletar_ceaps_senado"):
        monkeypatch.setattr(coletar, n, lambda n=n: chamadas.append(n))
    monkeypatch.setattr("sys.argv", ["coletar.py"])
    coletar.main()
    assert chamadas == ["dep", "vot", "sen", "coletar_votacoes_senado", "coletar_autorias_senado", "coletar_ceaps_senado"]
    assert any("detalhes das proposições" in a for a in coletar.AVISOS)
    assert "atualizadoEm" in json.loads((dados / "meta.json").read_text())
