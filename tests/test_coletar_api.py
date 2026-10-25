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
    monkeypatch.setattr(coletar, "coletar_cota_csv", lambda ano: {})
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
    assert d["despesas"]["itens"][0] == {"mes": 3, "tipo": "Passagens", "valor": 120.5, "fornecedor": "Cia", "cnpj": None, "data": "2025-03-01", "documento": "http://nf"}
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


CSV_COTA = '''﻿"txtFornecedor";"txtCNPJCPF";"txtDescricao";"datEmissao";"vlrLiquido";"numMes";"numAno";"nuDeputadoId";"urlDocumento"
"Cia A";"02.964.380/0001-00";"Passagens";"2026-01-05T00:00:00";"100.5";"1";"2026";"7";"http://nf1"
"Cia B";"";"Combustíveis";"2026-02-05T00:00:00";"20";"2";"2026";"7";""
"Cia C";"1";"Outros";"2025-12-05T00:00:00";"5";"12";"2025";"7";""
"Cia D";"1";"Outros";"2026-01-05T00:00:00";"5";"1";"2026";"";""
'''


def test_coletar_cota_csv_agrupa_por_deputado(monkeypatch):
    import io, zipfile
    csv_ = CSV_COTA
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Ano-2026.csv", csv_.encode("utf-8"))

    class Resp:
        content = buf.getvalue()
        def raise_for_status(self): pass
    monkeypatch.setattr(coletar.S, "get", lambda url, **k: Resp())
    cota = coletar.coletar_cota_csv(2026)
    assert list(cota) == [7]
    assert [i["fornecedor"] for i in cota[7]] == ["Cia B", "Cia A"]
    assert cota[7][1] == {"mes": 1, "tipo": "Passagens", "valor": 100.5, "fornecedor": "Cia A", "cnpj": "02964380000100",
                          "data": "2026-01-05", "documento": "http://nf1"}
    assert cota[7][0]["documento"] is None


def test_coletar_deputado_usa_a_cota_do_csv(dados, monkeypatch):
    monkeypatch.setattr(coletar, "coletar_proposicoes", lambda dep: [])
    roteador(monkeypatch, {"/deputados/7": DETALHE_DEP})
    d = coletar.coletar_deputado({"id": 7, "nome": "F"}, 2025, {7: [{"mes": 1, "valor": 3}]})
    assert d["despesas"]["itens"] == [{"mes": 1, "valor": 3}]


def test_coletar_deputados_salva_arquivos_e_resume(dados, monkeypatch):
    monkeypatch.setattr(coletar, "get_todos", lambda c, **p: [{"id": 1, "nome": "A"}, {"id": 2, "nome": "B"}, {"id": 3, "nome": "C"}])
    monkeypatch.setattr(coletar, "coletar_cota_csv", lambda ano: {})
    monkeypatch.setattr(coletar, "coletar_deputado", lambda dep, ano, cota=None: {"id": dep["id"], "nome": dep["nome"]})
    assert sorted(coletar.coletar_deputados(2)) == [1, 2]
    assert json.loads((dados / "deputados.json").read_text()) == [1, 2]
    assert json.loads((dados / "deputados" / "1.json").read_text())["nome"] == "A"


def test_coletar_deputados_aborta_com_muitas_falhas(dados, monkeypatch):
    monkeypatch.setattr(coletar, "get_todos", lambda c, **p: [{"id": i, "nome": str(i)} for i in range(10)])

    def quebra(dep, ano, cota=None):
        if dep["id"] < 5:
            raise RuntimeError("API fora")
        return {"id": dep["id"]}

    monkeypatch.setattr(coletar, "coletar_deputado", quebra)
    with pytest.raises(SystemExit, match="Muitas falhas"):
        coletar.coletar_deputados(None)


def test_coletar_deputados_tolera_poucas_falhas(dados, monkeypatch):
    monkeypatch.setattr(coletar, "get_todos", lambda c, **p: [{"id": i, "nome": str(i)} for i in range(10)])

    def quebra(dep, ano, cota=None):
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


def test_coletar_proposicoes_migra_formato_antigo_e_guarda_a_ementa_uma_vez(dados, monkeypatch):
    hoje = dt.date.today()
    projeto = {"id": 1, "siglaTipo": "PL", "numero": 1, "ano": 2024, "ementa": "coletiva"}
    for did in (7, 8):    # o mesmo projeto, assinado pelos dois deputados, repetido nos arquivos antigos
        coletar.salvar(dados / "proposicoes" / f"{did}.json", {"ate": hoje.isoformat(), "itens": [projeto]})
    monkeypatch.setattr(coletar, "get_todos", lambda c, **p: [])
    assert [p["ementa"] for p in coletar.coletar_proposicoes({"id": 7, "nome": "A"})] == ["coletiva"]
    coletar.coletar_proposicoes({"id": 8, "nome": "B"})
    coletar.cadastro().gravar(forcar=True)
    assert json.loads((dados / "proposicoes" / "7.json").read_text()) == {"ate": hoje.isoformat(), "ids": [1]}
    assert json.loads((dados / "proposicoes_cadastro" / "2024.json").read_text(encoding="utf-8")) == {"1": ["PL", 1, "coletiva"]}
    assert coletar.ids_de_projetos(coletar.TIPOS_PROJETO) == {"1"}
    assert coletar.ids_de_projetos({"REQ"}) == set()


