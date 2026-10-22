import io
import json
import zipfile
from datetime import date

import coletar_estadual_sp as sp
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"

XML_DEPUTADOS = (
    "<Deputados>"
    "<Deputado><IdSPL>1000000335</IdSPL><Situacao>EXE</Situacao><Email>balas@al.sp.gov.br</Email><Matricula>300607</Matricula>"
    "<NomeParlamentar>Agente Federal Danilo Balas</NomeParlamentar><Partido>PL</Partido></Deputado>"
    "<Deputado><IdSPL>1000000340</IdSPL><Situacao>EXE</Situacao><Email></Email><Matricula>300001</Matricula>"
    "<NomeParlamentar>Letícia Aguiar</NomeParlamentar><Partido>PP</Partido></Deputado>"
    "<Deputado><IdSPL>9</IdSPL><Situacao>LIC</Situacao><Matricula>300002</Matricula><NomeParlamentar>Fora</NomeParlamentar><Partido>PT</Partido></Deputado>"
    "</Deputados>"
).encode("utf-8")


def amostra(nome):
    return json.loads((FIX / f"estadual_sp_{nome}.json").read_text(encoding="utf-8"))["amostra"]


def zip_de(nome, xml):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(nome, xml)
    return buf.getvalue()


def test_parse_deputados_so_em_exercicio():
    deputados = sp.parse_deputados(XML_DEPUTADOS)
    assert [d["id"] for d in deputados] == ["300607", "300001"]
    assert deputados[0]["idAutor"] == "1000000335" and deputados[0]["email"] == "balas@al.sp.gov.br" and deputados[1]["email"] is None
    assert deputados[0]["fonte"] == "https://www.al.sp.gov.br/deputado/?matricula=300607"


def test_deputados_do_contrato():
    assert sp._conferir_deputados(amostra("deputados")) == ([], [])


def test_fotos_montam_a_url_do_portal():
    assert sp.fotos([{"nuMatricula": 300607, "txFoto": "/biografia/fotos/300607/a.jpeg"}, {"nuMatricula": 1, "txFoto": None}]) == {
        "300607": "https://www3.al.sp.gov.br/legis/biografia/fotos/300607/a.jpeg"}


def test_ligar_civis_ignora_titulo_e_exige_par_unico():
    deputados = [{"id": "1", "nome": "Agente Federal Danilo Balas"}, {"id": "2", "nome": "Carlos Silva"}, {"id": "3", "nome": "Ana Costa"},
                 {"id": "4", "nome": "Ana Costa Lima"}]
    civis = ["DANILO MASCARENHAS DE BALAS", "CARLOS EDUARDO SILVA", "CARLOS ALBERTO SILVA", "ANA COSTA LIMA"]
    assert sp.ligar_civis(civis, deputados) == {"DANILO MASCARENHAS DE BALAS": "1"}


def test_ligar_civis_pelo_tse_usa_nome_de_urna():
    deputados = [{"id": "5", "nome": "Beth Sahão"}]
    candidatos = [{"urna": "BETH SAHAO", "nome": "ELISABETH SAHAO"}, {"urna": "OUTRA", "nome": "MARIA"}]
    assert sp.ligar_civis_pelo_tse(["ELISABETH SAHAO", "MARIA"], deputados, candidatos) == {"ELISABETH SAHAO": "5"}


def test_proposituras_e_autores_viram_materias_por_ano():
    xml = ("<proposituras>"
           "<propositura><AnoLegislativo>2025</AnoLegislativo><Ementa>Institui  a política.</Ementa><DtPublicacao>2025-02-03T00:00:00-03:00</DtPublicacao>"
           "<IdDocumento>100</IdDocumento><IdNatureza>1</IdNatureza><NroLegislativo>12</NroLegislativo></propositura>"
           "<propositura><AnoLegislativo>2025</AnoLegislativo><Ementa>Requer.</Ementa><DtPublicacao>2025-02-03T00:00:00-03:00</DtPublicacao>"
           "<IdDocumento>101</IdDocumento><IdNatureza>7</IdNatureza><NroLegislativo>1</NroLegislativo></propositura>"
           "<propositura><AnoLegislativo>2020</AnoLegislativo><Ementa>Antiga.</Ementa><DtPublicacao>2020-02-03T00:00:00-03:00</DtPublicacao>"
           "<IdDocumento>102</IdDocumento><IdNatureza>1</IdNatureza><NroLegislativo>3</NroLegislativo></propositura>"
           "<propositura><AnoLegislativo>2025</AnoLegislativo><Ementa>Sem deputado.</Ementa><DtPublicacao>2025-03-03T00:00:00-03:00</DtPublicacao>"
           "<IdDocumento>103</IdDocumento><IdNatureza>2</IdNatureza><NroLegislativo>4</NroLegislativo></propositura>"
           "</proposituras>")
    proposituras = sp.ler_proposituras(zip_de("proposituras.xml", xml), 2023)
    assert sorted(proposituras) == ["100", "103"]
    autores_xml = ("<documentos_autores>"
                   "<DocumentoAutor><IdAutor>1000000335</IdAutor><IdDocumento>100</IdDocumento><NomeAutor>Agente Federal Danilo Balas</NomeAutor></DocumentoAutor>"
                   "<DocumentoAutor><IdAutor>77</IdAutor><IdDocumento>100</IdDocumento><NomeAutor>Letícia  Aguiar</NomeAutor></DocumentoAutor>"
                   "<DocumentoAutor><IdAutor>105</IdAutor><IdDocumento>103</IdDocumento><NomeAutor>Governador</NomeAutor></DocumentoAutor>"
                   "<DocumentoAutor><IdAutor>1</IdAutor><IdDocumento>999</IdDocumento><NomeAutor>Outro</NomeAutor></DocumentoAutor>"
                   "</documentos_autores>")
    autores = sp.ler_autores(zip_de("documento_autor.xml", autores_xml), proposituras)
    assert sorted(autores) == ["100", "103"]
    anos = sp.materias_por_ano(proposituras, autores, sp.parse_deputados(XML_DEPUTADOS))
    assert list(anos) == [2025] and list(anos[2025]) == ["100"]
    m = anos[2025]["100"]
    assert m["idsDeputados"] == ["300001", "300607"] and m["tipo"] == "PL" and m["numero"] == 12 and m["ementa"] == "Institui a política."
    assert m["dataApresentacao"] == "2025-02-03" and m["fonte"] == "https://www.al.sp.gov.br/propositura/?id=100"


