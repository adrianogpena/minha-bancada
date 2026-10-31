import json

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