def test_coletar_proposicoes_id_sem_cadastro_releia_desde_a_legislatura(dados, monkeypatch):
    hoje = dt.date.today()
    coletar.salvar(dados / "proposicoes" / "7.json", {"ate": hoje.isoformat(), "ids": [1]})     # execução interrompida antes de gravar o cadastro
    chamadas = []
    monkeypatch.setattr(coletar, "get_todos", lambda c, **p: chamadas.append(p) or [{"id": 1, "siglaTipo": "PL", "numero": 1, "ano": 2024, "ementa": "ok"}])
    itens = coletar.coletar_proposicoes({"id": 7, "nome": "F"})
    assert chamadas[0]["dataApresentacaoInicio"] == coletar.INICIO_LEGISLATURA and [p["ementa"] for p in itens] == ["ok"]


def test_coletar_proposicoes_usa_o_cadastro_no_formato_novo(dados, monkeypatch):
    hoje = dt.date.today()
    coletar.salvar(dados / "proposicoes_cadastro" / "2024.json", {"1": ["PL", 1, "guardada"]})
    coletar.salvar(dados / "proposicoes" / "7.json", {"ate": (hoje - dt.timedelta(days=20)).isoformat(), "ids": [1]})
    chamadas = []
    monkeypatch.setattr(coletar, "get_todos", lambda c, **p: chamadas.append(p) or [{"id": 2, "siglaTipo": "PEC", "numero": 5, "ano": 2025, "ementa": "nova"}])
    itens = coletar.coletar_proposicoes({"id": 7, "nome": "F"})
    assert [(p["id"], p["ementa"]) for p in itens] == [(2, "nova"), (1, "guardada")]
    assert chamadas[0]["dataApresentacaoInicio"] == (hoje - dt.timedelta(days=30)).isoformat()      # incremental
    assert json.loads((dados / "proposicoes" / "7.json").read_text())["ids"] == [2, 1]


# ---------------------------------------------------------------- Câmara: detalhes das proposições

def test_detalhes_proposicoes_prioriza_novas_e_marca_situacao_final(dados, monkeypatch):
    coletar.salvar(dados / "proposicoes" / "1.json", {"ate": "x", "itens": [
        {"id": 10, "siglaTipo": "PL"}, {"id": 11, "siglaTipo": "REQ"}, {"id": 12, "siglaTipo": "PEC"}]})
    monkeypatch.setattr(coletar, "ORCAMENTO_DETALHES", 10)
    resp = {
        "/proposicoes/10": {"dados": {"dataApresentacao": "2025-01-02T10:00", "ementaDetalhada": " det ", "keywords": "a, b",
                                       "urlInteiroTeor": "http://pdf",
                                       "statusProposicao": {"descricaoSituacao": "Arquivada", "descricaoTramitacao": "Arquivamento",
                                                            "despacho": " Arquive-se ", "siglaOrgao": "MESA", "dataHora": "2025-02-03T09:00", "regime": "Ordinário",
                                                            "uriUltimoRelator": "https://dadosabertos.camara.leg.br/api/v2/deputados/220645"}}},
        "/proposicoes/12": {"dados": {"dataApresentacao": "2025-03-04", "statusProposicao": {"descricaoSituacao": "Aguardando Parecer"}}},
    }
    chamadas = roteador(monkeypatch, resp)
    coletar.coletar_detalhes_proposicoes()
    assert sorted(c[0] for c in chamadas) == ["/proposicoes/10", "/proposicoes/12"]  # REQ não é projeto principal
    cache = json.loads((dados / "proposicoes_detalhe.json").read_text())
    assert cache["10"]["finalizada"] is True and cache["10"]["situacao"] == "Arquivada"
    assert cache["10"]["dataApresentacao"] == "2025-01-02" and cache["10"]["dataSituacao"] == "2025-02-03"
    assert cache["10"]["despacho"] == "Arquive-se" and cache["10"]["ementaDetalhada"] == "det"
    assert cache["12"]["finalizada"] is False and cache["12"]["despacho"] is None
    assert cache["10"]["relator"] == "220645" and cache["12"]["relator"] is None


def test_detalhes_proposicoes_respeita_orcamento_e_renova_so_o_que_tramita(dados, monkeypatch):
    hoje = dt.date.today()
    velho = (hoje - dt.timedelta(days=30)).isoformat()
    coletar.salvar(dados / "proposicoes" / "1.json", {"itens": [{"id": i, "siglaTipo": "PL"} for i in (1, 2, 3)]})
    coletar.salvar(dados / "proposicoes_detalhe.json", {"1": {"consultadoEm": velho, "finalizada": True}, "2": {"consultadoEm": velho, "finalizada": False}, "3": {"consultadoEm": hoje.isoformat(), "finalizada": False}})
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
        {"codSenador": 1, "mes": 1, "tipoDespesa": "Aluguel", "valorReembolsado": 100, "fornecedor": "A", "cpfCnpj": "02.964.380/0001-00", "data": "2025-01-05"},
        {"codSenador": 1, "mes": 3, "tipoDespesa": "Passagem", "valorReembolsado": None, "fornecedor": "B", "data": "2025-03-05"},
        {"codSenador": None, "valorReembolsado": 5},
    ])
    coletar.coletar_ceaps_senado()
    r = json.loads((dados / "senado_ceaps.json").read_text())
    assert list(r["itens"]) == ["1"]
    assert [i["data"] for i in r["itens"]["1"]] == ["2025-03-05", "2025-01-05"]
    assert r["itens"]["1"][0]["valor"] == 0
    assert r["itens"]["1"][1]["cnpj"] == "02964380000100" and r["itens"]["1"][0]["cnpj"] is None


