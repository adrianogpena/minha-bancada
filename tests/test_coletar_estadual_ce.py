"""Coletor da Assembleia do Ceará (scripts/coletar_estadual_ce.py) contra amostras reais em tests/fixtures/contratos/."""
import json

import pytest

import coletar_estadual_ce as ce
import estaduais_comum as comum
import identidades
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"


def fixture(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))


def amostra(nome):
    return fixture(nome)["amostra"]


DEPUTADOS = [
    {"id": "agenor-neto", "nome": "Agenor Neto", "nomeCivil": "Agenor Gomes de Araújo Neto"},
    {"id": "ap-luiz-henrique", "nome": "Ap Luiz Henrique", "nomeCivil": "Luiz Henrique Castelo Lima"},
    {"id": "dra-silvana", "nome": "Dra. Silvana", "nomeCivil": "Silvana Oliveira de Sousa"},
    {"id": "larissa-gaspar", "nome": "Larissa Gaspar", "nomeCivil": "Larissa Maria Fernandes Gaspar da Costa"},
    {"id": "jeova-mota", "nome": "Jeová Mota", "nomeCivil": "Jeová Mota"},
]


def test_contratos_registrados():
    assert [c["nome"] for c in ce.CONTRATOS] == [f"estadual_ce_{x}" for x in
                                                 ("deputados", "vdp", "pessoal", "diarias", "votacoes_lista", "votacao_xlsx", "proposicoes")]
    for c in ce.CONTRATOS:
        falhas, _ = c["html"](amostra(c["nome"]))
        assert falhas == [], c["nome"]


def test_cartoes_titulares_e_suplentes():
    lista = ce.cartoes(amostra("estadual_ce_deputados")["lista"])
    assert lista[0] == {"id": "agenor-neto", "nome": "Agenor Neto", "foto": "https://www.al.ce.gov.br/image/389109",
                        "partido": "MDB", "titular": True}
    assert [d["titular"] for d in lista] == [True, True, True, False, False]


def test_ficha():
    dados = ce.ficha(amostra("estadual_ce_deputados")["ficha"])
    assert dados == {"nomeCivil": "Agenor Gomes de Araújo Neto", "email": "gabdepagenor.neto@al.ce.gov.br"}


def test_ligar_ignora_pontos():
    ligados = ce.ligar(["DEP AGENOR NETO", "AP. LUIZ HENRIQUE", "DRA.SILVANA", "Gulherme Landim"], DEPUTADOS)
    assert ligados == {"DEP AGENOR NETO": "agenor-neto", "AP. LUIZ HENRIQUE": "ap-luiz-henrique", "DRA.SILVANA": "dra-silvana"}


def test_vdp_itens():
    linhas = ce.linhas_csv(amostra("estadual_ce_vdp")["csv"], "DEPUTADO")
    ligacao = ce.ligar({linha["DEPUTADO"] for linha in linhas}, DEPUTADOS)
    itens, sem_par = ce.itens_vdp(linhas, ligacao, "http://fonte")
    assert itens[0]["idDeputado"] == "agenor-neto" and itens[0]["mes"] == 10 and itens[0]["valor"] == 4000.0
    assert itens[0]["categoria"] == "Alimentação e refeição" and itens[0]["cnpj"] == "47866934000174" and itens[0]["fonte"] == "http://fonte"
    assert sem_par == set() or "AGENOR NETO" not in sem_par


def test_vdp_sem_par_e_cabecalho_sem_dados():
    itens, sem_par = ce.itens_vdp([{"DEPUTADO": "DEP FULANO", "PERIODO": "10/2026", "VALOR": "1,00"}], {}, "f")
    assert itens == [] and sem_par == {"FULANO"}
    assert ce.linhas_csv(";;;\nDEPUTADO;PERIODO;EMPENHO;DESCRICAO;CNPJ;CREDOR;VALOR\n", "DEPUTADO") == []


def test_remuneracao_so_deputados():
    linhas = ce.linhas_csv(amostra("estadual_ce_pessoal")["csv"], "NOME")
    ligacao = ce.ligar({linha["NOME"] for linha in linhas}, DEPUTADOS)
    itens, _ = ce.itens_remuneracao(linhas, ligacao, 2026, 9)
    assert itens[0]["idDeputado"] == "agenor-neto" and itens[0]["bruto"] == 39993.14 and itens[0]["liquido"] == 30621.93
    assert itens[0]["componentes"]["descontosLegais"] == 9371.21 and itens[0]["mes"] == 9
    assert itens[0]["fonte"].endswith("pessoal?mes=09&ano=2026")


def test_diarias():
    linhas = ce.linhas_csv(amostra("estadual_ce_diarias")["csv"], "BENEFICIARIO")
    nome = linhas[0]["BENEFICIARIO"]
    itens, sem_par = ce.itens_diarias(linhas, {nome: "agenor-neto"}, 2026)
    assert itens[0]["idDeputado"] == "agenor-neto" and itens[0]["data"] == "2026-10-19" and itens[0]["valor"] == 360.0
    assert nome not in sem_par and len(sem_par) == len({linha["BENEFICIARIO"] for linha in linhas}) - 1


def test_votacoes_da_pagina():
    lista = ce.votacoes_da_pagina(amostra("estadual_ce_votacoes_lista")["html"] + "</td></tr>")
    assert lista[0]["data"] == "2026-07-14" and lista[0]["sessao"].startswith("63")
    assert lista[0]["xlsx"].endswith(".xlsx") and lista[0]["pdf"].endswith(".pdf") and lista[0]["id"] in lista[0]["xlsx"]


