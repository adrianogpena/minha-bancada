import json

import pytest
import requests

import coletar_estadual_pr as pr
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"

DEPUTADOS = [
    {"id": "alexandre-curi", "nome": "ALEXANDRE CURI", "nomeCivil": "ALEXANDRE MARANHAO KHURY", "partido": "REP"},
    {"id": "ana-julia", "nome": "ANA JÚLIA", "nomeCivil": None, "partido": "PT"},
    {"id": "doutor-antenor", "nome": "DOUTOR ANTENOR", "nomeCivil": None, "partido": "PT"},
    {"id": "luis-raimundo-corti", "nome": "LUIS CORTI", "nomeCivil": None, "partido": "PSD"},
    {"id": "pedro-paulo-bazana", "nome": "PEDRO PAULO BAZANA", "nomeCivil": None, "partido": "PSD"},
    {"id": "marcia-huculak", "nome": "SECRETÁRIA MÁRCIA", "nomeCivil": None, "partido": "PSD"},
    {"id": "anibelli-neto", "nome": "ANIBELLI NETO", "nomeCivil": None, "partido": "MDB"},
]


def amostra(nome):
    return json.loads((FIX / f"estadual_pr_{nome}.json").read_text(encoding="utf-8"))["amostra"]


def test_parse_deputados_do_contrato():
    achados = pr.parse_deputados(amostra("deputados")["html"])
    assert achados[0]["id"] == "alexandre-curi" and achados[0]["partido"] and achados[0]["foto"].startswith("https://")
    assert achados[0]["fonte"] == "https://www.assembleia.pr.leg.br/deputados/perfil/alexandre-curi"
    assert pr._conferir_deputados(amostra("deputados")) == ([], [])


def test_ligar_variacoes_de_nome():
    nomes = ["DEPUTADO ALEXANDRE CURI", "ANA JÚLIA DO PT ", "DR. ANTENOR", "LUIS RAIMUNDO CORTI", "BAZANA", "MARCIA HUÇULAK",
             "MARIA VICTÓRIA(Art. 98, caput, do RI)", "ANNIBELLI NETO", "Fulano de Tal"]
    ligados = pr.ligar(nomes, DEPUTADOS)
    assert ligados == {"DEPUTADO ALEXANDRE CURI": "alexandre-curi", "ANA JÚLIA DO PT ": "ana-julia", "DR. ANTENOR": "doutor-antenor",
                       "LUIS RAIMUNDO CORTI": "luis-raimundo-corti", "BAZANA": "pedro-paulo-bazana", "MARCIA HUÇULAK": "marcia-huculak",
                       "ANNIBELLI NETO": "anibelli-neto"}


def test_ligar_deixa_ambiguo_de_fora():
    deputados = [{"id": "a", "nome": "MARCIO NUNES", "nomeCivil": None}, {"id": "b", "nome": "MARCIO PACHECO", "nomeCivil": None}]
    assert pr.ligar(["MARCIO"], deputados) == {}


def test_nome_civil_vem_da_lotacao_do_gabinete():
    deputados = [{"id": "ana-julia", "nome": "ANA JÚLIA", "nomeCivil": None, "partido": "PT"},
                 {"id": "goura", "nome": "GOURA", "nomeCivil": None, "partido": "PDT"}]
    lista = [{"nome": "ANA JULIA RIBEIRO", "lotacao": "GAB. DEP. ANA JÚLIA RIBEIRO"}, {"nome": "OUTRO", "lotacao": "GAB. DEP. FULANO"}]
    pr.deputados_com_nome_civil(deputados, lista)
    assert deputados[0]["nomeCivil"] == "ANA JULIA RIBEIRO" and deputados[1]["nomeCivil"] is None


def test_remuneracao_do_contrato():
    registro = amostra("remuneracao")
    assert pr._conferir_remuneracao(registro) == ([], [])
    itens, bruto, liquido = pr.componentes(registro["detalhe"])
    assert bruto == 34774.64 and liquido == 25403.99
    assert itens == {"Subsídio Deputado": 34774.64, "Descontos Obrigatórios": 9370.65}


def test_diarias_so_de_deputado_ligadas_pelo_nome_civil():
    deputados = [{"id": "luis-raimundo-corti", "nome": "LUIS CORTI", "nomeCivil": "LUIS RAIMUNDO CORTI", "partido": "PSD"}]
    linhas = [
        {"emitido": "Luis Raimundo Corti", "cargo_funcao": "DEPUTADO", "data_saida": "04/08/2026", "data_retorno": "05/08/2026",
         "destino": "Brasília", "motivo": "Evento", "valor": "521.10", "quantidade_autorizada": "0,5", "protocolo": "1-1.2026"},
        {"emitido": "Luis Raimundo Corti", "cargo_funcao": "GS4", "data_saida": "04/08/2026", "valor": "10"},
        {"emitido": "Outra Pessoa", "cargo_funcao": "DEPUTADA", "data_saida": "04/08/2026", "valor": "10"},
    ]
    itens = pr.itens_diarias(linhas, deputados)
    assert itens == [{"idDeputado": "luis-raimundo-corti", "data": "2026-08-04", "dataRetorno": "2026-08-05", "destino": "Brasília",
                      "motivo": "Evento", "valor": 521.1, "quantidade": "0,5", "protocolo": "1-1.2026", "fonte": pr.DIARIAS_PAGINA}]


def test_diarias_do_contrato():
    assert pr._conferir_diarias(amostra("diarias")) == ([], [])


def test_presenca_conta_por_ano_e_mes():
    sessoes = [
        {"data": "20/10/2026", "linhas": [["PRESENTES", "JUSTIFICADOS", "AUSENTES", "TOTAL"], ["ADEMAR TRAIANO", "ANA JÚLIA DO PT ", "BAZANA", ""],
                                          ["ALEXANDRE CURI", "", "", ""]]},
        {"data": "05/11/2026", "linhas": [["PRESENTES", "JUSTIFICADOS", "AUSENTES", "TOTAL"], ["ANA JÚLIA DO PT", "", "BAZANA", ""]]},
    ]
    contagem = pr.contar_presenca(sessoes)
    assert contagem["ANA JÚLIA DO PT"] == {"2026": [1, 1, 0], "2026-10": [0, 1, 0], "2026-11": [1, 0, 0]}
    deputados = [{"id": "ana-julia", "nome": "ANA JÚLIA", "nomeCivil": None, "partido": "PT"},
                 {"id": "pedro-paulo-bazana", "nome": "PEDRO PAULO BAZANA", "nomeCivil": None, "partido": "PSD"}]
    itens = {(i["idDeputado"], i["periodo"]): i for i in pr.itens_presenca(contagem, deputados)}
    ana = itens[("ana-julia", "2026")]
    assert (ana["presente"], ana["licenca"], ana["ausente"], ana["totalSessoes"]) == (1, 1, 0, 2)
    bazana = itens[("pedro-paulo-bazana", "2026-10")]
    assert (bazana["presente"], bazana["ausente"], bazana["totalSessoes"]) == (0, 1, 1)
    assert bazana["fonte"] == pr.PRESENCA_PAGINA