def test_recursos_senado_liga_escritorio_por_nome_e_uf_e_ignora_zerados(dados, monkeypatch):
    (dados / "senado.json").write_text(json.dumps([{"id": "7", "nome": "João Álvares", "uf": "AC"}]), encoding="utf-8")
    recursos = {"data": [{"gastosNaoInclusos": {"despesas": [{"recurso": "Correios", "valor": 10}, {"recurso": "Material", "valor": 0}], "totalValor": 10},
                          "beneficios": [{"beneficio": "Imóvel Funcional", "utilizacao": "Utilizou"}],
                          "pessoal": [{"local": "Gabinete", "quantidade": 3}]}]}
    escritorios = {"data": [{"parlamentar": {"nome": "JOAO ALVARES", "estado": "AC"}, "setor": {"nome": "Escritório 1", "endereco": "Rua A", "telefone": None}},
                            {"parlamentar": {"nome": "JOAO ALVARES", "estado": "SP"}, "setor": {"endereco": "Rua B"}}]}
    monkeypatch.setattr(coletar.S, "get", lambda url, **k: Resp(escritorios if "escritorios" in url else recursos))
    coletar.coletar_recursos_senado()
    r = json.loads((dados / "senado_recursos.json").read_text(encoding="utf-8"))
    assert r["recursos"]["7"]["foraCota"] == [["Correios", 10]] and r["recursos"]["7"]["pessoal"] == [["Gabinete", 3]]
    assert r["escritorios"] == {"7": [{"nome": "Escritório 1", "endereco": "Rua A"}]}


def votacao_s(codigo, data, voto="Sim", **extra):
    """Votação no formato do endpoint /votacao."""
    return {"codigoSessaoVotacao": codigo, "dataSessao": data, "identificacao": "PL 1/2025", "codigoMateria": 10, "resultadoVotacao": "A",
            "votos": [{"codigoParlamentar": 1, "siglaVotoParlamentar": voto, "descricaoVotoParlamentar": None}], **extra}


def ano_atual(monkeypatch):
    ano = dt.date.today().year
    monkeypatch.setattr(coletar, "INICIO_LEGISLATURA", f"{ano}-01-01")
    return ano


def test_votacoes_senado_consulta_o_endpoint_votacao_por_datas(dados, monkeypatch):
    ano = ano_atual(monkeypatch)
    chamadas = []

    def get_senado(caminho, **p):
        chamadas.append((caminho, p))
        return [votacao_s(1, f"{ano}-01-10"), {"semVotos": True}]

    monkeypatch.setattr(coletar, "get_senado", get_senado)
    coletar.coletar_votacoes_senado()
    assert chamadas == [("/votacao", {"dataInicio": f"{ano}-01-01", "dataFim": min(dt.date(ano, 12, 31), dt.date.today()).isoformat()})]
    salvo = json.loads((dados / "senado_votacoes" / f"{ano}.json").read_text())
    assert list(salvo) == ["1"] and salvo["1"]["votos"][0][:2] == ["1", "sim"]
    assert "sim" in json.loads((dados / "senado_votacoes" / "_rotulos.json").read_text())


def test_votacoes_senado_so_guarda_votacoes_do_proprio_ano(dados, monkeypatch):
    ano = ano_atual(monkeypatch)
    monkeypatch.setattr(coletar, "get_senado", lambda c, **p: [votacao_s(1, f"{ano}-02-01"), votacao_s(2, f"{ano - 1}-12-31")])
    coletar.coletar_votacoes_senado()
    assert list(json.loads((dados / "senado_votacoes" / f"{ano}.json").read_text())) == ["1"]


def test_votacoes_senado_preserva_o_que_ja_estava_salvo(dados, monkeypatch):
    ano = ano_atual(monkeypatch)
    coletar.salvar(dados / "senado_votacoes" / f"{ano}.json", {"0": {"id": "0", "data": f"{ano}-01-01", "votos": [["1", "sim", "Sim|"]]}})
    monkeypatch.setattr(coletar, "get_senado", lambda c, **p: [votacao_s(1, f"{ano}-02-01")])
    coletar.coletar_votacoes_senado()
    assert sorted(json.loads((dados / "senado_votacoes" / f"{ano}.json").read_text())) == ["0", "1"]


def test_votacoes_senado_reclassifica_o_que_ja_estava_salvo(dados, monkeypatch):
    ano = ano_atual(monkeypatch)
    coletar.salvar(dados / "senado_votacoes" / f"{ano}.json",
                   {"0": {"id": "0", "data": f"{ano}-01-01", "votos": [["1", "nao", "P-NRV|Presente – Não registrou voto"]]}})
    monkeypatch.setattr(coletar, "get_senado", lambda c, **p: [])
    coletar.coletar_votacoes_senado()
    assert json.loads((dados / "senado_votacoes" / f"{ano}.json").read_text())["0"]["votos"][0][1] == "ausente"


def test_votacoes_senado_sem_resultado_avisa(dados, monkeypatch):
    ano = ano_atual(monkeypatch)
    monkeypatch.setattr(coletar, "get_senado", lambda c, **p: [])
    coletar.coletar_votacoes_senado()
    assert any(str(ano) in a for a in coletar.AVISOS)


def test_votacoes_senado_erro_http_avisa_sem_derrubar(dados, monkeypatch):
    ano = ano_atual(monkeypatch)
    monkeypatch.setattr(coletar, "get_senado", lambda c, **p: (_ for _ in ()).throw(RuntimeError("HTTP 502")))
    coletar.coletar_votacoes_senado()
    assert any("502" in a for a in coletar.AVISOS) and not (dados / "senado_votacoes" / f"{ano}.json").exists()


