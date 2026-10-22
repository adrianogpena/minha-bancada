import json
from datetime import date

import coletar_estadual_pe as pe
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"

LISTA = [
    {"id": "4508", "nome": "Abimael Santos", "partido": "PL", "email": "abimael.santos@alepe.pe.gov.br", "foto": ""},
    {"id": "4496", "nome": "João Paulo", "partido": "PT", "email": "joao.paulo@alepe.pe.gov.br", "foto": "/imagens/deputados/joaopaulo.jpg"},
    {"id": "4497", "nome": "João Paulo Costa", "partido": "PC Do B", "email": None, "foto": ""},
    {"id": "4514", "nome": "Gilmar Junior", "partido": "PV", "email": "gilmar.junior@alepe.pe.gov.br", "foto": ""},
    {"id": "5", "nome": "Adelmo Duarte", "partido": "DEM", "email": None, "foto": ""},
]
PARLAMENTARES = [
    {"nomeParlamentar": "Abimael Santos", "partido": "PL"},
    {"nomeParlamentar": "João Paulo do PT", "partido": "PT"},
    {"nomeParlamentar": "Gilmar Júnior", "partido": "PV"},
    {"nomeParlamentar": "Cayo Albino", "partido": "PSB"},
]


def amostra(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


def test_montar_deputados_so_em_exercicio_e_sem_id_para_quem_nao_esta_na_lista():
    deputados = pe.montar_deputados(LISTA, PARLAMENTARES)
    assert [d["id"] for d in deputados] == ["4508", "4496", "4514", "sem-cayo-albino"]
    joao = deputados[1]
    assert joao["nome"] == "João Paulo do PT" and joao["foto"] == "https://www.alepe.pe.gov.br/imagens/deputados/joaopaulo.jpg"
    assert deputados[0]["foto"] is None and deputados[0]["email"] == "abimael.santos@alepe.pe.gov.br"
    assert deputados[3]["fonte"] == pe.PARLAMENTARES_URL


def test_ligar_tira_o_partido_do_nome_do_autor():
    deputados = pe.montar_deputados(LISTA, PARLAMENTARES)
    ligados = pe.ligar(["João Paulo do PT", "João Paulo Costa", "Fulano do PT"], deputados)
    assert ligados == {"João Paulo do PT": "4496"}


def test_deputados_do_contrato():
    assert pe._conferir_deputados(amostra("estadual_pe_deputados")) == ([], [])


def test_itens_verba_com_fornecedor_e_tipo():
    lancamento = {"docid": "7561", "numero": "77", "tipo": "P", "total": "44880"}
    notas = [{"rubrica": 3, "data": "30/01/2026", "cnpj": "47006999000140", "empresa": "Alysson Advocacia", "valor": "21880"}]
    itens = pe.itens_verba(lancamento, notas, "4508", 2026, 1, {3: "ASSESSORIA JURÍDICA"})
    assert itens == [{"idDeputado": "4508", "mes": 1, "categoria": "ASSESSORIA JURÍDICA", "fornecedor": "Alysson Advocacia", "cnpj": "47006999000140",
                      "valor": 21880.0, "data": "2026-01-30", "tipo": "Pedido", "numero": "77", "docid": "7561", "fonte": pe.VERBA_PAGINA}]


def test_itens_verba_sem_notas_usa_o_total():
    itens = pe.itens_verba({"docid": "1", "numero": "2", "tipo": "C", "total": "15000"}, [], "4508", 2026, 1, {})
    assert itens[0]["valor"] == 15000.0 and itens[0]["tipo"] == "Complemento" and itens[0]["fornecedor"] is None


def test_verba_do_contrato():
    a = amostra("estadual_pe_verba")
    assert pe._conferir_verba(a) == ([], [])
    l, n = a["lancamentos"][0], a["notas"]
    itens = pe.itens_verba(l, n, "4508", a["ano"], 1, {r["numero_categoria"]: r["nome_categoria"] for r in a["rubricas"]})
    assert itens[0]["categoria"] == "ASSESSORIA JURÍDICA" and itens[0]["data"] == "2025-01-31" and itens[0]["cnpj"] == "47006999000140"


def test_recentes():
    assert pe.recentes(date(2026, 1, 10)) == {(2026, 1), (2025, 12)}


def test_proposicoes_do_contrato():
    for tipo in pe.TIPOS_PROPOSICAO:
        a = amostra(f"estadual_pe_{tipo}")
        assert pe._conferir_proposicoes(tipo)(a) == ([], [])


def test_materias_liga_autor_e_corta_ementa():
    xml = ("<projetos><projeto docid='16370' numero='33' ano='2026' tipo='PROPOSTA DE EMENDA A CONSTITUIÇÃO' subtipo='' "
           "ementa='&lt;p&gt;Altera &amp;aacute; Constituição.&lt;/p&gt;' dataPublicacao='31/03/2026'>"
           "<autores><autor nome='João Paulo do PT' tipo='DEPUTADO'/><autor nome='Comissão' tipo='COMISSAO'/></autores></projeto>"
           "<projeto docid='1' numero='1' ano='2026' tipo='X' subtipo='' ementa='a' dataPublicacao='01/01/2026'><autores><autor nome='Outro' tipo='DEPUTADO'/></autores></projeto>"
           "</projetos>")
    props = pe.parse_proposicoes(xml.encode("utf-8"), "projetos")
    assert props[0]["ementa"] == "Altera á Constituição." and props[0]["autores"] == ["João Paulo do PT"]
    achadas = pe.materias(props, {"João Paulo do PT": "4496"}, "projetos")
    assert list(achadas) == ["projetos-16370"]
    m = achadas["projetos-16370"]
    assert m["idsDeputados"] == ["4496"] and m["dataApresentacao"] == "2026-03-31" and m["numero"] == 33 and m["tipo"] == "PROJ"
    assert m["fonte"] == pe.PROPOSICOES_PAGINA
    longa = [{**props[0], "ementa": "palavra " * 100}]
    assert pe.materias(longa, {"João Paulo do PT": "4496"}, "projetos")["projetos-16370"]["ementa"].endswith("...")
