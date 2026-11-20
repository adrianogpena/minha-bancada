import datetime as dt
import json

import coletar
import gerar_proposicoes
from conftest import RAIZ
from gerar import TIPOS_PROJETO, destino_projeto

HOJE = dt.date(2026, 11, 20)


def amostra(nome):
    return json.loads((RAIZ / "tests" / "fixtures" / "contratos" / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


def registro():
    return coletar.processo_senado(amostra("senado_processo_detalhe"), amostra("senado_relatoria_materia"), amostra("senado_emendas"))


def test_processo_senado_com_a_amostra_real():
    r = registro()
    assert r["apelido"] == "Ajuste fiscal" and r["tramitando"] is False
    assert r["texto"] == "38df22dd-1022-46cf-ac9d-d24f038d1d0d"
    assert r["autores"] == [["581", "Jaques Wagner", "SENADOR", "PT", "BA"]]
    assert r["outrasCasas"] == [["CD", "PLP", 299, 2026, True]]
    assert r["deliberacao"] == {"data": "2026-11-18", "tipo": "Aprovada pelo Plenário", "destino": "À Câmara dos Deputados"}
    assert r["despachos"] == [["2026-11-11", "Ao Plenário", ["PLEN"], False]]
    assert "norma" not in r
    assert r["relatorias"][0][:4] == ["4994", "Eduardo Braga", "MDB", "AM"] and r["relatorias"][0][7:9] == ["2026-11-11", "2026-11-18"]
    assert [e[0] for e in r["emendas"]] == ["1", "2"] and r["emendas"][0][6] == "531a5911-8467-42a5-9fd7-71e8c13c5edf"
    assert all(len(i) == 3 and len(i[0]) == 16 for i in r["informes"])
    assert all(d[1] not in coletar.DOCS_FORA and "/" not in d[4] for d in r["documentos"])
    assert r["situacoes"][0][2] == "AGDESP"
    assert "LEI KANDIR" in r["indexacao"] and "ALTERAÇÃO" not in r["indexacao"]


def test_processo_senado_norma_gerada_e_documento_de_outro_site():
    d = {**amostra("senado_processo_detalhe"), "normaGerada": {"codigo": 43749703, "descricao": "Decreto Legislativo nº 386 de 03/09/2026",
                                                                "dataAssinatura": "2026-09-03", "veiculoPublicacao": "DOU"}}
    d["documento"] = {**d["documento"], "url": "https://outro.exemplo/x.pdf"}
    r = coletar.processo_senado(d, [], [])
    assert r["norma"] == {"codigo": 43749703, "descricao": "Decreto Legislativo nº 386 de 03/09/2026", "data": "2026-09-03", "publicacao": "DOU"}
    assert r["texto"] == "https://outro.exemplo/x.pdf" and "relatorias" not in r and "emendas" not in r


def test_indexacao_senado():
    assert coletar.indexacao_senado(" ALTERAÇÃO ,  LEI KANDIR ,  DISTRITO FEDERAL (DF) . ALTERAÇÃO ,  LEI KANDIR ,  META FISCAL .") == [
        "LEI KANDIR", "DISTRITO FEDERAL (DF)", "META FISCAL"]
    assert coletar.indexacao_senado(None) == []


def test_orientacoes_senado_vale_a_ultima_orientacao():
    o = coletar.orientacoes_senado(amostra("senado_orientacoes"))
    assert o[4431]["PSDB"] == "Sim" and o[4431]["PSD"] == "Não" and o[4432]["Governo"] == "Sim"
    duas = {"votacoes": [{"sequencialVotacao": 1, "orientacoesLideranca": [
        {"partido": "PT", "voto": "SIM", "dataHora": "2026-01-01T10:00:00"}, {"partido": "PT", "voto": "LIBERADO", "dataHora": "2026-01-01T09:00:00"}]}]}
    assert coletar.orientacoes_senado(duas) == {1: {"PT": "Sim"}}
    assert coletar.orientacoes_senado(None) == {}


def _autorias(tmp_path, atualizado):
    coletar.salvar(tmp_path / "senado_autorias.json", {"581": [
        {"id": "176328", "processo": 9127383, "tipo": "PLP", "numero": "299", "ano": 2026, "atualizadoEm": atualizado},
        {"id": "9", "processo": 1, "tipo": "REQ", "numero": "1", "ano": 2026}]})


def test_coletar_processos_senado_incremental_e_id_da_camara(tmp_path, monkeypatch):
    monkeypatch.setattr(coletar, "DADOS", tmp_path)
    senado, camara = [], []

    def get_senado(caminho, **p):
        senado.append(caminho)
        return {"/processo/9127383": amostra("senado_processo_detalhe"), "/processo/relatoria": amostra("senado_relatoria_materia"),
                "/processo/emenda": amostra("senado_emendas")}[caminho]

    monkeypatch.setattr(coletar, "get_senado", get_senado)
    monkeypatch.setattr(coletar, "get", lambda caminho, **p: camara.append(p) or {"dados": [{"id": 2655570}]})
    _autorias(tmp_path, "2026-11-19T18:15:33.79")
    coletar.coletar_processos_senado(HOJE)
    r = coletar.ler(tmp_path / "senado_processos" / "2026.json", {})
    assert list(r) == ["176328"]   # o requerimento não é projeto
    assert r["176328"]["camara"] == "2655570" and r["176328"]["camaraNumero"] == "PLP 299/2026" and r["176328"]["processo"] == 9127383
    assert len(senado) == 3 and camara == [{"siglaTipo": "PLP", "numero": 299, "ano": 2026}]
    assert coletar.ids_camara_do_senado(tmp_path) == {"2655570"}

    coletar.coletar_processos_senado(HOJE)   # mesma marca de alteração: nada a ler
    assert len(senado) == 3

    _autorias(tmp_path, "2026-11-20T08:00:00")   # mudou: relê, e o id da Câmara já achado não é procurado de novo
    coletar.coletar_processos_senado(HOJE)
    assert len(senado) == 6 and len(camara) == 1
    assert coletar.ler(tmp_path / "senado_processos" / "2026.json", {})["176328"]["atualizadoEm"] == "2026-11-20T08:00:00"


def test_coletar_orientacoes_senado_grava_e_deixa_dia_recente_sem_orientacao_para_depois(tmp_path, monkeypatch):
    monkeypatch.setattr(coletar, "DADOS", tmp_path)
    coletar.salvar(tmp_path / "senado_votacoes" / "2026.json", {
        "7117": {"id": "7117", "data": "2026-11-18", "sessao": {"votacao": 4431}, "votos": []},
        "7200": {"id": "7200", "data": "2026-11-19", "sessao": {"votacao": 9999}, "votos": []},
        "7000": {"id": "7000", "data": "2026-10-01", "sessao": {"votacao": 1}, "votos": []},
        "6000": {"id": "6000", "data": "2026-09-01", "sessao": {"votacao": 2}, "votos": [], "orientacoes": {}}})
    dias = []
    monkeypatch.setattr(coletar, "get_senado", lambda caminho, **p: dias.append(caminho[-8:]) or amostra("senado_orientacoes"))
    coletar.coletar_orientacoes_senado(HOJE)
    assert sorted(dias) == ["20261001", "20261118", "20261119"]   # quem já tem o campo não é consultado
    v = coletar.ler(tmp_path / "senado_votacoes" / "2026.json", {})
    assert v["7117"]["orientacoes"]["PSDB"] == "Sim"
    assert "orientacoes" not in v["7200"]          # dia recente sem orientação: tenta de novo depois
    assert v["7000"]["orientacoes"] == {}          # dia antigo sem orientação: marcado como consultado


def test_gerar_ficha_do_senado_com_detalhe_tramitacao_e_ligacao_com_a_camara(tmp_path):
    proc = {**registro(), "camara": "2655570", "camaraNumero": "PLP 299/2026", "processo": 9127383}
    proc["autores"] = proc["autores"] + [["123", "Ana Deputada", "DEPUTADO", "PL", "SP"]]
    sens = [{"id": "581", "nome": "Jaques Wagner", "partido": "PT", "uf": "BA"}, {"id": "4994", "nome": "Eduardo Braga", "partido": "MDB", "uf": "AM"}]
    aut_sen = {"581": [{"id": "176328", "tipo": "PLP", "numero": "299", "ano": 2026, "ementa": "Altera a Lei Complementar nº 200, de 30 de agosto de 2023, para x.",
                        "principal": True, "situacao": "REMETIDA À CÂMARA DOS DEPUTADOS", "dataSituacao": "2026-11-19", "dataApresentacao": "2026-11-11"}]}
    detalhes = {"2655570": {"tipo": "PLP", "numero": 299, "ano": 2026, "ementa": "Altera", "situacao": "Aguardando Despacho"}}
    autorias = {"2655570": {"idPrincipal": None, "autores": [[None, "Senado Federal", "Órgão do Poder Legislativo"]]}}
    gerar_proposicoes.gerar(tmp_path, {}, detalhes, autorias, {}, {}, sens, aut_sen, [], TIPOS_PROJETO, destino_projeto, {},
                            processos_senado={"176328": proc})
    lido = lambda n: json.loads((tmp_path / n).read_text(encoding="utf-8"))
    f = lido("proposicao/s-2026.json")["176328"]
    assert f["au"] == [{"id": "581", "p": 1}, {"nome": "Ana Deputada", "pt": "PL", "uf": "SP", "tp": "DEPUTADO", "id": "sem-nome"}]
    assert f["ds"] == "2026-11-19" and f["rl"] == "4994" and f["apl"] == "Ajuste fiscal"
    assert f["tx"] == gerar_proposicoes.DOC_SENADO + "38df22dd-1022-46cf-ac9d-d24f038d1d0d"
    assert f["cd"] == "2655570" and f["cn"] == "PLP 299/2026"
    assert f["dl"] == {"d": "2026-11-18", "t": "Aprovada pelo Plenário", "p": "À Câmara dos Deputados"}
    assert "Tributos: Administração Tributária" in f["tm"] and "LEI KANDIR" in f["pc"] and f["ls"]
    t = lido("tramitacao_senado/176328.json")
    assert t["processo"] == 9127383 and t["relatorias"] and t["emendas"] and t["informes"]
    indice = {i["k"]: i for i in lido("proposicoes.json")}
    assert indice["s-176328"]["l"] == "Ajuste fiscal"
    c = lido("proposicao/c-2026.json")["2655570"]
    assert c["sf"] == "176328" and c["au"] == [{"nome": "Senado Federal"}]


def test_gerar_senado_sem_detalhe_mantem_os_senadores_das_autorias(tmp_path):
    sens = [{"id": "7", "nome": "Bia", "partido": "PL", "uf": "RJ"}]
    aut_sen = {"7": [{"id": "88", "tipo": "PL", "numero": "10", "ano": 2024, "ementa": "Algo", "principal": True, "situacao": "Aprovada", "dataSituacao": "2025-01-02"}]}
    gerar_proposicoes.gerar(tmp_path, {}, {}, {}, {}, {}, sens, aut_sen, [], TIPOS_PROJETO, destino_projeto, {})
    f = json.loads((tmp_path / "proposicao/s-2024.json").read_text(encoding="utf-8"))["88"]
    assert f == {"au": [{"id": "7", "p": 1}], "ds": "2025-01-02"}
    assert not (tmp_path / "tramitacao_senado").exists()