def test_presenca_do_contrato():
    assert pr._conferir_presenca(amostra("presenca")) == ([], [])


def _falso_vazio(com_dados=()):
    class Resp:
        def __init__(self, corpo):
            self.corpo = corpo

        def raise_for_status(self):
            pass

        def json(self):
            return self.corpo

    class Sessao:
        def post(self, url, **kw):
            return Resp({"update": "", "data": [{"x": 1}] if "ressarcimento" in com_dados else []})

    def get_json(s, url, **params):
        nome = url.rsplit("/api/", 1)[1]
        if nome == "ressarcimento/meses":
            return {"meses": {"1": "Janeiro"}}
        if nome == "estoque/meses":
            return {"meses": {"3": "Março"} if "estoque" in com_dados else []}
        if nome == "passagens":
            return [{"x": 1}] if "passagens" in com_dados else []
        raise AssertionError(url)

    return Sessao(), get_json


def test_publicados_no_ano_so_acusa_o_que_passou_a_ter_dados(monkeypatch):
    sessao, get_json = _falso_vazio()
    monkeypatch.setattr(pr, "get_json", get_json)
    assert pr.publicados_no_ano(sessao, pr.date(2026, 10, 31)) == []
    sessao, get_json = _falso_vazio({"ressarcimento", "passagens", "estoque"})
    monkeypatch.setattr(pr, "get_json", get_json)
    assert pr.publicados_no_ano(sessao, pr.date(2026, 10, 31)) == ["ressarcimento", "passagens", "estoque"]


def test_orgao_do_contrato():
    assert pr._conferir_orgao(amostra("orgao")) == ([], [])


def test_fornecedor_do_orgao_tira_cnpj_so_quando_valido():
    assert pr.fornecedor_do_orgao("CS CAD CAM SERVICOS DE SOFTWARE LTDA - 23.324.543/0001-60") == ("CS CAD CAM SERVICOS DE SOFTWARE LTDA", "23324543000160")
    assert pr.fornecedor_do_orgao("ACME - FILIAL SUL") == ("ACME - FILIAL SUL", None)
    assert pr.fornecedor_do_orgao("EMPRESA - 11.111.111/1111-11") == ("EMPRESA - 11.111.111/1111-11", None)


def test_itens_do_orgao_id_estavel_sem_servidores_e_sem_despublicados():
    linha = {"id": 7, "publicado": 1, "fornecedor": "ACME LTDA", "objeto": "  serviço   x ", "contrato": "001/2026", "valor": 10.5, "fiscal": "Fulano",
             "gestor": "Beltrano", "inicio_vigencia": "2026-10-01T03:00:00.000000Z", "fim_vigencia": "2027-10-01T03:00:00.000000Z",
             "anexos": [{"nome_documento": "Contrato.pdf", "url": "https://x/y.pdf"}]}
    a = pr.itens_do_orgao("contrato", [linha, {**linha, "id": 8, "publicado": 0}, {**linha, "id": 9, "deleted_at": "2026-10-02"}])
    b = pr.itens_do_orgao("contrato", [linha])
    assert list(a) == list(b) and len(a) == 1
    item = next(iter(a.values()))
    assert item["objeto"] == "serviço x" and item["inicio"] == "2026-10-01" and item["fim"] == "2027-10-01" and item["arquivos"] == [{"nome": "Contrato.pdf", "url": "https://x/y.pdf"}]
    assert "fiscal" not in item and "gestor" not in item
    assert next(iter(pr.itens_do_orgao("ata_registro", [linha]))) != next(iter(a))


def test_contratos_do_ano_percorre_as_paginas(monkeypatch):
    paginas = {1: {"data": [{"id": 1}], "last_page": 2}, 2: {"data": [{"id": 2}], "last_page": 2}}
    monkeypatch.setattr(pr, "get_json", lambda s, url, ano, page: {"contratos": paginas[page]})
    assert [x["id"] for x in pr.contratos_do_ano(None, 2026)] == [1, 2]


def test_materias_liga_autores_e_ignora_quem_nao_e_deputado():
    lista = [
        {"codigo": 10, "numero": 54, "ano": 2025, "autor": "DEPUTADA ANA JÚLIA, DEPUTADO BAZANA", "dataRecebimento": "2025-02-17T19:08:35.000+0000",
         "tipoProposicao": "PROJETO DE LEI", "ementa": "CONCEDE  O TÍTULO.", "status": "TRAMITANDO"},
        {"codigo": 11, "numero": 1, "ano": 2025, "autor": "PODER EXECUTIVO", "dataRecebimento": "2025-02-17T19:08:35.000+0000",
         "tipoProposicao": "PROJETO DE LEI", "ementa": "x", "status": "ARQUIVADA"},
        {"codigo": 12, "numero": 2, "ano": 2025, "autor": "DEPUTADO ANA JÚLIA", "dataRecebimento": None, "tipoProposicao": "INDICAÇÃO",
         "ementa": "palavra " * 100, "status": "ARQUIVADA"},
    ]
    achadas = pr.materias(lista, DEPUTADOS)
    assert sorted(achadas) == ["10", "12"]
    m = achadas["10"]
    assert m["idsDeputados"] == ["ana-julia", "pedro-paulo-bazana"] and m["tipo"] == "PRO" and m["emTramitacao"] is True
    assert m["dataApresentacao"] == "2025-02-17" and m["ementa"] == "CONCEDE O TÍTULO." and m["fonte"] == pr.PROPOSICOES_PAGINA
    assert achadas["12"]["ementa"].endswith("...") and achadas["12"]["emTramitacao"] is False and achadas["12"]["dataApresentacao"] is None


def test_proposicoes_do_contrato():
    assert pr._conferir_proposicoes(amostra("proposicoes")) == ([], [])


def test_diarias_le_so_meses_que_faltam_e_os_recentes(monkeypatch):
    lidos = []

    def get_json(s, url, ano, mes=None):
        if url.endswith("/meses"):
            return {"meses": {str(m): m for m in range(1, 11)}}
        lidos.append(mes)
        return []

    monkeypatch.setattr(pr, "get_json", get_json)
    existentes = [{"idDeputado": "ana-julia", "mes": m, "data": f"2026-{m:02d}-01", "protocolo": str(m)} for m in range(1, 11)]
    existentes.append({"idDeputado": "ana-julia", "data": "2026-03-05", "protocolo": "sem-mes"})
    itens = pr.diarias_do_ano(None, 2026, DEPUTADOS, existentes, pr.date(2026, 10, 22))
    assert lidos == [9, 10]
    assert [i["mes"] for i in itens] == list(range(1, 9))


