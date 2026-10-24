"""Respostas simuladas da API da Câmara (Executivo) e dos SAPL das Assembleias/Câmaras municipais."""
import datetime as dt
import json

import pytest

import coletar_estaduais as est
import coletar_executivo as ex
import coletar_prefeituras as pref


# ================================================================ Executivo

@pytest.mark.parametrize("sit,esperado", [
    ("Transformado na Lei Ordinária 15421/2026", True), ("Vetado totalmente", True), ("Perdeu a Eficácia", True),
    ("Arquivada", True), ("Aguardando Sanção", False), ("", False), (None, False),
    ("Pronta para Pauta (transformada)", False),  # só vale o início da frase
])
def test_executivo_final(sit, esperado):
    assert ex.final(sit) is esperado


def tramitacoes(*itens):
    return {"dados": list(itens)}


def test_desfecho_extrai_lei_e_veto_parcial(monkeypatch):
    monkeypatch.setattr(ex, "get", lambda c, **p: tramitacoes(
        {"despacho": "Remeta-se", "descricaoSituacao": "Em tramitação", "dataHora": "2025-01-01T10:00"},
        {"despacho": "Transformado na Lei Ordinária 15421/2026. Vetado parcialmente.", "descricaoSituacao": "Transformado em Norma Jurídica",
         "dataHora": "2026-05-06T12:00"}))
    assert ex.desfecho(1) == {"tramitacaoLida": True, "norma": "Lei Ordinária 15421/2026", "dataNorma": "2026-05-06", "veto": "parcial"}


def test_desfecho_remessa_a_sancao_razoes_do_veto_e_edicao_da_mp(monkeypatch):
    monkeypatch.setattr(ex, "get", lambda c, **p: tramitacoes(
        {"despacho": "Publicação da Medida Provisória no Diário Oficial da União.", "dataHora": "2026-03-19T00:00"},
        {"despacho": "Recebido Ofício que comunica remessa de Projeto de Lei à sanção.", "dataHora": "2026-05-28T00:00"},
        {"despacho": "Transformado na Lei Ordinária 15421/2026. Vetado parcialmente. MSC-PE 499/26. Razões do veto: DOU 02/06/2026 PÁG 07 COL 01.",
         "descricaoSituacao": "Transformado em Norma Jurídica", "dataHora": "2026-06-01T12:00"}))
    r = ex.desfecho(1)
    assert r["dataEdicao"] == "2026-03-19" and r["remessa"] == "2026-05-28"
    assert r["razoesVeto"] == "DOU 02/06/2026 PÁG 07 COL 01" and r["mensagemVeto"] == "499/26"


def test_desfecho_emenda_constitucional_e_veto_total(monkeypatch):
    monkeypatch.setattr(ex, "get", lambda c, **p: tramitacoes(
        {"despacho": "Transformada na Emenda Constitucional 130/2025", "dataHora": "2025-02-02T00:00"}))
    r = ex.desfecho(1)
    assert r["norma"] == "Emenda Constitucional 130/2025" and r["veto"] is None
    monkeypatch.setattr(ex, "get", lambda c, **p: tramitacoes({"despacho": "Vetado totalmente.", "descricaoSituacao": "Aguardando Apreciação de Veto", "dataHora": "2025-02-02T00:00"}))
    assert ex.desfecho(1) == {"tramitacaoLida": True, "norma": None, "dataNorma": "2025-02-02", "veto": "total"}


def test_desfecho_sem_norma(monkeypatch):
    monkeypatch.setattr(ex, "get", lambda c, **p: tramitacoes({"despacho": "Aguarda", "descricaoSituacao": "Em tramitação"}))
    assert ex.desfecho(1) == {"tramitacaoLida": True}


def prop_api(id_, sit, tipo="PL"):
    return {"dados": {"siglaTipo": tipo, "numero": id_, "ano": 2026, "ementa": f" ementa {id_} ", "dataApresentacao": "2026-03-01T09:00",
                      "urlInteiroTeor": "http://pdf", "statusProposicao": {"descricaoSituacao": sit, "dataHora": "2026-04-02T10:00"}}}


