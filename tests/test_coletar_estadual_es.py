import json
import re
from datetime import date

import pytest

import coletar_estadual_es as es
import estaduais_comum as comum
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"


def amostra(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


def linhas_do_contrato():
    return es.linhas_da_assembleia(amostra("estadual_es_despesas")["csv"].split("\n"))


def deputados_do_contrato(filtro):
    nomes = sorted({linha["Favorecido"] for linha in linhas_do_contrato() if filtro(linha)})
    return [{"id": str(i), "nome": n.title(), "nomeCivil": n} for i, n in enumerate(nomes, 1)]


def test_arquivos_por_ano_do_contrato():
    achados = es.arquivos_por_ano(amostra("estadual_es_ckan"))
    assert achados and all(2004 <= a <= 2100 for a in achados)


def test_arquivos_por_ano_ignora_semestres_e_outros():
    pacote = {"result": {"resources": [{"name": "Despesas-2024.csv", "url": "https://x/24.csv"},
                                       {"name": "Despesas-2024_1Semestre.csv", "url": "https://x/24s.csv"},
                                       {"name": "Despesas-2013.csv", "url": "https://x/13a.csv"}, {"name": "Despesas-2013.csv", "url": "https://x/13b.csv"},
                                       {"name": "RestosAPagar-2024.csv", "url": "https://x/rap.csv"}, {"name": "Dicionario de Dados", "url": "https://x/d.pdf"}]}}
    assert {a: r["url"] for a, r in es.arquivos_por_ano(pacote).items()} == {2024: "https://x/24.csv", 2013: "https://x/13a.csv"}


def test_linhas_da_assembleia_filtra_unidade_gestora():
    linhas = ["﻿UnidadeGestora;Favorecido;HistoricoDocumento",
              "ASSEMBLEIA LEGISLATIVA DO ESTADO DO ESPÍRITO SANTO;A;x".encode(),
              "SECRETARIA DA SAUDE;B;PAGO A ASSEMBLEIA LEGISLATIVA",
              "ASSEMBLEIA LEGISLATIVA;C"]
    assert [linha["Favorecido"] for linha in es.linhas_da_assembleia(linhas)] == ["A"]


def test_referencia_e_periodo():
    assert es.referencia("REFERENTE À COTA PARLAMENTAR DO MÊS DE MARÇO", "2026-04-09") == "2026-03"
    assert es.referencia("COTA PARLAMENTAR DO MÊS DE DEZEMBRO", "2026-01-15") == "2025-12"
    assert es.referencia("sem mês", "2026-01-15") is None
    assert es.periodo("REFERENTE AO PERÍODO DE 02/07/2026 a 03/07/2026, PARA") == ("2026-07-02", "2026-07-03")
    assert es.periodo("") == (None, None)


def test_itens_cota_so_pagamentos_de_deputados_do_contrato():
    deps = deputados_do_contrato(es.e_cota)
    itens = es.itens_cota(linhas_do_contrato(), deps)
    assert itens and {i["idDeputado"] for i in itens} <= {d["id"] for d in deps}
    assert all(i["valor"] and i["mes"] and i["data"] and i["fonte"] == es.PAGINA for i in itens)
    assert all(i["documento"][4:6] == "OB" for i in itens)
    assert es.itens_cota(linhas_do_contrato(), [{"id": "1", "nome": "Ninguém", "nomeCivil": "Ninguém"}]) == []


def test_itens_cota_ignora_empenho_e_liquidacao():
    base = {"UnidadeGestora": "ASSEMBLEIA LEGISLATIVA", "SubelementoDespesa": "Reembolso de Despesas – Cotas Parlamentares", "Favorecido": "FULANO DE TAL",
            "Data": "12/02/2026 00:00:00", "HistoricoDocumento": "COTA PARLAMENTAR DO MÊS DE JANEIRO"}
    linhas = [{**base, "Documento": "2026NE1", "ValorPago": "0,0000"}, {**base, "Documento": "2026NL1", "ValorPago": "0,0000"},
              {**base, "Documento": "2026OB1", "ValorPago": "1524,0000"}, {**base, "Documento": "2026OB2", "ValorPago": "-200,0000"}]
    itens = es.itens_cota(linhas, [{"id": "7", "nome": "Fulano", "nomeCivil": "Fulano de Tal"}])
    assert [(i["documento"], i["valor"], i["mes"], i["referencia"]) for i in itens] == [("2026OB1", 1524.0, 2, "2026-01"), ("2026OB2", -200.0, 2, "2026-01")]


def test_itens_diarias_do_contrato():
    deps = deputados_do_contrato(es.e_diaria)
    itens = es.itens_diarias(linhas_do_contrato(), deps)
    assert itens and all(i["valor"] and i["data"] and i["motivo"] for i in itens)


def test_conferir_contrato_despesas():
    assert es._conferir_despesas(amostra("estadual_es_despesas")) == ([], [])
    falhas, _ = es._conferir_despesas({"csv": "Data;UnidadeGestora\n01/01/2026;ASSEMBLEIA LEGISLATIVA"})
    assert any("ValorPago" in f for f in falhas)


def test_ano_fechado(tmp_path):
    hoje = date(2026, 10, 23)
    assert not es.ano_fechado(2024, hoje, tmp_path)
    (tmp_path / "verbas_2024.json").write_text("{}", encoding="utf-8")
    assert es.ano_fechado(2024, hoje, tmp_path)
    (tmp_path / "verbas_2025.json").write_text(json.dumps({"coletadoEm": "2026-02-20"}), encoding="utf-8")
    assert not es.ano_fechado(2025, hoje, tmp_path)
    assert not es.ano_fechado(2025, date(2026, 2, 21), tmp_path)
    (tmp_path / "verbas_2025.json").write_text(json.dumps({"coletadoEm": "2026-03-02"}), encoding="utf-8")
    assert es.ano_fechado(2025, hoje, tmp_path)
    assert not es.ano_fechado(2026, hoje, tmp_path)




def csv_bytes():
    return ("﻿" + amostra("estadual_es_despesas")["csv"].replace("\n", "\r\n") + "\r\n").encode("utf-8")


class Resp:
    def __init__(self, dados=None, conteudo=b"", status=200, falhar_em=None, total=None, inicio=0):
        self._dados, self.conteudo, self.status_code, self.falhar_em = dados, conteudo, status, falhar_em
        self.headers = {"Content-Range": f"bytes {inicio}-{total - 1}/{total}"} if total else {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    def json(self):
        return self._dados

    def iter_content(self, tamanho):
        for i in range(0, len(self.conteudo), 1000):
            if self.falhar_em is not None and i >= self.falhar_em:
                raise comum.PrazoEsgotado("prazo de coleta esgotado")
            yield self.conteudo[i:i + 1000]


class Sessao:
    def __init__(self, pacote, falhar_em=None, conteudo=None):
        self.pacote, self.falhar_em, self.pedidos = pacote, falhar_em, []
        self.conteudo = conteudo if conteudo is not None else csv_bytes()

    def get(self, url, timeout=None, stream=False, headers=None):
        if "package_show" in url:
            return Resp(dados=self.pacote)
        inicio, fim = re.fullmatch(r"bytes=(\d+)-(\d*)", headers["Range"]).groups()
        inicio = int(inicio)
        self.pedidos.append((url, inicio))
        corte = int(fim) + 1 if fim else None
        return Resp(conteudo=self.conteudo[inicio:corte], status=206, total=len(self.conteudo), inicio=inicio,
                    falhar_em=None if fim else self.falhar_em)


def preparar(tmp_path, monkeypatch, sessao):
    nome = next(linha["Favorecido"] for linha in linhas_do_contrato() if es.e_cota(linha))
    tse = [{"cargo": "DEPUTADO ESTADUAL", "situacao": "eleito", "sequencial": "80", "urna": "Fulano", "nome": nome, "partido": "PDT", "email": None},
           {"cargo": "DEPUTADO FEDERAL", "situacao": "eleito", "sequencial": "9", "urna": "X", "nome": "X"}]
    arquivo = tmp_path / "ES.json"
    arquivo.write_text(json.dumps(tse), encoding="utf-8")
    monkeypatch.setattr(es, "TSE_ARQUIVO", arquivo)
    monkeypatch.setattr(comum, "DADOS", tmp_path / "estaduais")
    monkeypatch.setattr(comum, "sessao", lambda *a: sessao)
    pasta = tmp_path / "estaduais" / "ES"
    pasta.mkdir(parents=True)
    return pasta


PACOTE = {"result": {"resources": [{"name": "Despesas-2026.csv", "url": "https://dados.es.gov.br/26.csv", "last_modified": "2026-10-22T10:56:36"},
                                   {"name": "Despesas-2023.csv", "url": "https://dados.es.gov.br/23.csv", "last_modified": "2026-10-17T23:10:32"},
                                   {"name": "Despesas-2020.csv", "url": "https://dados.es.gov.br/20.csv", "last_modified": "2026-10-17T19:25:27"}]}}


def test_coletar_grava_e_pula_anos_fechados_e_sem_mudanca(tmp_path, monkeypatch):
    sessao = Sessao(PACOTE)
    pasta = preparar(tmp_path, monkeypatch, sessao)
    (pasta / "verbas_2023.json").write_text(json.dumps({"coletadoEm": "2024-01-01", "itens": []}), encoding="utf-8")
    es.coletar()
    assert {u for u, _ in sessao.pedidos} == {"https://dados.es.gov.br/26.csv"}
    deps = json.loads((pasta / "deputados.json").read_text(encoding="utf-8"))
    assert [d["id"] for d in deps["deputados"]] == ["80"] and deps["host"] is None
    verbas = json.loads((pasta / "verbas_2026.json").read_text(encoding="utf-8"))
    assert verbas["itens"] and all(i["idDeputado"] == "80" for i in verbas["itens"])
    assert verbas["recursoModificadoEm"] == "2026-10-22T10:56:36"
    assert (pasta / "diarias_2026.json").exists() and not (pasta / "parcial_2026.json").exists()
    sessao.pedidos.clear()
    es.coletar()
    assert sessao.pedidos == []


def test_coletar_prazo_guarda_parcial_e_continua_com_range(tmp_path, monkeypatch):
    completo = Sessao(PACOTE)
    pasta = preparar(tmp_path, monkeypatch, completo)
    (pasta / "verbas_2023.json").write_text("{}", encoding="utf-8")
    es.coletar()
    esperado = json.loads((pasta / "verbas_2026.json").read_text(encoding="utf-8"))["itens"]
    (pasta / "verbas_2026.json").unlink()

    cortada = Sessao(PACOTE, falhar_em=len(csv_bytes()) // 2)
    monkeypatch.setattr(comum, "sessao", lambda *a: cortada)
    es.coletar()
    parcial = json.loads((pasta / "parcial_2026.json").read_text(encoding="utf-8"))
    offset = parcial["fatias"][0]["offset"]
    assert 0 < offset < len(csv_bytes()) and not (pasta / "verbas_2026.json").exists()
    assert csv_bytes()[offset - 1:offset] == b"\n"

    retomada = Sessao(PACOTE)
    monkeypatch.setattr(comum, "sessao", lambda *a: retomada)
    es.coletar()
    assert ("https://dados.es.gov.br/26.csv", offset) in retomada.pedidos
    assert json.loads((pasta / "verbas_2026.json").read_text(encoding="utf-8"))["itens"] == esperado
    assert not (pasta / "parcial_2026.json").exists()


def coletar_de_novo(tmp_path, monkeypatch, conteudo=None, modificado="2026-10-22T10:56:36"):
    pacote = {"result": {"resources": [{"name": "Despesas-2026.csv", "url": "https://dados.es.gov.br/26.csv", "last_modified": modificado}]}}
    sessao = Sessao(pacote, conteudo=conteudo)
    pasta = preparar(tmp_path, monkeypatch, sessao)
    return sessao, pasta


def itens_2026(pasta):
    return json.loads((pasta / "verbas_2026.json").read_text(encoding="utf-8"))


def test_fatias_paralelas_dao_o_mesmo_resultado(tmp_path, monkeypatch):
    sessao, pasta = coletar_de_novo(tmp_path, monkeypatch)
    es.coletar()
    esperado = itens_2026(pasta)["itens"]
    (pasta / "verbas_2026.json").unlink()
    monkeypatch.setattr(es, "FATIA_MIN", 100)
    sessao.pedidos.clear()
    es.coletar()
    assert len(sessao.pedidos) == 1 + es.CONEXOES
    assert itens_2026(pasta)["itens"] == esperado


def linha_nova():
    bruta = next(b for b in csv_bytes().split(b"\n") if es.e_cota(es.linha_da_assembleia(b.rstrip(b"\r"), cab()) or {}))
    doc = es.linha_da_assembleia(bruta.rstrip(b"\r"), cab())["Documento"].encode()
    return bruta.replace(doc, b"2026OB999999") + b"\n"


def cab():
    return es.cabecalho_csv(csv_bytes().split(b"\n")[0].rstrip(b"\r"))


def test_mudanca_na_fonte_le_so_o_trecho_novo(tmp_path, monkeypatch):
    sessao, pasta = coletar_de_novo(tmp_path, monkeypatch)
    es.coletar()
    antes = itens_2026(pasta)
    tamanho = len(csv_bytes())
    assert antes["tamanho"] == tamanho
    sessao.conteudo = csv_bytes() + linha_nova()
    sessao.pacote["result"]["resources"][0]["last_modified"] = "2026-10-23T10:00:00"
    sessao.pedidos.clear()
    es.coletar()
    assert ("https://dados.es.gov.br/26.csv", tamanho) in sessao.pedidos
    assert all(o in (0, tamanho) for _, o in sessao.pedidos)
    depois = itens_2026(pasta)
    assert len(depois["itens"]) == len(antes["itens"]) + 1 and depois["completaEm"] == antes["completaEm"]
    assert "2026OB999999" in {i["documento"] for i in depois["itens"]}


def test_completa_velha_ou_arquivo_menor_le_tudo(tmp_path, monkeypatch):
    sessao, pasta = coletar_de_novo(tmp_path, monkeypatch)
    es.coletar()
    antes = itens_2026(pasta)
    antes["completaEm"] = "2026-01-01"
    (pasta / "verbas_2026.json").write_text(json.dumps(antes), encoding="utf-8")
    sessao.pacote["result"]["resources"][0]["last_modified"] = "2026-10-23T10:00:00"
    sessao.pedidos.clear()
    es.coletar()
    assert len(itens_2026(pasta)["itens"]) == len(antes["itens"]) and itens_2026(pasta)["completaEm"] == date.today().isoformat()
    assert len(sessao.pedidos) > 1 and min(o for _, o in sessao.pedidos[1:]) > 0
    assert sessao.pedidos[-1][1] < antes["tamanho"]


def fatia(inicio, fim, offset, alinhada):
    return {"inicio": inicio, "fim": fim, "offset": offset, "alinhada": alinhada, "linhas": []}


def test_linha_da_assembleia_ignora_linha_curta_e_outra_unidade():
    cabecalho = ["UnidadeGestora", "Favorecido", "Documento"]
    assert es.linha_da_assembleia(b"ASSEMBLEIA LEGISLATIVA;A", cabecalho) is None
    assert es.linha_da_assembleia(b"SECRETARIA;A;2026OB1", cabecalho) is None
    assert es.linha_da_assembleia(b"SECRETARIA;PAGO A ASSEMBLEIA LEGISLATIVA;2026OB1", cabecalho) is None
    assert es.linha_da_assembleia(b"ASSEMBLEIA LEGISLATIVA;A;2026OB1", cabecalho)["Favorecido"] == "A"


def test_e_diaria_recusa_outro_elemento_e_sem_campo():
    assert es.e_diaria({"ElementoDespesa": "DIÁRIAS - CIVIL"})
    assert not es.e_diaria({"ElementoDespesa": "MATERIAL DE CONSUMO"})
    assert not es.e_diaria({})


def test_itens_diarias_descarta_favorecido_nao_ligado():
    assert es.itens_diarias(linhas_do_contrato(), [{"id": "1", "nome": "Ninguém", "nomeCivil": "Ninguém"}]) == []


def test_cabecalho_e_tamanho_le_cabecalho_e_content_range():
    sessao = Sessao(PACOTE)
    cabecalho, fim, total = es.cabecalho_e_tamanho(sessao, "https://x/26.csv")
    assert cabecalho == cab() and csv_bytes()[fim - 1:fim] == b"\n" and total == len(csv_bytes())
    assert sessao.pedidos == [("https://x/26.csv", 0)]


def test_cabecalho_e_tamanho_recusa_fonte_sem_range():
    class SemRange:
        def get(self, url, timeout=None, stream=False, headers=None):
            return Resp(conteudo=csv_bytes(), status=200)

    with pytest.raises(RuntimeError, match="Range"):
        es.cabecalho_e_tamanho(SemRange(), "https://x/26.csv")


def test_planejar_fatias_arquivo_pequeno_fica_numa_fatia_so():
    fatias = es.planejar_fatias(100, 200)
    assert [(f["inicio"], f["fim"], f["offset"], f["alinhada"]) for f in fatias] == [(100, 200, 100, True)]


def test_planejar_fatias_divide_em_conexoes_contiguas():
    total = 3 * es.FATIA_MIN
    fatias = es.planejar_fatias(0, total, 3)
    assert [f["alinhada"] for f in fatias] == [True, False, False]
    assert fatias[0]["inicio"] == 0 and fatias[-1]["fim"] == total
    assert all(a["fim"] == b["inicio"] for a, b in zip(fatias, fatias[1:]))


def test_ler_fatia_recusa_resposta_que_ignora_range():
    class SemRange:
        def get(self, url, timeout=None, stream=False, headers=None):
            return Resp(conteudo=csv_bytes(), status=200)

    with pytest.raises(RuntimeError, match="ignorou o Range"):
        es.ler_fatia(SemRange(), "https://x/26.csv", fatia(0, 10, 0, True), cab())


def test_ler_fatia_leitura_incompleta_levanta_e_mantem_o_que_leu():
    dados = csv_bytes()
    f = fatia(0, len(dados) + 50, 0, True)
    with pytest.raises(RuntimeError, match="incompleta"):
        es.ler_fatia(Sessao(PACOTE), "https://x/26.csv", f, cab())
    assert f["linhas"] and f["offset"] == len(dados)


def test_ler_fatia_retomada_apos_prazo_completa_sem_duplicar():
    dados = csv_bytes()
    fim_cab = dados.index(b"\n") + 1
    inteira = fatia(fim_cab, len(dados), fim_cab, True)
    es.ler_fatia(Sessao(PACOTE), "https://x/26.csv", inteira, cab())

    f = fatia(fim_cab, len(dados), fim_cab, True)
    with pytest.raises(comum.PrazoEsgotado):
        es.ler_fatia(Sessao(PACOTE, falhar_em=len(dados) // 2), "https://x/26.csv", f, cab())
    assert fim_cab < f["offset"] < len(dados)
    es.ler_fatia(Sessao(PACOTE), "https://x/26.csv", f, cab())
    assert f["linhas"] == inteira["linhas"] and f["offset"] == len(dados)


def test_ler_fatia_linha_que_cruza_a_fronteira_fica_na_fatia_anterior():
    dados = csv_bytes()
    fim_cab = dados.index(b"\n") + 1
    inteira = fatia(fim_cab, len(dados), fim_cab, True)
    es.ler_fatia(Sessao(PACOTE), "https://x/26.csv", inteira, cab())
    inicio_util, pos = None, 0
    for bruta in dados.split(b"\n"):
        if pos >= fim_cab and es.e_cota(es.linha_da_assembleia(bruta.rstrip(b"\r"), cab()) or {}):
            inicio_util = pos
            break
        pos += len(bruta) + 1
    fronteira = inicio_util + 20
    primeira = fatia(fim_cab, fronteira, fim_cab, True)
    segunda = fatia(fronteira, len(dados), fronteira, False)
    sessao = Sessao(PACOTE)
    es.ler_fatia(sessao, "https://x/26.csv", primeira, cab())
    es.ler_fatia(sessao, "https://x/26.csv", segunda, cab())
    assert primeira["linhas"] + segunda["linhas"] == inteira["linhas"]
    assert segunda["alinhada"] is True


def test_ler_fatias_sem_pendentes_nao_le_nada(monkeypatch):
    monkeypatch.setattr(es, "ler_fatia", lambda *a: pytest.fail("fatia lida sem pendência"))
    parcial = {"cabecalho": [], "fatias": [fatia(0, 10, 10, True)]}
    es.ler_fatias(None, "https://x", parcial)


def test_ler_fatias_termina_todas_e_prazo_tem_prioridade(monkeypatch):
    lidas = []

    def falso(s, url, f, cabecalho):
        lidas.append(f["inicio"])
        if f["inicio"] == 0:
            raise ValueError("falha")
        if f["inicio"] == 1:
            raise comum.PrazoEsgotado("prazo")

    monkeypatch.setattr(es, "ler_fatia", falso)
    fatias = [fatia(i, 100, i, False) for i in (0, 1, 2)]
    with pytest.raises(comum.PrazoEsgotado):
        es.ler_fatias(None, "https://x", {"cabecalho": [], "fatias": fatias})
    assert sorted(lidas) == [0, 1, 2]
    with pytest.raises(ValueError):
        es.ler_fatias(None, "https://x", {"cabecalho": [], "fatias": fatias[:1]})


def test_parcial_novo_completa_quando_nao_ha_arquivo_anterior():
    hoje = date(2026, 11, 3)
    p = es.parcial_novo(Sessao(PACOTE), "https://x/26.csv", "m1", {}, hoje)
    assert p["incremental"] is False and p["completaEm"] == "2026-11-03" and p["tamanho"] == len(csv_bytes())
    assert p["inicio"] == csv_bytes().index(b"\n") + 1 and p["recursoModificadoEm"] == "m1" and p["cabecalho"] == cab()


def test_parcial_novo_incremental_le_do_tamanho_anterior():
    hoje = date(2026, 11, 3)
    antigo = {"tamanho": len(csv_bytes()) - 100, "completaEm": "2026-10-30"}
    p = es.parcial_novo(Sessao(PACOTE), "https://x/26.csv", "m1", antigo, hoje)
    assert p["incremental"] is True and p["inicio"] == len(csv_bytes()) - 100 and p["completaEm"] == "2026-10-30"


def test_parcial_novo_le_tudo_se_arquivo_encolheu_ou_completa_velha():
    hoje = date(2026, 11, 3)
    encolheu = es.parcial_novo(Sessao(PACOTE), "https://x/26.csv", "m1", {"tamanho": len(csv_bytes()) + 1, "completaEm": "2026-11-01"}, hoje)
    velha = es.parcial_novo(Sessao(PACOTE), "https://x/26.csv", "m1", {"tamanho": 100, "completaEm": "2026-10-01"}, hoje)
    for p in (encolheu, velha):
        assert p["incremental"] is False and p["completaEm"] == "2026-11-03" and p["inicio"] == csv_bytes().index(b"\n") + 1


def test_conferir_despesas_sem_cota_diaria_e_linha_ilegivel():
    cabecalho = ";".join(es.CAMPOS)
    linha = "xx;abc;F;D;H;ASSEMBLEIA LEGISLATIVA;OUTRO;OUTRO"
    falhas, _ = es._conferir_despesas({"csv": f"{cabecalho}\n{linha}"})
    assert "nenhuma linha de cota parlamentar da Assembleia no CSV" in falhas
    assert "nenhuma linha de diárias da Assembleia no CSV" in falhas
    assert "linha sem data ou valor pago legível" in falhas


def test_coletar_sem_eleitos_avisa_e_nao_abre_sessao(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(es, "TSE_ARQUIVO", tmp_path / "inexistente.json")
    monkeypatch.setattr(comum, "DADOS", tmp_path / "estaduais")
    monkeypatch.setattr(comum, "sessao", lambda *a: pytest.fail("sessão aberta sem deputados"))
    es.coletar()
    assert "ES: sem eleitos de 2022" in capsys.readouterr().err
    assert not (tmp_path / "estaduais" / "ES" / "deputados.json").exists()


def test_coletar_erro_que_nao_e_prazo_avisa_sem_gravar_o_ano(tmp_path, monkeypatch, capsys):
    pacote = {"result": {"resources": [{"name": "Despesas-2026.csv", "url": "https://dados.es.gov.br/26.csv", "last_modified": "m1"}]}}

    class SemRange:
        def get(self, url, timeout=None, stream=False, headers=None):
            if "package_show" in url:
                return Resp(dados=pacote)
            return Resp(conteudo=csv_bytes(), status=200)

    pasta = preparar(tmp_path, monkeypatch, SemRange())
    es.coletar()
    saida = capsys.readouterr()
    assert "despesas 2026 não lidas por inteiro" in saida.err and "Range" in saida.err
    assert not (pasta / "verbas_2026.json").exists() and not (pasta / "parcial_2026.json").exists()
    assert (pasta / "deputados.json").exists() and "ES: 1 deputados" in saida.out


def test_coletar_incremental_junta_diarias_guardadas(tmp_path, monkeypatch):
    sessao, pasta = coletar_de_novo(tmp_path, monkeypatch)
    es.coletar()
    diarias = json.loads((pasta / "diarias_2026.json").read_text(encoding="utf-8"))
    guardada = {"idDeputado": "80", "data": "2026-01-01", "documento": "2026OB000001", "valor": 1.0}
    diarias["itens"].append(guardada)
    (pasta / "diarias_2026.json").write_text(json.dumps(diarias), encoding="utf-8")
    tamanho = len(csv_bytes())
    sessao.conteudo = csv_bytes() + linha_nova()
    sessao.pacote["result"]["resources"][0]["last_modified"] = "2026-10-23T10:00:00"
    es.coletar()
    depois = json.loads((pasta / "diarias_2026.json").read_text(encoding="utf-8"))
    assert guardada in depois["itens"] and len(depois["itens"]) == len(diarias["itens"])
    assert (pasta / "verbas_2026.json").exists() and json.loads((pasta / "verbas_2026.json").read_text(encoding="utf-8"))["tamanho"] == tamanho + len(linha_nova())