def test_remuneracao_rele_ultimo_mes_so_uma_vez_por_semana(monkeypatch):
    lidos = []
    monkeypatch.setattr(pr, "get_json", lambda s, url, ano: {"meses": {"8": 8, "9": 9}})
    monkeypatch.setattr(pr, "remuneracao_do_mes", lambda s, ano, mes, deps: lidos.append(mes) or [{"idDeputado": "ana-julia", "mes": mes}])
    anterior = {"itens": [{"idDeputado": "ana-julia", "mes": 8}, {"idDeputado": "ana-julia", "mes": 9}], "ultimoMesLidoEm": {"mes": 9, "dia": "2026-10-20"}}
    itens, marca = pr.remuneracao_do_ano(None, 2026, DEPUTADOS, anterior, pr.date(2026, 10, 22))
    assert lidos == [] and marca == {"mes": 9, "dia": "2026-10-20"} and len(itens) == 2
    itens, marca = pr.remuneracao_do_ano(None, 2026, DEPUTADOS, anterior, pr.date(2026, 10, 27))
    assert lidos == [9] and marca == {"mes": 9, "dia": "2026-10-27"} and len(itens) == 2
    itens, marca = pr.remuneracao_do_ano(None, 2026, DEPUTADOS, {"itens": [], "ultimoMesLidoEm": None}, pr.date(2026, 10, 22))
    assert lidos == [9, 8, 9] and marca == {"mes": 9, "dia": "2026-10-22"}


DEPUTADOS_VOTO = [
    {"id": "arilson-maroldi-chiorato", "nome": "ARILSON CHIORATO", "nomeCivil": "ARILSON MAROLDI CHIORATO", "partido": "PT"},
    {"id": "artagao-junior", "nome": "ARTAGÃO JUNIOR", "nomeCivil": "ARTAGAO DE MATTOS LEAO JUNIOR", "partido": "PSD"},
]


def zip_com(*nomes):
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in nomes:
            z.writestr(n, b"x")
    return buf.getvalue()


def test_votacoes_do_contrato():
    assert pr._conferir_votacoes(amostra("votacoes")) == ([], [])


def test_planilha_nominal_e_ignora_outros_tipos():
    linhas = amostra("votacoes")["linhas"]
    v = pr.votacao_da_planilha(linhas)
    assert v["titulo"].endswith("/2026") and v["item"].startswith("2") and v["resultado"] and len(v["votos"]) >= 2
    assert pr.votacao_da_planilha([{**lin, "B": "SIMBÓLICA"} if lin.get("A") == "TIPO VOTAÇÃO:" else lin for lin in linhas]) is None


def test_votacoes_do_zip_liga_deputado_grava_pdf_como_fonte_e_deixa_sem_par_de_fora(monkeypatch):
    linhas = amostra("votacoes")["linhas"]
    monkeypatch.setattr(pr.comum, "xlsx_linhas", lambda conteudo: linhas)
    zipado = zip_com("SESSAO--ITEM-134-33638-PROJETO DE LEI.xlsx", "leiame.txt")
    pdfs = {"2": "https://storage2/item2.pdf"}
    votacoes, materias, sem_par = pr.votacoes_do_zip(zipado, "1763", "2026-10-05", pdfs, "https://storage2/s.zip", DEPUTADOS_VOTO)
    (vid, v), = votacoes.items()
    assert vid == pr.ids.gerar_id("vot", "alep_pr", "1763|33638") and v["idMateria"] == vid
    assert v["data"] == "2026-10-05" and v["fonte"] == "https://storage2/item2.pdf" and v["fonteZip"] == "https://storage2/s.zip"
    assert {i for i, _ in v["votos"]} <= {"arilson-maroldi-chiorato", "artagao-junior"} and v["votos"]
    assert dict(v["votos"])["artagao-junior"] == "sim" and dict(v["votos"])["arilson-maroldi-chiorato"] == "não votou"
    assert sem_par and not sem_par & {"ARTAGAO DE MATTOS LEAO JUNIOR"}
    assert materias[vid]["tipo"] == "PRO" and materias[vid]["numero"] == 134 and materias[vid]["ano"] == 2026 and "turno" in materias[vid]["tipoDescricao"]
    sem_pdf = pr.votacoes_do_zip(zipado, "1763", "2026-10-05", {}, "https://storage2/s.zip", DEPUTADOS_VOTO)[0][vid]
    assert sem_pdf["fonte"] == "https://storage2/s.zip"


def test_aprovada_e_voto_normalizado():
    assert [pr.aprovada(x) for x in ("APROVADO", "NÃO APROVADO", "REJEITADO", "EM VOTAÇÃO", None)] == [True, False, False, None, None]
    assert [pr.voto_normalizado(x) for x in ("SIM", "NÃO", "ABSTENÇÃO", "NÃO VOTOU")] == ["sim", "não", "abstenção", "não votou"]


def test_precisa_ler_sessao():
    hoje = pr.date(2026, 10, 31)
    assert pr.precisa_ler(None, "2026-02-01", hoje, False)
    com_zip = {"data": "2026-02-01", "zip": True, "semPar": 0}
    assert not pr.precisa_ler(com_zip, "2026-02-01", hoje, False) and not pr.precisa_ler(com_zip, "2026-02-01", hoje, True)
    assert not pr.precisa_ler({**com_zip, "semPar": 2}, "2026-02-01", hoje, False) and pr.precisa_ler({**com_zip, "semPar": 2}, "2026-02-01", hoje, True)
    sem_zip = {"data": "2026-10-20", "zip": False}
    assert pr.precisa_ler(sem_zip, "2026-10-20", hoje, False)
    assert not pr.precisa_ler({"data": "2026-02-01", "zip": False}, "2026-02-01", hoje, False)
    assert pr.precisa_ler({"data": "2026-02-01", "zip": False}, "2026-02-01", hoje, True)


def test_votacoes_do_ano_incremental(monkeypatch):
    hoje = pr.date(2026, 10, 31)
    lidas = []
    sessoes = [("1", "2026-02-10", 2, "10"), ("2", "2026-09-10", 9, "10"), ("3", "2026-10-27", 10, "27")]
    zips = {"1": "u/1.zip", "2": None, "3": "u/3.zip"}
    monkeypatch.setattr(pr, "sessoes_do_ano", lambda s, ano, h, completa: sessoes)
    monkeypatch.setattr(pr, "zip_da_sessao", lambda s, sid: zips[sid])
    monkeypatch.setattr(pr, "pdfs_da_sessao", lambda *a: {})
    monkeypatch.setattr(pr.comum, "baixar", lambda s, url, **kw: url.encode())
    monkeypatch.setattr(pr.time, "sleep", lambda s: None)

    def zip_falso(conteudo, sid, data, pdfs, url, deputados):
        lidas.append(sid)
        return {f"v{sid}": {"data": data, "sessao": sid, "votos": []}}, {f"v{sid}": {"tipo": "PRO"}}, set()

    monkeypatch.setattr(pr, "votacoes_do_zip", zip_falso)
    votos, mats, estado, completa = pr.votacoes_do_ano(None, 2026, DEPUTADOS_VOTO, {}, hoje)
    assert completa and lidas == ["1", "3"] and sorted(votos) == ["v1", "v3"] and sorted(mats) == ["v1", "v3"]
    assert estado["2"]["zip"] is False and estado["1"]["zip"] is True

    lidas.clear()
    arquivo = {"completaEm": "2026-10-25", "sessoes": estado, "votacoes": votos, "materiasVotadas": mats}
    zips["2"], zips["3"] = "u/2.zip", "u/3.zip"
    votos, mats, estado, completa = pr.votacoes_do_ano(None, 2026, DEPUTADOS_VOTO, arquivo, hoje)
    assert not completa and lidas == []   # a 2 é antiga e sem ZIP: só a coleta completa confere
    assert sorted(votos) == ["v1", "v3"]

    arquivo["completaEm"] = "2026-10-01"
    votos, mats, estado, completa = pr.votacoes_do_ano(None, 2026, DEPUTADOS_VOTO, arquivo, hoje)
    assert completa and lidas == ["2"] and sorted(votos) == ["v1", "v2", "v3"] and sorted(mats) == ["v1", "v2", "v3"]