def processo_s(cod, identificacao, **extra):
    return {"id": cod * 10, "codigoMateria": cod, "identificacao": identificacao, "ementa": f" Ementa {cod} ", "autoria": "Senador Sena Dor (ABC/PE), Senador Outro (XYZ/SP)",
            "dataApresentacao": "2024-03-04", "situacaoAtual": "ARQUIVADA", "dataSituacaoAtual": "2025-01-02", "tramitando": "Não", **extra}


def test_autorias_senado_com_situacao_das_materias(dados, monkeypatch):
    coletar.salvar(dados / "senado.json", [{"id": "5001", "nome": "Sena Dor"}])
    chamadas = []

    def get_senado(caminho, **p):
        chamadas.append((caminho, p))
        return [processo_s(111, "PL 10/2024"), processo_s(112, "REQ 5/2025", autoria="Senador Outro (XYZ/SP), Senador Sena Dor (ABC/PE)"),
                processo_s(113, "PL 1/2018"),            # antes de 2019: ignorada
                processo_s(114, "PL 3/2025", situacaoAtual="AGUARDANDO DESPACHO", dataSituacaoAtual="2025-06-01")]

    monkeypatch.setattr(coletar, "get_senado", get_senado)
    coletar.coletar_autorias_senado()
    assert chamadas == [("/processo", {"codigoParlamentarAutor": "5001"})]
    aut = json.loads((dados / "senado_autorias.json").read_text())["5001"]
    assert [a["id"] for a in aut] == ["112", "114", "111"]   # 2025 (nº 5 antes do 3) e depois 2024
    pl = next(a for a in aut if a["id"] == "111")
    assert pl["principal"] is True and pl["ementa"] == "Ementa 111" and pl["dataApresentacao"] == "2024-03-04" and pl["situacao"] == "ARQUIVADA" and pl["dataSituacao"] == "2025-01-02"
    assert next(a for a in aut if a["id"] == "112")["principal"] is False   # o primeiro autor é outro
    cache = json.loads((dados / "senado_materias.json").read_text())
    assert sorted(cache) == ["111", "114"]   # REQ não é projeto
    assert cache["111"] == {"situacao": "ARQUIVADA", "dataSituacao": "2025-01-02", "dataApresentacao": "2024-03-04", "processo": 1110}
    assert cache["114"]["situacao"] == "AGUARDANDO DESPACHO"


def test_autorias_senado_coautoria_vira_uma_materia_so(dados, monkeypatch):
    coletar.salvar(dados / "senado.json", [{"id": "1", "nome": "A"}, {"id": "2", "nome": "B"}])
    monkeypatch.setattr(coletar, "get_senado", lambda c, **p: [processo_s(111, "PL 10/2024")])
    coletar.coletar_autorias_senado()
    assert len(json.loads((dados / "senado_materias.json").read_text())) == 1


def test_autorias_senado_falha_individual_nao_derruba_nem_apaga_o_cache(dados, monkeypatch):
    coletar.salvar(dados / "senado.json", [{"id": "1", "nome": "A"}, {"id": "2", "nome": "B"}])
    coletar.salvar(dados / "senado_materias.json", {"999": {"situacao": "APROVADA", "dataSituacao": None, "dataApresentacao": None, "processo": 1}})

    def get_senado(caminho, **p):
        if p["codigoParlamentarAutor"] == "1":
            raise RuntimeError("HTTP 503")
        return [processo_s(111, "PL 10/2024")]

    monkeypatch.setattr(coletar, "get_senado", get_senado)
    coletar.coletar_autorias_senado()
    assert list(json.loads((dados / "senado_autorias.json").read_text())) == ["2"]
    assert sorted(json.loads((dados / "senado_materias.json").read_text())) == ["111", "999"]
    assert coletar.AVISOS


def test_autorias_senado_sem_lista_de_senadores_nao_apaga_nada(dados):
    coletar.salvar(dados / "senado_materias.json", {"1": {"situacao": "X"}})
    with pytest.raises(RuntimeError, match="senadores vazia"):
        coletar.coletar_autorias_senado()
    assert json.loads((dados / "senado_materias.json").read_text()) == {"1": {"situacao": "X"}}


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


def test_votacoes_senado_consulta_de_novo_arquivos_sem_voto_secreto_e_placar(dados, monkeypatch):
    ano = ano_atual(monkeypatch)
    coletar.salvar(dados / "senado_votacoes" / f"{ano - 1}.json",
                   {"0": {"id": "0", "data": f"{ano - 1}-03-01", "votos": [["1", "sim", "Sim|"]]}})
    chamadas = []
    monkeypatch.setattr(coletar, "get_senado", lambda c, **p: chamadas.append(p["dataInicio"]) or [])
    coletar.coletar_votacoes_senado()
    assert chamadas[0] == f"{ano - 1}-01-01"


# ---------------------------------------------------------------- Câmara: autores das proposições

def _autor(nome, ordem, dep=None, proponente=0):
    uri = f"https://dadosabertos.camara.leg.br/api/v2/deputados/{dep}" if dep else None
    return {"uri": uri, "nome": nome, "ordemAssinatura": ordem, "proponente": proponente,
            "tipo": "Deputado(a)" if dep else "Órgão do Poder Executivo"}