def test_detalhar(monkeypatch):
    monkeypatch.setattr(ex, "get", lambda c, **p: prop_api(5, "Aguardando Parecer"))
    d = ex.detalhar({"id": 5})
    assert d == {"id": 5, "tipo": "PL", "numero": 5, "ano": 2026, "ementa": "ementa 5", "dataApresentacao": "2026-03-01",
                 "situacao": "Aguardando Parecer", "dataSituacao": "2026-04-02", "inteiroTeor": "http://pdf"}


def test_detalhar_busca_desfecho_so_quando_transformada(monkeypatch):
    chamadas = []

    def get(c, **p):
        chamadas.append(c)
        if c.endswith("/tramitacoes"):
            return tramitacoes({"despacho": "Transformado na Lei Ordinária 1/2026", "dataHora": "2026-05-01T00:00"})
        return prop_api(5, "Transformado em Norma Jurídica")

    monkeypatch.setattr(ex, "get", get)
    assert ex.detalhar({"id": 5})["norma"] == "Lei Ordinária 1/2026"
    assert any(c.endswith("/tramitacoes") for c in chamadas)


@pytest.fixture
def arquivo_exec(tmp_path, monkeypatch):
    monkeypatch.setattr(ex, "ARQUIVO", tmp_path / "executivo.json")
    monkeypatch.setattr(ex, "ANO_INICIAL", dt.date.today().year)
    monkeypatch.setattr(ex, "TIPOS", ("PL",))
    return ex.ARQUIVO


def test_executivo_main_salva_ordenado_por_apresentacao(arquivo_exec, monkeypatch):
    monkeypatch.setattr(ex, "get_todos", lambda c, **p: [{"id": 1}, {"id": 2}])
    monkeypatch.setattr(ex, "detalhar", lambda p: {"id": p["id"], "dataApresentacao": f"2026-0{p['id']}-01", "situacao": "Em tramitação"})
    ex.main()
    assert [p["id"] for p in json.loads(arquivo_exec.read_text(encoding="utf-8"))] == [2, 1]


def test_executivo_main_reaproveita_finais_sem_consultar(arquivo_exec, monkeypatch):
    arquivo_exec.write_text(json.dumps([{"id": 1, "dataApresentacao": "2026-01-01", "situacao": "Arquivada"}]), encoding="utf-8")
    monkeypatch.setattr(ex, "get_todos", lambda c, **p: [{"id": 1}, {"id": 2}])
    consultados = []
    monkeypatch.setattr(ex, "detalhar", lambda p: consultados.append(p["id"]) or {"id": p["id"], "dataApresentacao": "2026-02-01", "situacao": "x"})
    ex.main()
    assert consultados == [2]
    assert {p["id"] for p in json.loads(arquivo_exec.read_text(encoding="utf-8"))} == {1, 2}


def test_executivo_main_erro_de_detalhe_mantem_versao_antiga(arquivo_exec, monkeypatch):
    arquivo_exec.write_text(json.dumps([{"id": 1, "dataApresentacao": "2026-01-01", "situacao": "Em tramitação"}]), encoding="utf-8")
    monkeypatch.setattr(ex, "get_todos", lambda c, **p: [{"id": 1}])
    monkeypatch.setattr(ex, "detalhar", lambda p: (_ for _ in ()).throw(RuntimeError("HTTP 500")))
    ex.main()
    assert json.loads(arquivo_exec.read_text(encoding="utf-8"))[0]["situacao"] == "Em tramitação"


def test_executivo_main_nada_coletado_nao_apaga_arquivo(arquivo_exec, monkeypatch):
    arquivo_exec.write_text(json.dumps([{"id": 1, "dataApresentacao": "2026-01-01", "situacao": "x"}]), encoding="utf-8")
    monkeypatch.setattr(ex, "get_todos", lambda c, **p: (_ for _ in ()).throw(RuntimeError("API fora")))
    ex.main()
    assert json.loads(arquivo_exec.read_text(encoding="utf-8")) == [{"id": 1, "dataApresentacao": "2026-01-01", "situacao": "x"}]


# ================================================================ SAPL (Assembleias)