def test_normas_so_de_deputado_ligado():
    amostra_normas = amostra("normas")
    assert pr._conferir_normas(amostra_normas) == ([], [])
    lista = [
        {"codigo": 1, "numero": 23051, "ano": 2026, "data": "2026-03-19T03:00:00.000+0000", "ementa": "CONCEDE  O TÍTULO.",
         "autores": "DEPUTADO ALEXANDRE CURI, DEPUTADA ANA JÚLIA", "descricaoTipoNormaLegal": "Lei", "tipoMovimentacao": "SANCIONADO(A)"},
        {"codigo": 2, "numero": 1, "ano": 2026, "data": None, "ementa": "x", "autores": "COMISSÃO EXECUTIVA", "descricaoTipoNormaLegal": "Lei"},
    ]
    achadas = pr.normas(lista, DEPUTADOS)
    assert list(achadas) == ["1"]
    assert achadas["1"] == {"tipo": "Lei", "numero": 23051, "ano": 2026, "data": "2026-03-19", "ementa": "CONCEDE O TÍTULO.", "situacao": "SANCIONADO(A)",
                            "idsDeputados": ["alexandre-curi", "ana-julia"], "fonte": pr.NORMAS_PAGINA}


def test_pautas_do_contrato():
    falhas, _ = pr._conferir_pautas(amostra("pautas"))
    assert falhas == []


def test_itens_pauta_normaliza_fuso_arquivos_e_comissoes():
    ordem = {"s1": [{"id": 7, "publicado": True, "titulo": " 14ª  SESSÃO ", "data_sessao": "2026-11-03T01:30:00.000000Z", "arquivo": None,
                     "arquivos": [{"titulo": "PDF", "url": "https://x/a.pdf"}, {"titulo": "PDF", "url": "https://x/a.pdf"}, {"titulo": "sem", "url": None}]},
                    {"id": 8, "publicado": False, "titulo": "rascunho", "data_sessao": "2026-11-04T12:00:00Z", "arquivos": [{"url": "https://x/b.pdf"}]},
                    {"id": 9, "publicado": True, "titulo": "sem arquivo", "data_sessao": "2026-11-05T12:00:00Z", "arquivos": []}]}
    itens = pr.itens_pauta("ordem-do-dia", ordem)
    assert itens == [{"id": "7", "tipo": "ordem-do-dia", "titulo": "14ª SESSÃO", "data": "2026-11-02", "arquivos": [{"nome": "PDF", "url": "https://x/a.pdf"}]}]
    comissoes = {"s": {"Comissão X": [{"comissao": "Comissão X", "data": "2026-11-03", "nome_reuniao": "5ª Reunião", "arquivos": {"pauta": [{"titulo": "p", "url": "https://x/c.pdf"}], "ata": []}}]}}
    c = pr.itens_pauta("comissoes", comissoes)[0]
    assert c["id"] is None and c["comissao"] == "Comissão X" and c["arquivos"][0]["url"] == "https://x/c.pdf"
    assert pr.chave_pauta(c) == "comissoes|Comissão X|2026-11-03|5ª Reunião"


def test_pautas_do_ano_incremental_para_na_pagina_antiga(monkeypatch):
    hoje = pr.date(2026, 10, 31)
    paginas = {1: {"s": [{"id": 3, "titulo": "nova", "data_sessao": "2026-10-28T15:00:00Z", "arquivos": [{"url": "https://x/3.pdf"}]}]},
               2: {"s": [{"id": 2, "titulo": "velha", "data_sessao": "2026-02-10T15:00:00Z", "arquivos": [{"url": "https://x/2.pdf"}]}]},
               3: {"s": [{"id": 1, "titulo": "mais velha", "data_sessao": "2026-02-03T15:00:00Z", "arquivos": [{"url": "https://x/1.pdf"}]}]}}
    pedidas = []

    class Resp:
        def __init__(self, dados):
            self.dados = dados

        def raise_for_status(self):
            pass

        def json(self):
            return {"data": self.dados}

    class Sessao:
        def get(self, url, params, **kw):
            pedidas.append((url.rsplit("/", 2)[-2], params["page"]))
            return Resp(paginas.get(params["page"]) if "ordem" in url else None)

    monkeypatch.setattr(pr.time, "sleep", lambda s: None)
    todas = pr.pautas_do_ano(Sessao(), 2026, hoje, {}, True)
    assert sorted(i["id"] for i in todas.values()) == ["1", "2", "3"]
    pedidas.clear()
    anterior = {pr.chave_pauta(i): i for i in todas.values() if i["id"] == "1"}
    inc = pr.pautas_do_ano(Sessao(), 2026, hoje, anterior, False)
    assert sorted(i["id"] for i in inc.values()) == ["1", "2", "3"]
    assert ("ordem-do-dia", 3) not in pedidas and ("ordem-do-dia", 2) in pedidas


def test_gabinete_do_contrato():
    assert pr._conferir_gabinete(amostra("gabinete")) == ([], [])


def test_servidores_do_gabinete_liga_so_lotacao_de_deputado():
    linhas = [["FUNCIONARIO", "NOME", "SIGLA", "LOTAÇÃO CARGO"],
              ["1", "FULANO  DA SILVA", "G-7", "GAB. DEP. ANA JÚLIA"],
              ["2", "BELTRANO", "G-3", "GAB. DEP. LUIS CORTI"],
              ["3", "CICLANO", "G-3", "LIDERANÇA DO PSD"],
              ["4", "SEM LOTACAO", "SDP", ""],
              ["5", "DE OUTRO", "G-1", "GAB. DEP. NINGUEM CONHECIDO"],
              ["6", "SEM SIMBOLO", "", "GAB. DEP. ANA JÚLIA"]]
    itens = pr.servidores_do_gabinete(linhas, DEPUTADOS)
    assert itens == [{"idDeputado": "ana-julia", "matricula": "6", "nome": "SEM SIMBOLO", "simbolo": None},
                     {"idDeputado": "ana-julia", "matricula": "1", "nome": "FULANO DA SILVA", "simbolo": "G-7"},
                     {"idDeputado": "luis-raimundo-corti", "matricula": "2", "nome": "BELTRANO", "simbolo": "G-3"}]


