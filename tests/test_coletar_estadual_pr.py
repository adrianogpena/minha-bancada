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