def test_autores_da_resposta_acha_principal_e_ordena():
    r = coletar.autores_da_resposta([_autor("Bia", 2, 20), _autor("Ana", 1, 10, proponente=1), _autor("Poder Executivo", 3)])
    assert r == {"idPrincipal": 10, "autores": [[10, "Ana"], [20, "Bia"], [None, "Poder Executivo", "Órgão do Poder Executivo"]]}


def test_autores_da_resposta_principal_que_nao_e_deputado():
    r = coletar.autores_da_resposta([_autor("Comissão X", 1, proponente=1), _autor("Bia", 2, 20)])
    assert r["idPrincipal"] is None and r["autores"][0] == [None, "Comissão X", "Órgão do Poder Executivo"] and r["autores"][1] == [20, "Bia"]
    assert coletar.autores_da_resposta([]) == {"idPrincipal": None, "autores": []}


def test_autores_proposicoes_so_projetos_e_nao_reconsulta(dados, monkeypatch):
    coletar.salvar(dados / "proposicoes" / "1.json", {"itens": [
        {"id": 10, "siglaTipo": "PL"}, {"id": 11, "siglaTipo": "REQ"}, {"id": 12, "siglaTipo": "PEC"}]})
    coletar.salvar(dados / "proposicoes" / "2.json", {"itens": [{"id": 10, "siglaTipo": "PL"}]})  # compartilhada
    coletar.salvar(dados / "proposicoes_autores.json", {"12": {"idPrincipal": 5, "autores": [[5, "Cia"]]}})
    chamadas = roteador(monkeypatch, {"/proposicoes/10/autores": {"dados": [_autor("Ana", 1, 10, 1)]}})
    coletar.coletar_autores_proposicoes()
    assert [c[0] for c in chamadas] == ["/proposicoes/10/autores"]  # REQ fora, 12 já coletada, 10 uma vez só
    cache = json.loads((dados / "proposicoes_autores.json").read_text())
    assert cache == {"10": {"idPrincipal": 10, "autores": [[10, "Ana"]]}, "12": {"idPrincipal": 5, "autores": [[5, "Cia"]]}}


def test_autores_proposicoes_falha_da_api_mantem_arquivo_anterior(dados, monkeypatch):
    coletar.salvar(dados / "proposicoes" / "1.json", {"itens": [{"id": 10, "siglaTipo": "PL"}, {"id": 12, "siglaTipo": "PL"}]})
    coletar.salvar(dados / "proposicoes_autores.json", {"12": {"idPrincipal": 5, "autores": [[5, "Cia"]]}})
    roteador(monkeypatch, {"/proposicoes/10/autores": RuntimeError("HTTP 500")})
    coletar.coletar_autores_proposicoes()
    assert json.loads((dados / "proposicoes_autores.json").read_text()) == {"12": {"idPrincipal": 5, "autores": [[5, "Cia"]]}}
    assert coletar.AVISOS


def test_coletar_deputado_guarda_so_frentes_da_legislatura(dados, monkeypatch):
    monkeypatch.setattr(coletar, "coletar_proposicoes", lambda dep: [])
    roteador(monkeypatch, {"/deputados/7": DETALHE_DEP, "/deputados/7/despesas": {"dados": []}, "/deputados/7/frentes": {"dados": [
        {"id": 1, "titulo": " Frente A ", "idLegislatura": 57}, {"id": 2, "titulo": "Frente B", "idLegislatura": 56}]}})
    assert coletar.coletar_deputado({"id": 7, "nome": "F"}, 2025)["frentes"] == [{"id": 1, "titulo": "Frente A"}]


def test_coletar_deputado_frentes_falham_sem_derrubar(dados, monkeypatch):
    monkeypatch.setattr(coletar, "coletar_proposicoes", lambda dep: [])
    roteador(monkeypatch, {"/deputados/7": DETALHE_DEP, "/deputados/7/despesas": {"dados": []}, "/deputados/7/frentes": RuntimeError("fora")})
    d = coletar.coletar_deputado({"id": 7, "nome": "F"}, 2025)
    assert "frentes" not in d
    assert any("frentes" in a for a in coletar.AVISOS)


ROTAS_COMPLEMENTOS = {
    "/deputados/7": DETALHE_DEP, "/deputados/7/despesas": {"dados": []}, "/deputados/7/frentes": {"dados": []},
    "/deputados/7/profissoes": {"dados": [{"dataHora": "2019-02-06T18:58", "codTipoProfissao": 1, "titulo": " Empresário "},
                                          {"dataHora": None, "codTipoProfissao": None, "titulo": None}]},
    "/deputados/7/ocupacoes": {"dados": [{"titulo": " Diretor ", "entidade": "Cooperativa X", "entidadeUF": "AP", "entidadePais": "Brasil",
                                          "anoInicio": 2005, "anoFim": None},
                                         {"titulo": None, "entidade": "Sem título"}]},
    "/deputados/7/mandatosExternos": {"dados": [{"cargo": "Vereador(a)", "siglaUf": "AP", "municipio": "Macapá", "anoInicio": "2009",
                                                 "anoFim": "2016", "siglaPartidoEleicao": "PMDB"}]},
    "/deputados/7/historico": {"dados": [
        {"idLegislatura": 56, "dataHora": "2019-02-01T11:45", "siglaPartido": "PR", "situacao": "Exercício"},
        {"idLegislatura": 57, "dataHora": "2023-02-01T00:00", "siglaPartido": "ABC", "situacao": "Exercício", "condicaoEleitoral": "Titular",
         "descricaoStatus": "Posse"}]},
    "/deputados/7/discursos": {"dados": [{"dataHoraInicio": "2026-09-02T11:36", "tipoDiscurso": "PELA ORDEM", "faseEvento": {"titulo": "Ordem do Dia"},
                                          "sumario": "Orientou&nbsp;a bancada.", "urlTexto": None, "urlVideo": "https://v/1", "transcricao": "longa"}]},
}