def test_votacao_do_xlsx():
    dados = ce.votacao_do_xlsx(amostra("estadual_ce_votacao_xlsx")["linhas"])
    assert dados["data"] == "2026-07-14" and dados["aprovada"] is True and dados["tipo"] == "PL"
    assert (dados["numero"], dados["ano"]) == ("69", 2026)
    assert dados["apuracao"] == {"sim": "23", "nao": "6", "abstencao": "1"}
    assert ("LARISSA GASPAR", "PT", "não") in dados["votos"] and ("DE ASSIS DINIZ", "PT", "sim") in dados["votos"]
    assert all(nome != "ROMEU ALDIGUERI" for nome, _, _ in dados["votos"])


def test_votacao_data_com_espacos():
    linhas = [{"A": "Presidente: X   Data: 03 /03/2026   Horário: 12:18"}, {"A": "Processo: NOMINAL   Resultado: REJEITADO"},
              {"A": "MATÉRIA - 03/2026 - Projeto de Lei Complementar oriundo da Mensagem"},
              {"A": "1", "B": "AGENOR NETO", "C": "MDB", "E": "NÃO (V)"}]
    dados = ce.votacao_do_xlsx(linhas)
    assert dados["data"] == "2026-03-03" and dados["aprovada"] is False and dados["tipo"] == "PLC"
    assert ce.votacao_do_xlsx(linhas[:3]) is None


@pytest.mark.parametrize("texto,esperado", [
    ("AUTORIA: DEPUTADO BRUNO PEDROSA, COAUTORIA: DEPUTADO SIMÃO PEDRO", ["BRUNO PEDROSA", "SIMÃO PEDRO"]),
    ("Autoria: Deputado Danniel Oliveira.", ["Danniel Oliveira"]),
    ("ALMIR BIE COAUTORIA SÉRGIO AGUIAR", ["ALMIR BIE", "SÉRGIO AGUIAR"]),
    ("DRA. SILVANA", ["DRA. SILVANA"]),
    ("A / B E C", ["A", "B", "C"]),
])
def test_autores(texto, esperado):
    assert ce.autores(texto) == esperado


def test_proposicoes_da_pagina():
    html = amostra("estadual_ce_proposicoes")["html"]
    assert ce.ultima_pagina(html) > 1
    itens = ce.proposicoes_da_pagina(html)
    assert itens[0]["numero"] == 2 and itens[0]["ano"] == 2023 and itens[0]["autor"] == "LEONARDO PINHEIRO"
    assert itens[0]["dataApresentacao"] == "2023-02-02" and itens[0]["situacao"] == "Lei 18.393"
    assert itens[0]["linkTexto"].endswith("pl2_23.htm")


def test_tipo_da_materia():
    assert ce.tipo_da_materia("Projeto de Lei Complementar oriundo da Mensagem")[0] == "PLC"
    assert ce.tipo_da_materia("Proposta de Emenda à Constituição n.º 1")[0] == "PEC"
    assert ce.tipo_da_materia("algo sem tipo") == ("MAT", None)


class Resposta:
    def __init__(self, conteudo):
        self.content = conteudo.encode("utf-8") if isinstance(conteudo, str) else conteudo

    def raise_for_status(self):
        pass


class SessaoFalsa:
    def __init__(self, paginas):
        self.paginas = paginas

    def get(self, url, timeout=None):
        return Resposta(self.paginas[url])


def test_coletar_deputados_grava_no_formato_comum(tmp_path, monkeypatch):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    amostras = amostra("estadual_ce_deputados")
    paginas = {ce.LISTA_URL: amostras["lista"]}
    for d in ce.cartoes(amostras["lista"]):
        paginas[f"{ce.SITE}/deputados/{d['id']}"] = amostras["ficha"]
    deputados = ce.coletar_deputados(SessaoFalsa(paginas))
    gravado = json.loads((tmp_path / "deputados.json").read_text(encoding="utf-8"))
    assert gravado["host"] is None and gravado["fonte"] == ce.LISTA_URL and len(gravado["deputados"]) == len(deputados) == 5
    primeiro = gravado["deputados"][0]
    assert primeiro["id"] == "agenor-neto" and primeiro["nomeCivil"] == "Agenor Gomes de Araújo Neto" and primeiro["fonte"].endswith("/deputados/agenor-neto")
    assert identidades.ligar_nomes(["DEP AGENOR NETO"], gravado["deputados"]) == {"DEP AGENOR NETO": "agenor-neto"}


def test_coletar_votacoes_grava_votos_ligados(tmp_path, monkeypatch):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    lista_html = amostra("estadual_ce_votacoes_lista")["html"] + "</td></tr>"
    primeira = ce.votacoes_da_pagina(lista_html)[0]
    monkeypatch.setattr(ce.comum, "xlsx_linhas", lambda conteudo: amostra("estadual_ce_votacao_xlsx")["linhas"])
    s = SessaoFalsa({ce.VOTACOES_URL: lista_html, **{v["xlsx"]: b"x" for v in ce.votacoes_da_pagina(lista_html)}})
    ce.coletar_votacoes(s, DEPUTADOS)
    votacoes = json.loads((tmp_path / "votacoes.json").read_text(encoding="utf-8"))["votacoes"]
    v = votacoes[primeira["id"]]
    assert v["sim"] == 23 and v["nao"] == 6 and v["abstencoes"] == 1 and v["aprovada"] is True and v["fonte"] == primeira["pdf"]
    assert ["larissa-gaspar", "não"] in v["votos"] and ["jeova-mota", "sim"] in v["votos"]
    materias = json.loads((tmp_path / "materias_votadas.json").read_text(encoding="utf-8"))
    assert materias[primeira["id"]]["tipo"] == "PL" and materias[primeira["id"]]["numero"] == "69"