def test_gabinete_atual_decodifica_utf8_e_rejeita_lista_vazia():
    class Resp:
        def __init__(self, corpo):
            self.content = corpo

        def raise_for_status(self):
            pass

    class Sessao:
        def __init__(self, corpo):
            self.corpo = corpo

        def get(self, url, **kw):
            return Resp(self.corpo)

    bom = json.dumps([["F", "N", "S", "L"], ["1", "JOSÉ", "G-1", "GAB. DEP. ANA JÚLIA"]], ensure_ascii=False).encode("utf-8")
    assert pr.gabinete_atual(Sessao(bom), DEPUTADOS)[0]["nome"] == "JOSÉ"
    try:
        pr.gabinete_atual(Sessao(b"[]"), DEPUTADOS)
    except RuntimeError:
        return
    raise AssertionError("lista vazia deveria falhar")



class RespPr:
    def __init__(self, dados=None, status=200, texto=""):
        self.status_code = status
        self.dados = dados
        self.text = texto
        self.content = texto.encode("utf-8")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        if self.dados is None:
            raise ValueError("sem json")
        return self.dados


class SessaoPr:
    def __init__(self, get=None, post=None):
        self.chamadas_get, self.chamadas_post = [], []
        self.fn_get, self.fn_post = get, post

    def get(self, url, **kw):
        self.chamadas_get.append((url, kw))
        return self.fn_get(url, kw)

    def post(self, url, **kw):
        self.chamadas_post.append((url, kw))
        return self.fn_post(url, kw)


def test_get_json_passa_parametros_cabecalho_e_levanta_em_erro():
    s = SessaoPr(get=lambda url, kw: RespPr({"meses": {"1": 1}}))
    assert pr.get_json(s, "https://x/api", ano=2026) == {"meses": {"1": 1}}
    url, kw = s.chamadas_get[0]
    assert url == "https://x/api" and kw["params"] == {"ano": 2026} and kw["headers"]["X-Requested-With"] == "XMLHttpRequest"
    with pytest.raises(RuntimeError, match="HTTP 500"):
        pr.get_json(SessaoPr(get=lambda url, kw: RespPr(status=500)), "https://x/api")


def test_detalhe_remuneracao_espera_429_e_desiste_depois_de_seis(monkeypatch):
    esperas = []
    monkeypatch.setattr(pr.time, "sleep", esperas.append)
    respostas = [RespPr(status=429), RespPr(status=429), RespPr({"valores": []})]
    s = SessaoPr(post=lambda url, kw: respostas.pop(0))
    r = {"matricula": 77, "id": 5}
    assert pr.detalhe_remuneracao(s, r, 10, 2026, {"X-CSRF-TOKEN": "t"}) == {"valores": []}
    assert esperas == [5, 10, pr.PAUSA]
    url, kw = s.chamadas_post[0]
    assert url == f"{pr.PORTAL}/api/remuneracao/77" and kw["data"] == {"t": pr.TIPO_REMUNERACAO, "mes": 10, "ano": 2026, "id": 5}
    assert kw["headers"] == {"X-CSRF-TOKEN": "t"}

    esperas.clear()
    sempre = SessaoPr(post=lambda url, kw: RespPr(status=429))
    with pytest.raises(RuntimeError, match="HTTP 429"):
        pr.detalhe_remuneracao(sempre, r, 10, 2026, {})
    assert len(sempre.chamadas_post) == 6 and esperas == [5, 10, 15, 20, 25, 30]


def test_remuneracao_do_mes_pagina_liga_pelo_gabinete_e_pula_sem_par(monkeypatch):
    monkeypatch.setattr(pr.time, "sleep", lambda s: None)
    paginas = {1: {"remuneracoes": [{"id": 1, "matricula": 11, "nome": "ALEXANDRE MARANHAO KHURY", "lotacao": "GAB. DEP. ALEXANDRE CURI"},
                                    {"id": 2, "matricula": 22, "nome": "FULANO SEM PAR", "lotacao": "SETOR X"}], "last_page": 2},
               2: {"remuneracoes": [{"id": 3, "matricula": 33, "nome": "ANA JULIA RIBEIRO", "lotacao": "GAB. DEP. ANA JÚLIA"}], "last_page": 2}}

    def get(url, kw):
        if url == pr.REMUNERACAO_PAGINA:
            return RespPr(texto='<meta name="csrf-token" content="tok123">')
        return RespPr(paginas[kw["params"]["page"]])

    def post(url, kw):
        assert kw["headers"]["X-CSRF-TOKEN"] == "tok123"
        return RespPr({"valores": [["Total Bruto", "Valor Bruto (- Descontos Obrigatórios)", "Subsídio (1)"], ["35.000,00", "30.000,00", "20.000,00"]]})

    s = SessaoPr(get=get, post=post)
    itens = pr.remuneracao_do_mes(s, 2026, 10, DEPUTADOS)
    assert [(i["idDeputado"], i["mes"], i["bruto"], i["liquido"], i["componentes"]) for i in itens] == [
        ("alexandre-curi", 10, 35000.0, 30000.0, {"Subsídio": 20000.0}), ("ana-julia", 10, 35000.0, 30000.0, {"Subsídio": 20000.0})]
    assert [url for url, _ in s.chamadas_post] == [f"{pr.PORTAL}/api/remuneracao/11", f"{pr.PORTAL}/api/remuneracao/33"]
    assert [kw["params"]["page"] for url, kw in s.chamadas_get if url != pr.REMUNERACAO_PAGINA] == [1, 2]
    assert itens[0]["fonte"] == pr.REMUNERACAO_PAGINA


def test_remuneracao_do_mes_sem_token_envia_cabecalho_vazio_e_lista_vazia(monkeypatch):
    s = SessaoPr(get=lambda url, kw: RespPr(texto="<html></html>") if url == pr.REMUNERACAO_PAGINA else RespPr({"remuneracoes": [], "last_page": 0}))
    assert pr.remuneracao_do_mes(s, 2026, 10, DEPUTADOS) == []
    assert s.chamadas_get[1][1]["headers"]["X-CSRF-TOKEN"] == ""


def test_regras_do_ressarcimento_pega_a_resolucao_mais_nova():
    pagina = ('<a href="https://x/ressarcimento_da_atividade_parlamentar/2019/Resolução 11.pdf">a</a>'
              '<a href="https://x/ressarcimento_da_atividade_parlamentar/2024/Ato 5 de 2024.pdf">b</a>'
              '<a href="https://x/outra/2025/z.pdf">c</a>')
    regra = pr.regras_do_ressarcimento(SessaoPr(get=lambda url, kw: RespPr(texto=pagina)))
    assert regra == {"url": "https://x/ressarcimento_da_atividade_parlamentar/2024/Ato%205%20de%202024.pdf", "ano": 2024, "fonte": pr.RESSARCIMENTO_REGRAS_PAGINA}
    assert pr.regras_do_ressarcimento(SessaoPr(get=lambda url, kw: RespPr(texto="<p>sem pdf</p>"))) is None
    with pytest.raises(RuntimeError, match="HTTP 500"):
        pr.regras_do_ressarcimento(SessaoPr(get=lambda url, kw: RespPr(status=500)))