def test_proposituras_do_contrato():
    assert sp._conferir_proposituras(amostra("proposituras")) == ([], [])


def test_itens_verba_so_dos_deputados_em_exercicio():
    xml = ("<despesas><despesa><Ano>2025</Ano><Matricula>300607</Matricula><Mes>3</Mes><Valor>9200.0</Valor><CNPJ>00192198000152</CNPJ>"
           "<Deputado>Danilo</Deputado><Tipo>D - MATERIAIS</Tipo><Fornecedor>GRAFICA  PARATODOS</Fornecedor></despesa>"
           "<despesa><Ano>2025</Ano><Matricula>999</Matricula><Mes>3</Mes><Valor>1.0</Valor><CNPJ>1</CNPJ><Deputado>X</Deputado><Tipo>A</Tipo>"
           "<Fornecedor>F</Fornecedor></despesa></despesas>").encode("utf-8")
    itens = sp.itens_verba(xml, {"300607": "300607"})
    assert itens == [{"idDeputado": "300607", "mes": 3, "categoria": "D - MATERIAIS", "fornecedor": "GRAFICA PARATODOS", "cnpj": "00192198000152",
                      "valor": 9200.0, "fonte": sp.DESPESAS_PAGINA}]


def test_verba_do_contrato():
    assert sp._conferir_verba(amostra("verba")) == ([], [])


def test_folha_do_contrato():
    registro = amostra("folha")
    assert sp._conferir_folha(registro) == ([], [])
    linhas = sp.parse_folha(registro["linhas"])
    assert linhas[0]["bruto"] == 34774.64 and linhas[0]["liquido"] == linhas[0]["bruto"] - linhas[0]["tributos"]
    assert sp.meses_da_folha('href=".../folha-deputados-2026-08.html" href=".../folha-deputados-2025-12.html"') == [(2025, 12), (2026, 8)]


def test_itens_folha_liga_pelo_nome_civil():
    linhas = [{"nome": "DANILO MASCARENHAS DE BALAS", "bruto": 34774.64, "tributos": 9000.0, "liquido": 25774.64},
              {"nome": "SEM PAR", "bruto": 1.0, "tributos": 0.0, "liquido": 1.0}]
    itens = sp.itens_folha(linhas, {"DANILO MASCARENHAS DE BALAS": "300607"}, 2026, 8)
    assert itens == [{"idDeputado": "300607", "mes": 8, "bruto": 34774.64, "liquido": 25774.64, "componentes": {"Tributos": 9000.0},
                      "fonte": "https://www.al.sp.gov.br/repositorio/folha-de-pagamento/folha-deputados-2026-08.html"}]


def test_contar_presenca_separa_presente_licenca_e_ausente():
    registros = [{"situacao": "Presente"}, {"situacao": "Justificada"}, {"situacao": "Licença-Saúde"}, {"situacao": "Não Justificada"},
                 {"situacao": "Ausência em Sessão Extraordinária"}, {"situacao": "Sessão não Deliberativa - com quórum regimental para abertura da sessão"}]
    assert sp.contar_presenca(registros) == [1, 2, 2]


def test_itens_presenca_soma_o_ano():
    itens = sp.itens_presenca({("300607", "2026-01"): [3, 1, 0], ("300607", "2026-02"): [2, 0, 1]})
    por_periodo = {i["periodo"]: i for i in itens}
    assert set(por_periodo) == {"2026-01", "2026-02", "2026"}
    ano = por_periodo["2026"]
    assert (ano["presente"], ano["licenca"], ano["ausente"], ano["totalSessoes"]) == (5, 1, 1, 7)


def test_presenca_do_contrato():
    assert sp._conferir_presenca(amostra("presenca")) == ([], [])


def test_presenca_do_ano_so_busca_o_que_falta(monkeypatch):
    chamadas = []

    def falso(sessao, matricula, mes, ano):
        chamadas.append((matricula, mes))
        return [{"situacao": "Presente"}]

    monkeypatch.setattr(sp, "presenca_do_mes", falso)
    existentes = [{"idDeputado": "1", "periodo": f"2026-0{m}", "presente": 9, "licenca": 0, "ausente": 0} for m in (1, 2, 3)]
    itens = sp.presenca_do_ano(None, [{"id": "1"}], 2026, existentes, date(2026, 4, 10))
    assert sorted(chamadas) == [("1", 3), ("1", 4)]
    por_periodo = {i["periodo"]: i for i in itens}
    assert por_periodo["2026-01"]["presente"] == 9 and por_periodo["2026-03"]["presente"] == 1 and por_periodo["2026"]["presente"] == 9 + 9 + 1 + 1