def test_coletar_deputado_grava_complementos_da_ficha(dados, monkeypatch):
    monkeypatch.setattr(coletar, "coletar_proposicoes", lambda dep: [])
    chamadas = roteador(monkeypatch, ROTAS_COMPLEMENTOS)
    d = coletar.coletar_deputado({"id": 7, "nome": "F"}, 2025)
    assert d["profissoes"] == [{"titulo": "Empresário", "desde": "2019-02-06"}]
    assert d["ocupacoes"] == [{"titulo": "Diretor", "entidade": "Cooperativa X", "uf": "AP", "inicio": 2005, "fim": None}]
    assert d["mandatosExternos"] == [{"cargo": "Vereador(a)", "uf": "AP", "municipio": "Macapá", "inicio": "2009", "fim": "2016", "partido": "PMDB"}]
    assert d["historico"] == [{"data": "2023-02-01", "partido": "ABC", "situacao": "Exercício", "condicao": "Titular", "descricao": "Posse"}]
    assert d["discursos"] == [{"data": "2026-09-02", "tipo": "PELA ORDEM", "fase": "Ordem do Dia", "sumario": "Orientou a bancada.", "link": "https://v/1"}]
    assert d["complementosEm"] == dt.date.today().isoformat()
    discursos = next(p for c, p in chamadas if c == "/deputados/7/discursos")
    assert discursos["itens"] == coletar.DISCURSOS_RECENTES and discursos["dataInicio"] == coletar.INICIO_LEGISLATURA


def test_coletar_deputado_complementos_recentes_nao_consultam_de_novo(dados, monkeypatch):
    monkeypatch.setattr(coletar, "coletar_proposicoes", lambda dep: [])
    coletar.salvar(dados / "deputados" / "7.json", {"profissoes": [{"titulo": "Médico", "desde": None}], "mandatosExternos": [], "historico": [],
                                                    "discursos": [], "complementosEm": dt.date.today().isoformat()})
    chamadas = roteador(monkeypatch, ROTAS_COMPLEMENTOS)
    d = coletar.coletar_deputado({"id": 7, "nome": "F"}, 2025)
    assert d["profissoes"] == [{"titulo": "Médico", "desde": None}]
    assert not any(c[0].endswith(("/profissoes", "/ocupacoes", "/historico", "/discursos", "/mandatosExternos")) for c in chamadas)


def test_coletar_deputado_complemento_que_falha_mantem_o_anterior(dados, monkeypatch):
    monkeypatch.setattr(coletar, "coletar_proposicoes", lambda dep: [])
    antigo = (dt.date.today() - dt.timedelta(days=30)).isoformat()
    coletar.salvar(dados / "deputados" / "7.json", {"discursos": [{"data": "2026-01-01"}], "complementosEm": antigo})
    chamadas = roteador(monkeypatch, {**ROTAS_COMPLEMENTOS, "/deputados/7/discursos": RuntimeError("fora")})
    d = coletar.coletar_deputado({"id": 7, "nome": "F"}, 2025)
    assert d["discursos"] == [{"data": "2026-01-01"}] and d["profissoes"]
    assert d["complementosEm"] == antigo
    assert any("discursos" in a for a in coletar.AVISOS) and chamadas


def test_ficha_senador_filtra_comissoes_antigas_e_ordena_mandatos():
    comissoes = {"MembroComissaoParlamentar": {"Parlamentar": {"MembroComissoes": {"Comissao": [
        {"IdentificacaoComissao": {"CodigoComissao": "1", "SiglaComissao": "CAE", "NomeComissao": "Assuntos Econômicos", "SiglaCasaComissao": "SF"},
         "DescricaoParticipacao": "Titular", "DataInicio": "2023-02-02"},
        {"IdentificacaoComissao": {"CodigoComissao": "2", "SiglaComissao": "CCJ", "NomeComissao": "Justiça", "SiglaCasaComissao": "SF"},
         "DescricaoParticipacao": "Titular", "DataInicio": "2015-03-04", "DataFim": "2018-12-28"}]}}}}
    mandatos = {"MandatoParlamentar": {"Parlamentar": {"Mandatos": {"Mandato": [
        {"CodigoMandato": "475", "UfParlamentar": "AP", "DescricaoParticipacao": "Titular",
         "PrimeiraLegislaturaDoMandato": {"DataInicio": "2011-02-01", "DataFim": "2015-01-31"},
         "SegundaLegislaturaDoMandato": {"DataInicio": "2015-02-01", "DataFim": "2019-01-31"},
         "Partidos": {"Partido": {"Sigla": "PSOL", "DataFiliacao": "2011-01-28", "DataDesfiliacao": "2015-09-28"}}},
        {"CodigoMandato": "522", "UfParlamentar": "AP", "DescricaoParticipacao": "Titular",
         "PrimeiraLegislaturaDoMandato": {"DataInicio": "2019-02-01", "DataFim": "2023-01-31"},
         "SegundaLegislaturaDoMandato": {"DataInicio": "2023-02-01", "DataFim": "2027-01-31"},
         "Partidos": {"Partido": [{"Sigla": "REDE", "DataFiliacao": "2015-09-29", "DataDesfiliacao": "2024-01-23"},
                                  {"Sigla": "PT", "DataFiliacao": "2024-07-18"}]}}]}}}}
    ficha = coletar.ficha_senador(comissoes, mandatos)
    assert ficha["comissoes"] == [{"codigo": "1", "sigla": "CAE", "nome": "Assuntos Econômicos", "casa": "SF", "cargo": "Titular", "inicio": "2023-02-02", "fim": None}]
    assert [m["codigo"] for m in ficha["mandatos"]] == ["522", "475"]
    assert ficha["mandatos"][0]["fim"] == "2027-01-31"
    assert [x["sigla"] for x in ficha["mandatos"][0]["partidos"]] == ["PT", "REDE"]
    assert ficha["mandatos"][1]["partidos"][0]["sigla"] == "PSOL"