def test_proposicoes_do_ano_tenta_de_novo_so_em_erro_de_rede(monkeypatch):
    esperas = []
    monkeypatch.setattr(pr.time, "sleep", esperas.append)
    respostas = [requests.ConnectionError("caiu"), requests.Timeout("lento"), RespPr({"sucesso": True, "lista": [{"codigo": 1}]})]

    def post(url, kw):
        r = respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    s = SessaoPr(post=post)
    assert pr.proposicoes_do_ano(s, 2026) == [{"codigo": 1}]
    assert esperas == [15, 15] and s.chamadas_post[0][0] == f"{pr.API_PROPOSICOES}/proposicao/filtrar" and s.chamadas_post[0][1]["json"] == {"ano": 2026}

    def sempre(url, kw):
        raise requests.ConnectionError("caiu")

    with pytest.raises(requests.ConnectionError):
        pr.proposicoes_do_ano(SessaoPr(post=sempre), 2026)
    with pytest.raises(RuntimeError, match="proposicao/filtrar 2026: falhou"):
        pr.proposicoes_do_ano(SessaoPr(post=lambda url, kw: RespPr({"sucesso": False, "erro": "falhou"})), 2026)
    assert pr.proposicoes_do_ano(SessaoPr(post=lambda url, kw: RespPr({"sucesso": True, "lista": None})), 2026) == []


def test_normas_do_ano_levanta_quando_o_webservice_nao_tem_sucesso():
    s = SessaoPr(post=lambda url, kw: RespPr({"sucesso": True, "lista": [{"codigo": 3}]}))
    assert pr.normas_do_ano(s, 2026) == [{"codigo": 3}]
    assert s.chamadas_post[0][0] == f"{pr.API_PROPOSICOES}/norma-legal/filtrar"
    with pytest.raises(RuntimeError, match="norma-legal/filtrar 2026: erro"):
        pr.normas_do_ano(SessaoPr(post=lambda url, kw: RespPr({"sucesso": False, "erro": "erro"})), 2026)
    with pytest.raises(RuntimeError, match="HTTP 502"):
        pr.normas_do_ano(SessaoPr(post=lambda url, kw: RespPr(status=502)), 2026)


def test_sessoes_do_ano_completa_lista_todos_os_meses_e_incremental_so_os_recentes(monkeypatch):
    consultas = []

    def get_json(s, url, **params):
        consultas.append((url.rsplit("/", 1)[1], params.get("mes")))
        if url.endswith("/meses"):
            return {"meses": {"1": 1, "9": 9, "10": 10}}
        if url.endswith("/datas"):
            return ["05"]
        return [params["mes"] * 100]

    monkeypatch.setattr(pr, "get_json", get_json)
    hoje = pr.date(2026, 10, 31)
    assert pr.sessoes_do_ano(None, 2026, hoje, True) == [("100", "2026-01-05", 1, "05"), ("900", "2026-09-05", 9, "05"), ("1000", "2026-10-05", 10, "05")]
    consultas.clear()
    assert pr.sessoes_do_ano(None, 2026, hoje, False) == [("900", "2026-09-05", 9, "05"), ("1000", "2026-10-05", 10, "05")]
    assert ("datas", 1) not in consultas


def test_zip_da_sessao_trata_erro_5xx_e_corpo_sem_json():
    def sessao(resp):
        return SessaoPr(get=lambda url, kw: resp)

    assert pr.zip_da_sessao(sessao(RespPr({"arquivo": "https://storage2/s.zip"})), "55") == "https://storage2/s.zip"
    assert pr.zip_da_sessao(sessao(RespPr({"arquivo": ""})), "55") is None
    assert pr.zip_da_sessao(sessao(RespPr(status=404)), "55") is None
    with pytest.raises(RuntimeError, match="HTTP 503"):
        pr.zip_da_sessao(sessao(RespPr(status=503)), "55")
    s = sessao(RespPr({"arquivo": None}))
    pr.zip_da_sessao(s, "55")
    assert s.chamadas_get[0][1]["params"] == {"sessao": "55"}


def test_pdfs_da_sessao_indexa_pelo_numero_do_item(monkeypatch):
    consulta = []

    def get_json(s, url, **params):
        consulta.append((url, params))
        return [{"item": "ITEM 2 - PL", "arquivo": "https://x/2.pdf"}, {"item": "ITEM 3", "arquivo": None}, {"item": "Mesa", "arquivo": "https://x/m.pdf"},
                {"item": None, "arquivo": "https://x/n.pdf"}]

    monkeypatch.setattr(pr, "get_json", get_json)
    assert pr.pdfs_da_sessao(None, 2026, 10, "05", "55") == {"2": "https://x/2.pdf"}
    assert consulta == [(pr.VOTACOES_API, {"ano": 2026, "mes": 10, "data": "05", "sessao": "55"})]


def test_votacoes_do_ano_avisa_nomes_sem_par_e_guarda_sessao_sem_zip(monkeypatch, capsys):
    hoje = pr.date(2026, 10, 31)
    monkeypatch.setattr(pr, "sessoes_do_ano", lambda s, ano, h, completa: [("1", "2026-10-20", 10, "20"), ("2", "2026-10-21", 10, "21")])
    monkeypatch.setattr(pr, "zip_da_sessao", lambda s, sid: "u/1.zip" if sid == "1" else None)
    monkeypatch.setattr(pr, "pdfs_da_sessao", lambda *a: {})
    monkeypatch.setattr(pr.comum, "baixar", lambda s, url, **kw: b"zip")
    monkeypatch.setattr(pr.time, "sleep", lambda s: None)
    monkeypatch.setattr(pr, "votacoes_do_zip", lambda *a: ({"v1": {"sessao": "1", "votos": []}}, {"v1": {"tipo": "PRO"}}, {"ZULU", "ALFA"}))
    votos, mats, estado, completa = pr.votacoes_do_ano(None, 2026, DEPUTADOS_VOTO, {}, hoje)
    assert estado == {"1": {"data": "2026-10-20", "zip": True, "lidoEm": "2026-10-31", "semPar": 2}, "2": {"data": "2026-10-21", "zip": False, "lidoEm": "2026-10-31"}}
    assert "AVISO: PR: votos de nomes sem deputado ligado (não gravados): ALFA, ZULU" in capsys.readouterr().err
    assert completa and list(votos) == ["v1"]