class SaplFalso:
    """Simula a API REST do SAPL: listagens paginadas ({results, pagination}) e itens por id."""

    def __init__(self, **colecoes):
        self.colecoes = colecoes
        self.chamadas = []

    def get(self, host, caminho, **params):
        self.chamadas.append((caminho.strip("/"), params))
        c = self.colecoes[caminho.strip("/")]
        if isinstance(c, Exception):
            raise c
        if callable(c):
            return c(**params)
        if isinstance(c, list):
            tam, pag = params.get("page_size", 100), params.get("page", 1)
            filtro = {k: v for k, v in params.items() if k not in ("page", "page_size")}
            itens = [i for i in c if all(i.get(k) == v for k, v in filtro.items() if k in i or k in ("ano", "tipo"))] if filtro else c
            ini = (pag - 1) * tam
            return {"results": itens[ini:ini + tam], "pagination": {"next_page": pag + 1 if ini + tam < len(itens) else None}}
        return c


@pytest.fixture
def sapl(monkeypatch, tmp_path):
    monkeypatch.setattr(est, "DADOS", tmp_path / "estaduais")
    monkeypatch.setattr(pref, "DADOS", tmp_path / "municipais")

    def instalar(**colecoes):
        s = SaplFalso(**colecoes)
        monkeypatch.setattr(est, "get", s.get)
        return s

    return instalar


def test_paginar_percorre_todas_as_paginas(sapl):
    s = sapl(x=[{"i": n} for n in range(250)])
    assert [r["i"] for r in est.paginar("h", "x")] == list(range(250))
    assert [c[1]["page"] for c in s.chamadas] == [1, 2, 3]


def test_helpers():
    assert est.https("http://a/b") == "https://a/b" and est.https(None) is None
    assert est.data_curta("2025-03-04T10:00:00") == "2025-03-04" and est.data_curta(None) is None
    assert est.sem_acento("  São  JOSÉ ") == "sao jose"


@pytest.mark.parametrize("m,esperado", [
    ({"em_tramitacao": True, "resultado": "Aprovado"}, "Em tramitação"),
    ({"em_tramitacao": False, "resultado": " Aprovado "}, "Aprovado"),
    ({"em_tramitacao": False, "resultado": ""}, "Tramitação encerrada"),
    ({"em_tramitacao": False}, "Tramitação encerrada"),
])
def test_situacao(m, esperado):
    assert est.situacao(m) == esperado


def test_compactar_materia():
    r = est.compactar_materia({"tipo": 1, "numero": 10, "ano": 2026, "data_apresentacao": "2026-02-01", "ementa": " e ", "em_tramitacao": True,
                               "texto_original": "http://pdf", "autores": [3]}, {1: {"sigla": "PL", "descricao": "Projeto de Lei"}})
    assert r == {"tipo": "PL", "tipoDescricao": "Projeto de Lei", "numero": 10, "ano": 2026, "dataApresentacao": "2026-02-01", "ementa": "e",
                 "situacao": "Em tramitação", "emTramitacao": True, "linkTexto": "https://pdf", "idsAutores": [3]}
    desconhecido = est.compactar_materia({"tipo": 99, "numero": 1, "ano": 2026}, {})
    assert desconhecido["tipo"] == "?" and desconhecido["linkTexto"] is None and desconhecido["idsAutores"] == []


@pytest.mark.parametrize("nome,nat,esperado", [
    ("Aprovado", "A", 1), ("Rejeitado", "R", 0), ("Não votado", "A", None), ("Retirado de pauta", "R", None), ("Outro", "X", None),
])
def test_resultado_aprovado(nome, nat, esperado):
    assert est.resultado_aprovado(nome, nat) == esperado


def test_legislatura_atual(sapl):
    hoje = dt.date.today()
    sapl(**{"parlamentares/legislatura": {"results": [
        {"id": 1, "numero": 1, "data_inicio": "2000-01-01", "data_fim": "2001-01-01"},
        {"id": 2, "numero": 2, "data_inicio": (hoje - dt.timedelta(days=5)).isoformat(), "data_fim": (hoje + dt.timedelta(days=5)).isoformat()}]}})
    assert est.legislatura_atual("h")["id"] == 2