def test_coletar_ficha_senado_grava_por_senador_e_avisa_falha(dados, monkeypatch):
    coletar.salvar(dados / "senado.json", [{"id": 1, "nome": "A"}, {"id": 2, "nome": "B"}])

    def falso(caminho, **params):
        if caminho.startswith("/senador/2/"):
            raise RuntimeError("HTTP 503")
        return {}

    monkeypatch.setattr(coletar, "get_senado", falso)
    coletar.coletar_ficha_senado()
    assert json.loads((dados / "senado_ficha.json").read_text()) == {"1": {"comissoes": [], "mandatos": []}}
    assert any("ficha de senador" in a for a in coletar.AVISOS)


def test_coletar_temas_proposicoes_agrupa_por_projeto_e_ignora_requerimento(dados, monkeypatch):
    uri = "https://dadosabertos.camara.leg.br/api/v2/proposicoes/"
    linhas = [
        {"uriProposicao": uri + "10", "siglaTipo": "PL", "tema": "Saúde", "relevancia": 0},
        {"uriProposicao": uri + "10", "siglaTipo": "PL", "tema": "Educação", "relevancia": 5},
        {"uriProposicao": uri + "10", "siglaTipo": "PL", "tema": "Educação", "relevancia": 1},
        {"uriProposicao": uri + "11", "siglaTipo": "REQ", "tema": "Saúde", "relevancia": 0},
    ]
    anos = []
    monkeypatch.setattr(coletar, "baixar_arquivo_camara", lambda c: anos.append(c) or (linhas if "2023" in c else (_ for _ in ()).throw(RuntimeError("x"))))
    class Hoje(dt.date):
        @classmethod
        def today(cls):
            return cls(2024, 5, 1)
    monkeypatch.setattr(coletar.dt, "date", Hoje)
    coletar.coletar_temas_proposicoes()
    assert json.loads((dados / "proposicoes_temas.json").read_text(encoding="utf-8")) == {"10": ["Educação", "Saúde"]}
    assert len(anos) == 2 and len(coletar.AVISOS) == 1


def test_coletar_orgaos_deputados_agrupa_por_deputado(dados, monkeypatch):
    dep = "https://dadosabertos.camara.leg.br/api/v2/deputados/"
    monkeypatch.setattr(coletar, "baixar_arquivo_camara", lambda c: [
        {"siglaOrgao": "CSAUDE", "nomeOrgao": "Comissão de Saúde", "nomePublicacaoOrgao": "Saúde", "uriDeputado": dep + "7",
         "cargo": "Titular", "dataInicio": "2025-03-01", "dataFim": ""},
        {"siglaOrgao": "", "uriDeputado": dep + "7"}, {"siglaOrgao": "X", "uriDeputado": "sem-id"}])
    coletar.coletar_orgaos_deputados()
    assert json.loads((dados / "orgaos_deputados.json").read_text(encoding="utf-8")) == {
        "7": [{"sigla": "CSAUDE", "nome": "Saúde", "cargo": "Titular", "inicio": "2025-03-01", "fim": None}]}


def test_coletar_orientacoes_guarda_so_nominais_e_ignora_em_branco(dados, monkeypatch):
    (dados / "votacoes").mkdir()
    (dados / "votacoes" / "2026.json").write_text(json.dumps({
        "1-1": {"id": "1-1", "data": "2026-03-01", "votos": [["7", "Sim"]]},
        "2-2": {"id": "2-2", "data": "2026-03-02", "votos": []}}), encoding="utf-8")
    monkeypatch.setattr(coletar, "baixar_arquivo_camara", lambda c: [
        {"idVotacao": "1-1", "siglaBancada": "PL", "orientacao": "Sim"},
        {"idVotacao": "1-1", "siglaBancada": "Governo", "orientacao": "Não"},
        {"idVotacao": "1-1", "siglaBancada": "Oposição", "orientacao": ""},
        {"idVotacao": "2-2", "siglaBancada": "PL", "orientacao": "Sim"}])
    coletar.coletar_orientacoes()
    assert json.loads((dados / "orientacoes.json").read_text(encoding="utf-8")) == {"1-1": {"PL": "Sim", "Governo": "Não"}}


def test_coletar_blocos_guarda_partidos_de_cada_bloco(dados, monkeypatch):
    monkeypatch.setattr(coletar, "get_todos", lambda c, **p: [{"id": "1", "nome": "A, B", "federacao": False}, {"id": "2", "nome": "PL", "federacao": False}])
    monkeypatch.setattr(coletar, "get", lambda c, **p: {"dados": [{"sigla": "A"}, {"sigla": "B"}] if c.endswith("/1/partidos") else []})
    coletar.coletar_blocos()
    assert json.loads((dados / "blocos.json").read_text(encoding="utf-8")) == [
        {"nome": "A, B", "federacao": False, "partidos": ["A", "B"]}, {"nome": "PL", "federacao": False, "partidos": []}]