def test_votacoes_do_ano_troca_votacoes_da_sessao_relida_e_descarta_materias_orfas(monkeypatch):
    hoje = pr.date(2026, 10, 31)
    monkeypatch.setattr(pr, "sessoes_do_ano", lambda s, ano, h, completa: [("1", "2026-10-20", 10, "20")])
    monkeypatch.setattr(pr, "zip_da_sessao", lambda s, sid: "u/1.zip")
    monkeypatch.setattr(pr, "pdfs_da_sessao", lambda *a: {})
    monkeypatch.setattr(pr.comum, "baixar", lambda s, url, **kw: b"zip")
    monkeypatch.setattr(pr.time, "sleep", lambda s: None)
    monkeypatch.setattr(pr, "votacoes_do_zip", lambda *a: ({"novo": {"sessao": "1"}}, {"novo": {"tipo": "PRO"}}, set()))
    arquivo = {"completaEm": "2026-10-01", "sessoes": {"1": {"data": "2026-10-20", "zip": True, "semPar": 1}},
               "votacoes": {"velho": {"sessao": "1"}, "outro": {"sessao": "9"}}, "materiasVotadas": {"velho": {"tipo": "X"}, "outro": {"tipo": "Y"}}}
    votos, mats, estado, completa = pr.votacoes_do_ano(None, 2026, DEPUTADOS_VOTO, arquivo, hoje)
    assert completa and sorted(votos) == ["novo", "outro"] and sorted(mats) == ["novo", "outro"]


def servidor_de_endpoints_vazios(ressarcimento, passagens, estoque, postados):
    def get_json(s, url, **params):
        if url.endswith("/meses"):
            nome = url.rsplit("/", 2)[1]
            tem = (nome == "ressarcimento" and ressarcimento) or (nome == "estoque" and estoque)
            return {"meses": {"3": 3} if tem else {}}
        return passagens

    def post(url, kw):
        postados.append(kw["data"])
        return RespPr({"data": [{"id": 1}] if ressarcimento else []})

    return get_json, SessaoPr(post=post)


def test_publicados_no_ano_e_avisar_publicados(monkeypatch, capsys):
    postados = []
    get_json, s = servidor_de_endpoints_vazios(True, [{"id": 1}], True, postados)
    monkeypatch.setattr(pr, "get_json", get_json)
    assert pr.publicados_no_ano(s, pr.date(2026, 10, 31)) == ["ressarcimento", "passagens", "estoque"]
    assert postados == [{"ano": 2026, "mes": 3}]
    pr.avisar_publicados(s, pr.date(2026, 10, 31))
    assert "AVISO: PR: ressarcimento, passagens, estoque passaram a trazer registros" in capsys.readouterr().err

    get_json, s = servidor_de_endpoints_vazios(False, [], False, [])
    monkeypatch.setattr(pr, "get_json", get_json)
    assert pr.publicados_no_ano(s, pr.date(2026, 10, 31)) == []
    pr.avisar_publicados(s, pr.date(2026, 10, 31))
    assert capsys.readouterr().err == ""

    def erro(s, url, **params):
        raise RuntimeError("HTTP 500")

    monkeypatch.setattr(pr, "get_json", erro)
    with pytest.raises(RuntimeError, match="HTTP 500"):
        pr.publicados_no_ano(s, pr.date(2026, 10, 31))


def preparar_coleta_pr(monkeypatch, tmp_path, html):
    monkeypatch.setattr(pr.comum, "DADOS", tmp_path)
    monkeypatch.setattr(pr.comum, "sessao", lambda: SessaoPr(get=lambda url, kw: RespPr(texto=html)))
    monkeypatch.setattr(pr.time, "sleep", lambda s: None)
    return tmp_path / "PR"


def test_coletar_lista_de_deputados_vazia_para_na_hora(monkeypatch, tmp_path, capsys):
    pasta = preparar_coleta_pr(monkeypatch, tmp_path, "<html></html>")

    def get_json(*a, **k):
        raise AssertionError("não deveria consultar a API")

    monkeypatch.setattr(pr, "get_json", get_json)
    pr.coletar()
    assert "AVISO: PR: lista de deputados vazia" in capsys.readouterr().err and not pasta.exists()