def test_legislatura_atual_inexistente(sapl):
    sapl(**{"parlamentares/legislatura": {"results": [{"id": 1, "numero": 1, "data_inicio": "2000-01-01", "data_fim": "2001-01-01"}]}})
    with pytest.raises(RuntimeError, match="legislatura"):
        est.legislatura_atual("h")


def test_coletar_deputados_so_mandatos_em_vigor_e_pula_erro(sapl):
    hoje = dt.date.today()
    ontem, amanha = (hoje - dt.timedelta(days=1)).isoformat(), (hoje + dt.timedelta(days=1)).isoformat()

    def parlamentar(pid):
        raise RuntimeError("HTTP 404")

    sapl(**{
        "parlamentares/mandato": [
            {"parlamentar": 1, "data_inicio_mandato": "2023-02-01", "data_fim_mandato": amanha, "titular": True},
            {"parlamentar": 2, "data_inicio_mandato": "2023-02-01", "data_fim_mandato": ontem, "titular": True},   # expirado
            {"parlamentar": 3, "data_inicio_mandato": ontem, "data_fim_mandato": None, "titular": False},          # suplente em exercício
            {"parlamentar": 4, "data_inicio_mandato": "2023-02-01", "data_fim_mandato": amanha, "titular": True},  # falha ao buscar
        ],
        "parlamentares/parlamentar/1": {"nome_parlamentar": "Um", "nome_completo": "Um Completo", "fotografia": "http://f", "email": ""},
        "parlamentares/parlamentar/3": {"nome_parlamentar": "Tres", "nome_completo": "T", "fotografia": None, "email": "t@x"},
        "parlamentares/parlamentar/4": RuntimeError("HTTP 500"),
    })
    deps = est.coletar_deputados("h", {"id": 7})
    assert [d["id"] for d in deps] == [1, 3]
    assert deps[0] == {"id": 1, "nome": "Um", "nomeCivil": "Um Completo", "foto": "https://f", "email": None, "titular": True}
    assert deps[1]["titular"] is False


def test_mapa_autores_so_parlamentares_em_exercicio(sapl):
    sapl(**{"base/tipoautor": [{"id": 1, "descricao": " Parlamentar "}, {"id": 2, "descricao": "Órgão"}],
            "base/autor": [{"id": 10, "tipo": 1, "object_id": 100}, {"id": 11, "tipo": 1, "object_id": 999},
                           {"id": 12, "tipo": 2, "object_id": 100}, {"id": 13, "tipo": 1}]})
    assert est.mapa_autores("h", {100: {}}) == {10: 100}


def test_coletar_materias_filtra_tipo_e_autoria(sapl, monkeypatch):
    ano = dt.date.today().year
    mats = [
        {"id": 1, "tipo": 1, "ano": ano, "numero": 1, "autores": [10], "em_tramitacao": True},
        {"id": 2, "tipo": 1, "ano": ano, "numero": 2, "autores": [55]},          # autor não é deputado
        {"id": 3, "tipo": 1, "ano": ano, "numero": 3, "autores": [10, 11]},
    ]
    s = sapl(**{"materia/materialegislativa": mats})
    tipos = {1: {"sigla": "PL", "descricao": "Projeto de Lei"}, 2: {"sigla": "REQ", "descricao": "Requerimento"}}
    est.coletar_materias("h", "PB", {"data_inicio": f"{ano}-01-01"}, {10: 100, 11: 101}, tipos)
    salvo = json.loads((est.DADOS / "PB" / f"materias_{ano}.json").read_text(encoding="utf-8"))["materias"]
    assert sorted(salvo) == ["1", "3"]
    assert salvo["3"]["idsDeputados"] == [100, 101] and salvo["1"]["tipo"] == "PL"
    assert all(c[1].get("tipo") != 2 for c in s.chamadas if c[0] == "materia/materialegislativa")  # requerimentos nem são consultados


