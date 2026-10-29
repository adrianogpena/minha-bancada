"""Coletor dos ministros de Estado (scripts/coletar_ministros.py) contra amostras reais em tests/fixtures/contratos/."""
import json

import pytest

import coletar_ministros as m
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"


def amostra(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


def test_ler_planalto_amostra_real():
    lista, atualizado = m.ler_planalto(amostra("planalto_ministros")["html"])
    assert len(lista) >= m.MINIMO_PLANALTO
    assert lista[0]["cargo"].startswith("Ministr") and lista[0]["nome"]
    assert {"cargo": "Advocacia-Geral da União", "nome": "Jorge Rodrigo Araújo Messias"} in lista
    assert atualizado and atualizado[4] == "-"


def test_atualizar_planalto_mantem_entrada_e_fecha_saida():
    anterior = {"atuais": [{"cargo": "Ministro da Saúde", "nome": "A", "vistoDesde": "2026-01-01"},
                           {"cargo": "Ministro das Cidades", "nome": "B", "vistoDesde": "2026-01-01"}],
                "anteriores": [{"cargo": "Ministro da Pesca", "nome": "Z", "vistoDesde": "2025-01-01", "vistoAte": "2025-06-01"}]}
    lidos = [{"cargo": "Ministro da Saúde", "nome": "A"}, {"cargo": "Ministro das Cidades", "nome": "C"}]
    r = m.atualizar_planalto(anterior, lidos, "2026-10-29")
    assert r["atuais"] == [{"cargo": "Ministro da Saúde", "nome": "A", "vistoDesde": "2026-01-01"},
                           {"cargo": "Ministro das Cidades", "nome": "C", "vistoDesde": "2026-10-29"}]
    assert r["anteriores"][-1] == {"cargo": "Ministro das Cidades", "nome": "B", "vistoDesde": "2026-01-01", "vistoAte": "2026-10-29"}
    assert len(r["anteriores"]) == 2


def test_atualizar_planalto_primeira_coleta():
    r = m.atualizar_planalto(None, [{"cargo": "Ministro da Saúde", "nome": "A"}], "2026-10-29")
    assert r == {"atuais": [{"cargo": "Ministro da Saúde", "nome": "A", "vistoDesde": "2026-10-29"}], "anteriores": []}


def test_coletar_planalto_recusa_pagina_quebrada(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "PASTA", tmp_path)
    monkeypatch.setattr(m.comum, "get", lambda s, url, **kw: type("R", (), {"text": "<p><strong>Ministro</strong></p><p>A</p>"})())
    with pytest.raises(RuntimeError):
        m.coletar_planalto("2026-10-29")
    assert not (tmp_path / "planalto.json").exists()


def test_filtrar_camara_amostra_real():
    props = amostra("camara_arquivo_proposicoes")["dados"]
    outro = {**props[0], "id": 1, "siglaTipo": "PL", "ementa": "Altera a lei do Ministério"}
    autores = [{"idProposicao": props[0]["id"], "idDeputadoAutor": 2, "nomeAutor": "Segundo", "ordemAssinatura": "2"},
               {"idProposicao": props[0]["id"], "idDeputadoAutor": 1, "nomeAutor": "Primeiro", "ordemAssinatura": "1"}]
    itens = m.filtrar_camara(props + [outro], autores)
    assert set(itens) == {str(props[0]["id"]), str(props[1]["id"])}
    ric = itens[str(props[0]["id"])]
    assert ric["tipo"] == "RIC" and ric["autores"] == [[1, "Primeiro"], [2, "Segundo"]]
    assert ric["dataStatus"][4] == "-" and ric["tramitacao"] and ric["dataApresentacao"]
    assert itens[str(props[1]["id"])]["tipo"] == "REQ"


def test_ler_tramitacao_amostra_real(monkeypatch):
    monkeypatch.setattr(m, "get", lambda c, **p: amostra("camara_tramitacoes_ric"))
    r = m.ler_tramitacao("1")
    assert set(r) == {"prazoFim", "resposta"} and r["prazoFim"][4] == r["resposta"][4] == "-"


def test_ler_tramitacao_remessa_prazo_e_resposta(monkeypatch):
    monkeypatch.setattr(m, "get", lambda c, **p: {"dados": [
        {"dataHora": "2026-02-09T10:00", "descricaoTramitacao": "Apresentação de Proposição", "despacho": "x"},
        {"dataHora": "2026-04-24T10:00", "descricaoTramitacao": "Remessa a Ministério", "despacho": "Ofício 126/2026"},
        {"dataHora": "2026-04-24T10:00", "descricaoTramitacao": "Abertura de Prazo", "despacho": "Prazo para Resposta Externas (de 25/04/2026 a 25/05/2026)"},
        {"dataHora": "2026-05-25T10:00", "descricaoTramitacao": "Recebimento de Resposta", "despacho": "ofício nº 30"}]})
    assert m.ler_tramitacao("1") == {"remessa": "2026-04-24", "prazoFim": "2026-05-25", "resposta": "2026-05-25"}


def test_pendente():
    ric = {"tipo": "RIC", "dataStatus": "2026-05-01"}
    assert m.pendente(ric, None)
    assert not m.pendente(ric, {"lidoEm": "2026-05-01"})
    assert m.pendente(ric, {"lidoEm": "2026-04-01"})
    assert not m.pendente(ric, {"lidoEm": "2026-04-01", "resposta": "2026-04-20"})
    assert not m.pendente({"tipo": "REQ", "dataStatus": "2026-05-01"}, None)


def prop(id_, data, tipo="RIC"):
    return {"id": id_, "siglaTipo": tipo, "numero": id_, "ano": 2026, "ementa": "Requer informações ao Ministro de Estado da Saúde",
            "dataApresentacao": "2026-02-01T10:00", "urlInteiroTeor": None, "ultimoStatus": {"data": data, "descricaoTramitacao": "x"}}


def test_coletar_camara_le_so_tramitacao_pendente(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "PASTA", tmp_path)
    m.comum.salvar(tmp_path / "camara_2026.json", {"itens": {
        "1": {"tipo": "RIC", "lidoEm": "2026-03-01", "remessa": "2026-02-20"},
        "2": {"tipo": "RIC", "lidoEm": "2026-03-01", "resposta": "2026-03-01"},
        "3": {"tipo": "RIC", "lidoEm": "2026-02-01"}}})
    arquivos = {"proposicoes": [prop(1, "2026-03-01T00:00"), prop(2, "2026-04-01T00:00"), prop(3, "2026-04-01T00:00"), prop(4, "2026-04-01T00:00")],
                "proposicoesAutores": []}
    monkeypatch.setattr(m, "baixar_arquivo", lambda nome, ano: arquivos[nome])
    lidos = []
    monkeypatch.setattr(m, "ler_tramitacao", lambda id_: lidos.append(id_) or {"resposta": "2026-04-01"})
    m.coletar_camara(2026, "2026-10-29", float("inf"))
    assert sorted(lidos) == ["3", "4"]
    itens = m.comum.ler(tmp_path / "camara_2026.json")["itens"]
    assert itens["1"]["remessa"] == "2026-02-20" and itens["1"]["lidoEm"] == "2026-03-01"
    assert itens["2"]["resposta"] == "2026-03-01"
    assert itens["3"]["resposta"] == "2026-04-01" and itens["3"]["lidoEm"] == "2026-04-01"


def test_coletar_camara_prazo_esgotado_deixa_para_depois(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "PASTA", tmp_path)
    monkeypatch.setattr(m, "baixar_arquivo", lambda nome, ano: [prop(1, "2026-03-01T00:00")] if nome == "proposicoes" else [])
    monkeypatch.setattr(m, "ler_tramitacao", lambda id_: {"resposta": "2026-04-01"})
    m.coletar_camara(2026, "2026-10-29", 0)
    assert "lidoEm" not in m.comum.ler(tmp_path / "camara_2026.json")["itens"]["1"]


def test_coletar_camara_ano_encerrado(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "PASTA", tmp_path)
    monkeypatch.setattr(m, "ler_tramitacao", lambda id_: {})
    baixados = []
    monkeypatch.setattr(m, "baixar_arquivo", lambda nome, ano: baixados.append(nome) or ([prop(1, "2024-03-01T00:00")] if nome == "proposicoes" else []))
    m.comum.salvar(tmp_path / "camara_2024.json", {"itens": {"1": {"tipo": "RIC"}}})
    m.coletar_camara(2024, "2026-10-29", float("inf"))
    assert baixados
    baixados.clear()
    m.coletar_camara(2024, "2026-10-29", float("inf"))
    assert not baixados


def test_filtrar_senado_amostra_real():
    processos = amostra("senado_requerimentos")
    voto = {**processos[0], "id": 1, "tipoConteudo": "Homenagem de pesar"}
    itens = m.filtrar_senado(processos + [voto])
    assert set(itens) == {str(p["id"]) for p in processos}
    i = next(iter(itens.values()))
    assert i["tipoConteudo"] in m.TIPOS_SENADO and i["autoria"] and i["dataApresentacao"][4] == "-"


def test_afastamentos_senado_amostra_real():
    r = m.afastamentos_senado(amostra("senado_afastados"))
    assert r
    a = next(iter(r.values()))
    assert a["nome"] and a["afastamentos"][0]["inicio"][4] == "-"


def test_afastamentos_senado_exercicio_unico_e_sem_exercicio():
    lista = {"Lista": {"Parlamentares": {"Parlamentar": [
        {"IdentificacaoParlamentar": {"CodigoParlamentar": "1", "NomeParlamentar": "A"},
         "Mandato": {"Exercicios": {"Exercicio": {"DataInicio": "2023-01-01", "DataFim": "2023-02-01",
                                                  "DescricaoCausaAfastamento": "Ocupação de cargo de ministro/secretário"}}}},
        {"IdentificacaoParlamentar": {"CodigoParlamentar": "2", "NomeParlamentar": "B"}, "Mandato": {}}]}}}
    assert m.afastamentos_senado(lista) == {"1": {"nome": "A", "afastamentos": [{"inicio": "2023-01-01", "fim": "2023-02-01", "cargo": None, "uf": None}]}}


def test_licencas_camara_so_fora_de_exercicio_e_ministro(monkeypatch):
    monkeypatch.setattr(m, "get_todos", lambda c, **p: [{"id": 1, "nome": "Atual"}] + ([{"id": 2, "nome": "Min"}, {"id": 3, "nome": "Outro"}] if p else []))
    hist = {2: [{"idLegislatura": m.LEGISLATURA, "dataHora": "2025-03-10T00:00", "situacao": "Licença", "condicaoEleitoral": "Titular",
                 "descricaoStatus": "Saída - Afastamento sem prazo determinado - Ministro de Estado"}],
            3: [{"idLegislatura": m.LEGISLATURA, "dataHora": "2025-03-10T00:00", "situacao": "Fim de Mandato", "descricaoStatus": "Renúncia"}]}
    monkeypatch.setattr(m, "get", lambda c, **p: {"dados": hist[int(c.split("/")[2])]})
    r = m.licencas_camara()
    assert list(r) == ["2"] and r["2"]["historico"][0]["data"] == "2025-03-10"