def test_coletar_monta_arquivos_pula_ano_encerrado_e_isola_etapas_com_erro(monkeypatch, tmp_path, capsys):
    hoje = pr.date.today()
    antigo = hoje.year - 3
    html = amostra("deputados")["html"]
    pasta = preparar_coleta_pr(monkeypatch, tmp_path, html)
    monkeypatch.setattr(pr, "PRIMEIRO_ANO", antigo)
    pr.comum.salvar(pasta / f"materias_{antigo}.json", {"materias": {"1": {}}})
    pr.comum.salvar(pasta / f"normas_{antigo}.json", {"normas": {"1": {}}})
    pr.comum.salvar(pasta / f"diarias_{antigo}.json", {"itens": [{"marca": "antiga"}]})
    pr.comum.salvar(pasta / f"orgao_{antigo}.json", {"itens": {"ctr_x": {}}})
    pr.comum.salvar(pasta / f"normas_{hoje.year}.json", {"normas": {"1": {"ano": 2026}}})
    pr.comum.salvar(pasta / "presenca.json", {"itens": [{"idDeputado": "x", "periodo": "2020", "presente": 1, "ausente": 0, "licenca": 0, "totalSessoes": 1}]})
    chamadas = {"proposicoes": [], "normas": [], "diarias": [], "contratos": [], "pautas": [], "votacoes": [], "remuneracao": [], "presenca": []}

    def get_json(s, url, **params):
        if url == f"{pr.PORTAL}/api/remuneracao/meses":
            return {"meses": {"9": 9, "10": 10}}
        if url == f"{pr.PORTAL}/api/remuneracao":
            return {"remuneracoes": [{"nome": "ALEXANDRE MARANHAO KHURY", "lotacao": "GAB. DEP. ALEXANDRE CURI"}]}
        if url == f"{pr.PORTAL}/api/presenca/ano":
            chamadas["presenca"].append(params["ano"])
            return {"sessoes": [{"data": "05/02/2026", "linhas": [["PRESENTES", "JUSTIFICADOS", "AUSENTES"], ["ALEXANDRE CURI", "", ""]]}]}
        if url in pr.ORGAO_APIS.values():
            return {"data": []}
        raise AssertionError(url)

    def proposicoes(s, ano):
        chamadas["proposicoes"].append(ano)
        return [{"codigo": 1, "autor": "DEPUTADO ALEXANDRE CURI", "tipoProposicao": "PROJETO DE LEI", "ementa": "x", "numero": 1, "ano": ano,
                 "status": "TRAMITANDO", "dataRecebimento": "2026-02-01"}]

    def normas_vazias(s, ano):
        chamadas["normas"].append(ano)
        return []

    def diarias(s, ano, deputados, existentes, hoje_):
        chamadas["diarias"].append(ano)
        return [{"idDeputado": "alexandre-curi", "data": "2026-02-01", "protocolo": "1"}]

    def contratos(s, ano):
        chamadas["contratos"].append(ano)
        return [{"id": 7, "fornecedor": "ACME LTDA", "objeto": "x", "inicio_vigencia": "05/10/2026", "valor": 10.0, "contrato": "1/2026"}]

    def pautas(s, ano, hoje_, anterior, completa):
        chamadas["pautas"].append((ano, completa))
        return {"ordem-do-dia|1": {"id": "1", "tipo": "ordem-do-dia"}}

    def votacoes(s, ano, deputados, arquivo, hoje_):
        chamadas["votacoes"].append(ano)
        return {"v": {}}, {"v": {}}, {"1": {"zip": True}}, True

    def remuneracao(s, ano, deputados, anterior, hoje_):
        chamadas["remuneracao"].append(ano)
        return [], {"mes": 10, "dia": hoje_.isoformat()}

    monkeypatch.setattr(pr, "get_json", get_json)
    monkeypatch.setattr(pr, "proposicoes_do_ano", proposicoes)
    monkeypatch.setattr(pr, "normas_do_ano", normas_vazias)
    monkeypatch.setattr(pr, "diarias_do_ano", diarias)
    monkeypatch.setattr(pr, "contratos_do_ano", contratos)
    monkeypatch.setattr(pr, "pautas_do_ano", pautas)
    monkeypatch.setattr(pr, "votacoes_do_ano", votacoes)
    monkeypatch.setattr(pr, "remuneracao_do_ano", remuneracao)
    monkeypatch.setattr(pr, "gabinete_atual", lambda s, deputados: [{"idDeputado": "alexandre-curi", "matricula": "1", "nome": "F", "simbolo": "G-1"}])
    monkeypatch.setattr(pr, "regras_do_ressarcimento", lambda s: {"url": "https://x/r.pdf", "ano": 2024, "fonte": pr.RESSARCIMENTO_REGRAS_PAGINA})
    monkeypatch.setattr(pr, "avisar_publicados", lambda s, h: None)
    pr.coletar()

    anos = list(range(antigo, hoje.year + 1))
    erro = capsys.readouterr().err
    assert chamadas["pautas"] == [(a, True) for a in anos] and chamadas["votacoes"] == anos
    assert chamadas["proposicoes"] == anos[1:] and chamadas["normas"] == anos[1:] and chamadas["diarias"] == anos[1:] and chamadas["contratos"] == anos[1:]
    assert chamadas["remuneracao"] == [hoje.year] and chamadas["presenca"] == [hoje.year - 1, hoje.year]
    assert f"AVISO: PR: normas {hoje.year}: webservice devolveu lista vazia para {hoje.year}; mantém o arquivo anterior" in erro
    assert json.loads((pasta / f"diarias_{antigo}.json").read_text(encoding="utf-8"))["itens"] == [{"marca": "antiga"}]
    assert json.loads((pasta / f"normas_{hoje.year}.json").read_text(encoding="utf-8"))["normas"] == {"1": {"ano": 2026}}
    deputados = json.loads((pasta / "deputados.json").read_text(encoding="utf-8"))["deputados"]
    assert next(d for d in deputados if d["id"] == "alexandre-curi")["nomeCivil"] == "ALEXANDRE MARANHAO KHURY"
    assert list(json.loads((pasta / f"materias_{hoje.year}.json").read_text(encoding="utf-8"))["materias"]) == ["1"]
    assert len(json.loads((pasta / f"orgao_{hoje.year}.json").read_text(encoding="utf-8"))["itens"]) == 1
    assert json.loads((pasta / f"remuneracao_{hoje.year}.json").read_text(encoding="utf-8"))["ultimoMesLidoEm"]["mes"] == 10
    assert set(json.loads((pasta / f"pautas_{hoje.year}.json").read_text(encoding="utf-8"))["itens"]) == {"ordem-do-dia|1"}
    assert json.loads((pasta / "votacoes.json").read_text(encoding="utf-8"))["sessoes"] == {"1": {"zip": True}}
    assert (pasta / "materias_votadas.json").exists()
    presenca = json.loads((pasta / "presenca.json").read_text(encoding="utf-8"))["itens"]
    assert presenca[0]["periodo"] == "2020" and {i["idDeputado"] for i in presenca[1:]} == {"alexandre-curi"}
    assert json.loads((pasta / "gabinete.json").read_text(encoding="utf-8"))["itens"][0]["idDeputado"] == "alexandre-curi"
    assert json.loads((pasta / "regras_ressarcimento.json").read_text(encoding="utf-8"))["ano"] == 2024


def test_coletar_etapas_sem_resultado_viram_aviso_e_nao_gravam(monkeypatch, tmp_path, capsys):
    hoje = pr.date.today()
    pasta = preparar_coleta_pr(monkeypatch, tmp_path, amostra("deputados")["html"])
    pr.comum.salvar(pasta / f"orgao_{hoje.year}.json", {"itens": {"ctr_x": {}}})
    pr.comum.salvar(pasta / f"materias_{hoje.year}.json", {"materias": {"1": {}}})

    def get_json(s, url, **params):
        if url == f"{pr.PORTAL}/api/remuneracao/meses":
            return {"meses": {}}
        if url == f"{pr.PORTAL}/api/presenca/ano":
            return {}
        if url in pr.ORGAO_APIS.values():
            return {"data": []}
        raise RuntimeError("HTTP 500")

    monkeypatch.setattr(pr, "get_json", get_json)
    monkeypatch.setattr(pr, "contratos_do_ano", lambda s, ano: [])
    monkeypatch.setattr(pr, "proposicoes_do_ano", lambda s, ano: [])
    monkeypatch.setattr(pr, "normas_do_ano", lambda s, ano: (_ for _ in ()).throw(RuntimeError("norma-legal/filtrar: falhou")))
    monkeypatch.setattr(pr, "pautas_do_ano", lambda *a: (_ for _ in ()).throw(RuntimeError("HTTP 500")))
    monkeypatch.setattr(pr, "votacoes_do_ano", lambda *a: (_ for _ in ()).throw(RuntimeError("HTTP 500")))
    monkeypatch.setattr(pr, "gabinete_atual", lambda s, deputados: [])
    monkeypatch.setattr(pr, "regras_do_ressarcimento", lambda s: None)
    monkeypatch.setattr(pr, "avisar_publicados", lambda s, h: (_ for _ in ()).throw(RuntimeError("fora do ar")))
    pr.coletar()
    erro = capsys.readouterr().err
    ano = hoje.year
    assert "AVISO: PR: sem nome civil (sem diárias):" in erro
    assert f"AVISO: PR: proposições {ano}: webservice devolveu lista vazia para {ano}; mantém o arquivo anterior" in erro
    assert f"AVISO: PR: normas {ano}: norma-legal/filtrar: falhou" in erro
    assert f"AVISO: PR: pautas e atas {ano}: HTTP 500" in erro and f"AVISO: PR: votações {ano}: HTTP 500" in erro
    assert f"AVISO: PR: contratos e atas {ano}: portal devolveu lista vazia para {ano}; mantém o arquivo anterior" in erro
    assert f"AVISO: PR: diárias {ano}: HTTP 500" in erro and f"AVISO: PR: remuneração {ano}" not in erro
    assert "AVISO: PR: gabinete: nenhum servidor ligado a gabinete de deputado; mantém o arquivo anterior" in erro
    assert "AVISO: PR: regras do ressarcimento: nenhum PDF de resolução do ressarcimento na página; mantém o arquivo anterior" in erro
    assert "AVISO: PR: fontes vazias: fora do ar" in erro
    assert not (pasta / "gabinete.json").exists() and not (pasta / "regras_ressarcimento.json").exists()
    assert json.loads((pasta / f"orgao_{ano}.json").read_text(encoding="utf-8"))["itens"] == {"ctr_x": {}}