def test_coletar_materias_ano_antigo_recente_vem_do_cache(sapl):
    ano = dt.date.today().year
    ontem = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    est.salvar(est.DADOS / "PB" / f"materias_{ano - 1}.json", {"coletadoEm": ontem, "materias": {}})
    s = sapl(**{"materia/materialegislativa": []})
    est.coletar_materias("h", "PB", {"data_inicio": f"{ano - 1}-01-01"}, {}, {1: {"sigla": "PL", "descricao": "Projeto de Lei"}})
    anos = {c[1]["ano"] for c in s.chamadas if c[0] == "materia/materialegislativa"}
    assert anos == {ano}


def votos_api(votacao, parl, voto):
    return {"votacao": votacao, "parlamentar": parl, "voto": voto}


def test_coletar_votacoes_agrega_votos_e_resultado(sapl):
    registro = {"data_hora": "2026-05-04T10:00:00-03:00", "materia": 77, "tipo_resultado_votacao": 1,
                "numero_votos_sim": 20, "numero_votos_nao": 3, "numero_abstencoes": 1}
    sapl(**{"sessao/tiporesultadovotacao": [{"id": 1, "nome": "Aprovado", "natureza": "A"}],
            "sessao/votoparlamentar": [votos_api(5, 100, "Sim"), votos_api(5, 101, "Não"), votos_api(5, 999, "Sim"), votos_api(5, 100, ""), votos_api(6, 100, "Sim")],
            "sessao/registrovotacao/5": registro,
            "sessao/registrovotacao/6": RuntimeError("HTTP 500")})
    est.coletar_votacoes("h", "PB", {"data_inicio": "2023-02-01"}, {100: {}, 101: {}})
    v = json.loads((est.DADOS / "PB" / "votacoes.json").read_text(encoding="utf-8"))["votacoes"]
    assert list(v) == ["5"]  # a 6 falhou e é ignorada
    assert v["5"] == {"data": "2026-05-04", "idMateria": 77, "aprovada": 1, "resultado": "Aprovado", "sim": 20, "nao": 3, "abstencoes": 1, "votos": [[100, "Sim"], [101, "Não"]]}


def test_coletar_votacoes_incremental_comeca_14_dias_antes_da_ultima(sapl):
    est.salvar(est.DADOS / "PB" / "votacoes.json", {"votacoes": {"1": {"data": "2026-05-20", "votos": []}}})
    s = sapl(**{"sessao/tiporesultadovotacao": [], "sessao/votoparlamentar": []})
    est.coletar_votacoes("h", "PB", {"data_inicio": "2023-02-01"}, {})
    filtro = next(p for c, p in s.chamadas if c == "sessao/votoparlamentar")["data_hora__gte"]
    assert filtro == "2026-05-06"
    assert "1" in json.loads((est.DADOS / "PB" / "votacoes.json").read_text(encoding="utf-8"))["votacoes"]  # cache preservado


def test_coletar_materias_votadas_so_busca_o_que_falta(sapl):
    est.salvar(est.DADOS / "PB" / "votacoes.json", {"votacoes": {"a": {"idMateria": 1, "data": "x", "votos": []}, "b": {"idMateria": 2, "data": "x", "votos": []}, "c": {"idMateria": None, "data": "x", "votos": []}}})
    est.salvar(est.DADOS / "PB" / "materias_votadas.json", {"1": {"tipo": "PL"}})
    s = sapl(**{"materia/materialegislativa/2": {"tipo": 1, "numero": 9, "ano": 2026, "ementa": "x", "em_tramitacao": False}})
    est.coletar_materias_votadas("h", "PB", {1: {"sigla": "PL", "descricao": "Projeto"}})
    assert [c[0] for c in s.chamadas] == ["materia/materialegislativa/2"]
    r = json.loads((est.DADOS / "PB" / "materias_votadas.json").read_text(encoding="utf-8"))
    assert r["2"] == {"tipo": "PL", "tipoDescricao": "Projeto", "numero": 9, "ano": 2026, "ementa": "x"} and "1" in r


def test_coletar_assembleia_sem_deputados_falha(sapl):
    hoje = dt.date.today()
    sapl(**{"parlamentares/legislatura": {"results": [{"id": 1, "numero": 1, "data_inicio": "2000-01-01", "data_fim": (hoje + dt.timedelta(days=9)).isoformat()}]},
            "parlamentares/mandato": []})
    with pytest.raises(RuntimeError, match="nenhum deputado"):
        est.coletar_assembleia("PB", "h")


