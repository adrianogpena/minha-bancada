import json

import coletar_estadual_ms as ms
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"

DEPUTADOS = [
    {"id": "1", "nome": "Roberto Hashioka", "nomeCivil": "Roberto Hashioka Soler"},
    {"id": "2", "nome": "Coronel David", "nomeCivil": "Carlos Alberto David dos Santos"},
    {"id": "3", "nome": "Pedrossian Neto", "nomeCivil": "Pedro Pedrossian Neto"},
    {"id": "4", "nome": "Zeca do Pt", "nomeCivil": "José Orcírio Miranda dos Santos"},
]


def amostra(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


def test_contratos_registrados():
    assert [c["nome"] for c in ms.CONTRATOS] == ["estadual_ms_ceap", "estadual_ms_diarias"]
    for c in ms.CONTRATOS:
        falhas, _ = c["html"](amostra(c["nome"]))
        assert falhas == [], c["nome"]


def test_ligar_apelidos_e_prefixo_sem_espaco():
    nomes = ["DEP. HASHIOKA", "Dep. Cel. David", "Dep.Pedrossian Neto", "Dep. Zeca do PT", "Dep. Fulano"]
    assert ms.ligar(nomes, DEPUTADOS) == {"DEP. HASHIOKA": "1", "Dep. Cel. David": "2", "Dep.Pedrossian Neto": "3", "Dep. Zeca do PT": "4"}


def test_linhas_csv_pula_metadados():
    linhas = ms.linhas_csv(amostra("estadual_ms_ceap")["csv"], "DEPUTADO")
    assert linhas and linhas[0]["DEPUTADO"] == "DEP. HASHIOKA" and "VALOR (R$)" in linhas[0]


def test_itens_ceap():
    linhas = ms.linhas_csv(amostra("estadual_ms_ceap")["csv"], "DEPUTADO")
    ligacao = ms.ligar({l["DEPUTADO"] for l in linhas}, DEPUTADOS)
    itens, sem_par = ms.itens_ceap(linhas, ligacao, "http://pagina")
    assert itens[0]["idDeputado"] == "1" and itens[0]["mes"] == 1 and itens[0]["valor"] == 99.9
    assert itens[0]["cnpj"] == "16551514000175" and itens[0]["emissao"] == "2026-01-10"
    assert itens[0]["fonte"].startswith("http://www.transparencia.al.ms.gov.br/arquivo/") and itens[0]["fonte"].endswith(".pdf")
    assert sem_par == set()


def test_sem_par_e_sem_comprovante():
    itens, sem_par = ms.itens_ceap([{"DEPUTADO": "Dep. Fulano", "VALOR (R$)": "R$ 1,00"},
                                    {"DEPUTADO": "DEP. HASHIOKA", "MES": "Março", "VALOR (R$)": "R$ 1.000,50", "COMPROVANTE": ""}],
                                   {"DEP. HASHIOKA": "1"}, "http://pagina")
    assert sem_par == {"Fulano"}
    assert itens == [{"idDeputado": "1", "mes": 3, "categoria": None, "fornecedor": None, "cnpj": None, "valor": 1000.5,
                      "documento": None, "emissao": None, "fonte": "http://pagina"}]


def test_diarias_sem_despesa():
    assert ms.linhas_diarias(amostra("estadual_ms_diarias")["csv"]) == []
    texto = "Mês;Ano;Informação\nJaneiro;2024;Viagem a Brasília\nFevereiro;2024;\"Não houve despesa com a concessão de diárias nesse período.\"\n"
    assert [l["MES"] for l in ms.linhas_diarias(texto)] == ["Janeiro"]


def test_emissao_iso():
    assert ms.emissao_iso("10/01/2026") == "2026-01-10"
    assert ms.emissao_iso("") is None