def test_coletar_votacoes_proposicoes_guarda_so_projetos_dos_deputados(dados, monkeypatch):
    (dados / "proposicoes").mkdir()
    (dados / "proposicoes" / "7.json").write_text(json.dumps({"itens": [{"id": 10, "siglaTipo": "PL"}, {"id": 11, "siglaTipo": "REQ"}]}), encoding="utf-8")
    monkeypatch.setattr(coletar, "baixar_arquivo_camara", lambda c: [
        {"idVotacao": "10-1", "data": "2026-02-01", "descricao": "Aprovado.", "proposicao_": {"id": 10}},
        {"idVotacao": "10-1", "data": "2026-02-01", "descricao": "Aprovado.", "proposicao_": {"id": 10}},
        {"idVotacao": "11-1", "data": "2026-02-01", "descricao": "x", "proposicao_": {"id": 11}},
        {"idVotacao": "99-1", "data": "2026-02-01", "descricao": "x", "proposicao_": {"id": 99}}])
    coletar.coletar_votacoes_proposicoes()
    assert json.loads((dados / "proposicoes_votacoes.json").read_text(encoding="utf-8")) == {
        "10": [{"id": "10-1", "data": "2026-02-01", "descricao": "Aprovado."}]}


def test_tipo_evento_separa_sessoes_comissoes_e_outros():
    assert [coletar.tipo_evento(t) for t in ("Sessão Deliberativa", "Reunião Deliberativa", "Audiência Pública", "Sessão Não Deliberativa Solene", None)] == [
        "sessoes", "comissoes", "comissoes", "outros", "outros"]


def test_coletar_presenca_eventos_conta_por_tipo_sem_repetir(dados, monkeypatch):
    hoje = dt.date.today()
    monkeypatch.setattr(coletar, "INICIO_LEGISLATURA", f"{hoje.year}-02-01")

    def baixar(caminho):
        if caminho.startswith("eventos/"):
            return [{"id": 1, "descricaoTipo": "Sessão Deliberativa", "situacao": "Encerrada"},
                    {"id": 2, "descricaoTipo": "Sessão Deliberativa", "situacao": "Cancelada"},
                    {"id": 3, "descricaoTipo": "Reunião Deliberativa", "situacao": "Encerrada (Final)"}]
        return [{"idEvento": 1, "idDeputado": 7}, {"idEvento": 1, "idDeputado": 7}, {"idEvento": 3, "idDeputado": 7}, {"idEvento": 9, "idDeputado": 8}]
    monkeypatch.setattr(coletar, "baixar_arquivo_camara", baixar)
    coletar.coletar_presenca_eventos()
    assert json.loads((dados / "presenca_eventos.json").read_text(encoding="utf-8")) == {str(hoje.year): {
        "sessoesDeliberativas": 1, "deputados": {"7": {"sessoes": 1, "comissoes": 1, "outros": 0}, "8": {"sessoes": 0, "comissoes": 0, "outros": 1}}}}


def test_cota_csv_cnpj_invalido_ou_mascarado_vira_none():
    cota = coletar.comum.fornecedor("Cia", "12.345.678/0001-90")
    assert cota == {"fornecedor": "Cia", "cnpj": None}
    assert coletar.comum.fornecedor("Fulano", "***.123.456-**")["cnpj"] is None


def test_tramitacao_da_resposta_ordena_acha_relator_e_relacionadas():
    tram = [
        {"dataHora": "2026-02-01T10:00", "sequencia": 2, "siglaOrgao": "CCJC", "descricaoTramitacao": "Designação de Relator(a)",
         "descricaoSituacao": "Aguardando Parecer", "despacho": "Designada Relatora, Dep. Ana Souza (PP-PI)"},
        {"dataHora": "2026-01-01T09:00", "sequencia": 1, "siglaOrgao": "MESA", "descricaoTramitacao": "Apresentação", "despacho": ""},
    ]
    rel = [{"uri": "https://dadosabertos.camara.leg.br/api/v2/proposicoes/20", "siglaTipo": "PL", "numero": "5", "ano": "2025"}, {"uri": None}]
    r = coletar.tramitacao_da_resposta(tram, rel)
    assert r["eventos"][0] == ["2026-01-01", "MESA", "Apresentação", None, None]
    assert r["relator"] == "Ana Souza (PP-PI)"
    assert r["relacionadas"] == [["20", "PL 5/2025"]]


def test_tramitacoes_proposicoes_nao_reconsulta_finalizada(dados, monkeypatch):
    coletar.salvar(dados / "proposicoes" / "1.json", {"itens": [{"id": 10, "siglaTipo": "PL"}, {"id": 12, "siglaTipo": "PL"}]})
    coletar.salvar(dados / "proposicoes_tramitacoes.json", {"12": {"eventos": [], "consultadoEm": "2020-01-01"}})
    coletar.salvar(dados / "proposicoes_detalhe.json", {"12": {"finalizada": True}})
    chamadas = roteador(monkeypatch, {"/proposicoes/10/tramitacoes": {"dados": []}, "/proposicoes/10/relacionadas": {"dados": []}})
    coletar.coletar_tramitacoes_proposicoes()
    assert [c[0] for c in chamadas] == ["/proposicoes/10/tramitacoes", "/proposicoes/10/relacionadas"]
    assert set(json.loads((dados / "proposicoes_tramitacoes.json").read_text())) == {"10", "12"}
