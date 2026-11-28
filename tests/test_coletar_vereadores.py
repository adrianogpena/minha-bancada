import zipfile
from io import BytesIO

import coletar_vereadores as v

PE = [
    {"UnidadeJurisdicionadaTCE": "100", "NomeUJ": "Câmara Municipal de Afogados da Ingazeira", "CPFServidor": "***.212.314-**", "NomeServidor": "JOSE LIMA",
     "Matricula": "1", "NomeCargo": "VEREADOR", "NomeTipoVinculo": "Eletivo", "DataIngresso": "2025-01-01"},
    {"UnidadeJurisdicionadaTCE": "100", "NomeUJ": "Câmara Municipal de Afogados da Ingazeira", "CPFServidor": "***.111.222-**", "NomeServidor": "ANA SUPLENTE",
     "Matricula": "9", "NomeCargo": "VEREADOR(A)", "NomeTipoVinculo": "Eletivo", "DataIngresso": "2025-06-10", "DataAfastamento": "2026-03-01"},
    {"UnidadeJurisdicionadaTCE": "100", "NomeUJ": "Câmara Municipal de Afogados da Ingazeira", "CPFServidor": "***.212.314-**", "NomeServidor": "JOSE LIMA",
     "Matricula": "1", "NomeCargo": "VEREADOR", "NomeTipoVinculo": "Eletivo", "DataIngresso": "2021-01-01", "DataAfastamento": "2024-12-31"},
    {"UnidadeJurisdicionadaTCE": "100", "NomeUJ": "Câmara Municipal de Afogados da Ingazeira", "NomeServidor": "FULANO", "NomeCargo": "ASSESSOR DE VEREADOR",
     "NomeTipoVinculo": "Comissionado", "DataIngresso": "2025-02-01"},
]


def test_itens_pe_filtra_eletivos_e_legislatura_atual():
    itens = v.itens_pe(PE)
    assert [(i["nome"], i["ingresso"], i["afastamento"]) for i in itens] == [("JOSE LIMA", "2025-01-01", None), ("ANA SUPLENTE", "2025-06-10", "2026-03-01")]
    assert {i["municipio"] for i in itens} == {"Afogados da Ingazeira"}
    assert {i["cargo"] for i in itens} == {"VEREADOR"}


def test_cpf_mascarado_nunca_guarda_cpf_inteiro():
    assert v.cpf_mascarado("123.456.789-09") == "***.456.789-**"
    assert v.cpf_mascarado("12345678909") == "***.456.789-**"
    assert v.cpf_mascarado("***.212.314-**") == "***.212.314-**"
    assert v.cpf_mascarado("123") is None


def test_iso_aceita_iso_e_br():
    assert v.iso("2025-01-01T00:00:00") == "2025-01-01"
    assert v.iso("01/01/2025") == "2025-01-01"
    assert v.iso("") is None


CSV_PB = ("nome_municipio;codigo_unidade_gestora;descricao_unidade_gestora;cpf_cnpj;nome_servidor;tipo_cargo;descricao_cargo;valor_vantagem;data_admissao;matricula;ano_mes\n"
          "Agua Branca;101001;Câmara Municipal de Água Branca;12345678909;MARIA A;Eletivos;00000001 - VEREADOR;6.000;01/01/2025;56;202601\n"
          "Agua Branca;101001;Câmara Municipal de Água Branca;12345678909;MARIA A;Eletivos;00000001 - VEREADOR;6.000;01/01/2025;56;202602\n"
          "Agua Branca;101001;Câmara Municipal de Água Branca;98765432100;JOAO B;Eletivos;00000002 - VEREADOR PRESIDENTE;6.000;01/01/2025;57;202601\n"
          "Agua Branca;101001;Câmara Municipal de Água Branca;11111111111;SECRETARIA C;Comissionado;ASSESSOR;1.000;01/03/2025;58;202601\n")


def zip_csv(texto: str) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("servidores-2026.csv", "﻿" + texto)
    return buf.getvalue()


def test_pb_so_vereadores_e_agrega_por_matricula():
    linhas = v.linhas_vereador_pb(zip_csv(CSV_PB))
    assert len(linhas) == 3
    itens = v.itens_pb(linhas)
    por_nome = {i["nome"]: i for i in itens}
    assert set(por_nome) == {"MARIA A", "JOAO B"}
    assert (por_nome["MARIA A"]["primeiroMes"], por_nome["MARIA A"]["ultimoMes"], por_nome["MARIA A"]["ingresso"]) == ("2026-01", "2026-02", "2025-01-01")
    assert por_nome["MARIA A"]["cpf"] == "***.456.789-**"


def test_mandatos_pb_deriva_afastamento_de_quem_sumiu_da_folha():
    itens = v.itens_pb(v.linhas_vereador_pb(zip_csv(CSV_PB)))
    ms = {m["nome"]: m for m in v.mandatos_pb([itens])}
    assert ms["MARIA A"]["afastamento"] is None
    assert ms["JOAO B"]["afastamento"] == "2026-01-31"


def test_mandatos_pb_junta_anos():
    a = [{"municipio": "X", "unidade": "1", "nome": "N", "cpf": None, "cargo": "VEREADOR", "matricula": "5", "ingresso": "2025-01-01",
          "primeiroMes": "2025-01", "ultimoMes": "2025-12"}]
    b = [{**a[0], "ingresso": "2025-01-01", "primeiroMes": "2026-01", "ultimoMes": "2026-10"}]
    m = v.mandatos_pb([a, b])
    assert len(m) == 1 and (m[0]["primeiroMes"], m[0]["ultimoMes"], m[0]["afastamento"]) == ("2025-01", "2026-10", None)


def test_codigos_pb_le_listagem_s3():
    xml = ('<?xml version="1.0"?><ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><IsTruncated>true</IsTruncated>'
           "<NextContinuationToken>abc</NextContinuationToken><CommonPrefixes><Prefix>dados-por-municipio/001/</Prefix></CommonPrefixes>"
           "<CommonPrefixes><Prefix>dados-por-municipio/002/</Prefix></CommonPrefixes></ListBucketResult>")
    assert v.codigos_pb(xml) == (["001", "002"], "abc")


def test_municipio_da_camara_formas_do_tce():
    assert v.municipio_da_camara("Câmara Municipal de Afogados da Ingazeira") == "Afogados da Ingazeira"
    assert v.municipio_da_camara("Vereadores de Custódia") == "Custódia"
    assert v.municipio_da_camara("Vereadores dos Palmares") == "Palmares"
    assert v.municipio_da_camara("Câmara de Vereadores da Cidade do Paulista") == "Paulista"