def test_main_estaduais_erro_em_uma_uf_nao_para_as_outras(monkeypatch):
    feitos = []

    def fake(uf, host):
        if uf == "PB":
            raise RuntimeError("fora")
        feitos.append(uf)

    monkeypatch.setattr(est, "coletar_assembleia", fake)
    monkeypatch.setattr("sys.argv", ["x", "pb", "am"])
    est.main()
    assert feitos == ["AM"]


def test_main_estaduais_roda_modulo_de_uf_e_isola_falha(monkeypatch):
    class Modulo:
        def __init__(self, uf, falha=False):
            self.UF, self.falha, self.rodou = uf, falha, False

        def coletar(self):
            self.rodou = True
            if self.falha:
                raise RuntimeError("fora")

    go, mt = Modulo("GO"), Modulo("MT", falha=True)
    feitos = []
    monkeypatch.setattr(est, "modulos_uf", lambda: {"GO": go, "MT": mt})
    monkeypatch.setattr(est, "coletar_assembleia", lambda uf, host: feitos.append(uf))
    monkeypatch.setattr("sys.argv", ["x", "go", "mt", "pb"])
    est.main()
    assert go.rodou and mt.rodou and feitos == ["PB"]

    go.rodou = mt.rodou = False
    monkeypatch.setattr("sys.argv", ["x", "go"])
    est.main()
    assert go.rodou and not mt.rodou


# ================================================================ Prefeituras (SAPL)

def test_autores_prefeitura_reconhece_executivo(sapl):
    sapl(**{"base/autor": [{"id": 1, "nome": "Prefeito Fulano", "cargo": ""}, {"id": 2, "nome": "Poder Executivo", "cargo": None},
                           {"id": 3, "nome": "Vereador X", "cargo": "Vereador"}]})
    assert pref.autores_prefeitura("h") == {1, 2}


def test_autores_prefeitura_ausente_levanta(sapl):
    sapl(**{"base/autor": [{"id": 3, "nome": "Vereador X", "cargo": "Vereador"}]})
    with pytest.raises(RuntimeError, match="prefeito"):
        pref.autores_prefeitura("h")


def test_coletar_prefeitura_filtra_tipos_e_autoria(sapl, monkeypatch):
    ano = dt.date.today().year
    monkeypatch.setattr(pref, "ANO_INICIAL", ano)
    mats = [{"id": 1, "tipo": 1, "ano": ano, "numero": 1, "autores": [1], "em_tramitacao": True},
            {"id": 2, "tipo": 1, "ano": ano, "numero": 2, "autores": [3]},               # de vereador
            {"id": 3, "tipo": 2, "ano": ano, "numero": 3, "autores": [1]}]               # tipo "Projeto de Lei do Legislativo": excluído
    s = sapl(**{"base/autor": [{"id": 1, "nome": "Prefeitura", "cargo": ""}],
                "materia/tipomaterialegislativa": [{"id": 1, "sigla": "PL", "descricao": "Projeto de Lei"},
                                                   {"id": 2, "sigla": "PLL", "descricao": "Projeto de Lei do Legislativo"},
                                                   {"id": 3, "sigla": "REQ", "descricao": "Requerimento"}],
                "materia/materialegislativa": mats})
    pref.coletar("PB", "h")
    salvo = json.loads((pref.DADOS / "PB" / f"prefeitura_{ano}.json").read_text(encoding="utf-8"))
    assert list(salvo["materias"]) == ["1"] and salvo["host"] == "h"
    assert salvo["materias"]["1"]["tipo"] == "PL"
    assert {p["tipo"] for c, p in s.chamadas if c == "materia/materialegislativa"} == {1}


def test_main_prefeituras_isola_erros(monkeypatch):
    feitos = []

    def fake(uf, host):
        if uf == "RN":
            raise RuntimeError("fora")
        feitos.append(uf)

    monkeypatch.setattr(pref, "coletar", fake)
    monkeypatch.setattr("sys.argv", ["x", "RN", "PB"])
    pref.main()
    assert feitos == ["PB"]
