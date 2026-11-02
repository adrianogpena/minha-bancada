import io
import json
import zipfile
from datetime import date

import pytest

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
).encode()


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
    xml = (b"<despesas><despesa><Ano>2025</Ano><Matricula>300607</Matricula><Mes>3</Mes><Valor>9200.0</Valor><CNPJ>00192198000152</CNPJ>"
           b"<Deputado>Danilo</Deputado><Tipo>D - MATERIAIS</Tipo><Fornecedor>GRAFICA  PARATODOS</Fornecedor></despesa>"
           b"<despesa><Ano>2025</Ano><Matricula>999</Matricula><Mes>3</Mes><Valor>1.0</Valor><CNPJ>1</CNPJ><Deputado>X</Deputado><Tipo>A</Tipo>"
           b"<Fornecedor>F</Fornecedor></despesa></despesas>")
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


MATRICULAS = {"300396", "300631"}


def detalhe_norma(**mudancas):
    base = {"idProcesso": 1000671453, "descricao": "Projeto de Lei 1.332/2025", "resumo": "Declara de utilidade pública a Associação X.", "transformadoNorma": True,
            "urlNorma": "/norma/212580", "descricaoNorma": "Lei nº 18.462, de 11/05/2026",
            "autores": [{"matricula": 300396, "nome": "VALDOMIRO LOPES"}, {"matricula": None, "nome": "Governador"}]}
    return {**base, **mudancas}


def test_normas_do_contrato():
    assert sp._conferir_normas(amostra("normas")) == ([], [])


def test_norma_do_detalhe_liga_autor_pela_matricula():
    nid, norma = sp.norma_do_detalhe(detalhe_norma(), MATRICULAS)
    assert nid == "212580" and norma["idsDeputados"] == ["300396"]
    assert (norma["tipo"], norma["numero"], norma["ano"], norma["data"]) == ("Lei", 18462, 2026, "2026-05-11")
    assert norma["fonte"] == "https://www.al.sp.gov.br/norma/212580" and norma["linkProjeto"].endswith("?id=1000671453")


def test_norma_do_detalhe_tipos_e_casos_sem_deputado():
    _, lc = sp.norma_do_detalhe(detalhe_norma(descricaoNorma="Lei Complementar nº 1.418, de 26/12/2024", urlNorma="/norma/210419"), MATRICULAS)
    assert (lc["tipo"], lc["numero"], lc["ano"]) == ("Lei Complementar", 1418, 2024)
    assert sp.norma_do_detalhe(detalhe_norma(), {"1"}) is None
    assert sp.norma_do_detalhe(detalhe_norma(transformadoNorma=False), MATRICULAS) is None
    assert sp.norma_do_detalhe(detalhe_norma(urlNorma=None, descricaoNorma=None), MATRICULAS) is None


def test_precisa_do_detalhe_so_para_deputado_ou_varios_autores():
    assert sp.precisa_do_detalhe({"tipoAutorPrincipal": "Parlamentar", "numeroAutorPrincipal": 300396}, MATRICULAS)
    assert sp.precisa_do_detalhe({"tipoAutorPrincipal": "varios", "numeroAutorPrincipal": 1}, MATRICULAS)
    assert not sp.precisa_do_detalhe({"tipoAutorPrincipal": "Pessoa", "numeroAutorPrincipal": 105}, MATRICULAS)


def test_coletar_normas_le_so_o_que_falta(tmp_path, monkeypatch):
    monkeypatch.setattr(sp, "PASTA", tmp_path)
    candidatas = {1: {"idProcesso": 1, "tipoProcesso": "PL", "anoTipo": 2025, "numeroTipo": 1}}
    lidos = []

    def detalhe(s, caminho, **params):
        lidos.append(caminho)
        return detalhe_norma(idProcesso=1)

    monkeypatch.setattr(sp, "normas_candidatas", lambda s, matriculas, anos: candidatas)
    monkeypatch.setattr(sp, "pegar_json", detalhe)
    sp.coletar_normas(None, [{"id": "300396"}], date(2026, 11, 2))
    assert lidos == ["/processo/detalhes/todos/PL/2025/1"]
    assert list(json.loads((tmp_path / "normas_2026.json").read_text(encoding="utf-8"))["normas"]) == ["212580"]
    candidatas[2] = {"idProcesso": 2, "tipoProcesso": "PL", "anoTipo": 2025, "numeroTipo": 2}
    lidos.clear()
    sp.coletar_normas(None, [{"id": "300396"}], date(2026, 11, 3))
    assert lidos == ["/processo/detalhes/todos/PL/2025/2"]


def test_sessoes_do_contrato():
    assert sp._conferir_sessoes(amostra("sessoes")) == ([], [])


def test_ler_sessao_pede_so_o_que_existe(monkeypatch):
    chamadas = []
    registro = amostra("sessoes")

    def falso(s, caminho, **params):
        chamadas.append(caminho.rsplit("/", 1)[1])
        return {"pauta": registro["pauta"], "ordem-do-dia": registro["ordemDoDia"], "integra": registro["integra"]}[chamadas[-1]]

    monkeypatch.setattr(sp, "pegar_json", falso)
    itens = sp.ler_sessao(None, {**registro["sessao"], "temOrdemDoDia": False})
    assert chamadas == ["pauta", "integra"]
    assert sorted(i["tipo"] for i in itens) == ["atas", "ordem-do-dia"]
    assert sp.ler_sessao(None, {**registro["sessao"], "temPauta": False, "temOrdemDoDia": False, "temIntegra": False}) == []


def test_reunioes_do_contrato():
    assert sp._conferir_reunioes(amostra("reunioes")) == ([], [])


def test_itens_comissoes_so_documento_com_arquivo():
    reuniao = {"idReuniao": 5, "nuReuniao": 7, "tituloReuniao": "Reunião de Pauta", "dtReuniao": "2026-11-04T15:00", "status": {"txNome": "Convocada"},
               "colegiadosRelacionados": [{"sigla": "CCJR", "nome": "Comissão de Constituição"}],
               "documentosReuniao": [{"idDocumento": 11, "tipo": "Pauta de colegiado", "descricao": "Pauta nº 8/2026", "linkArquivo": "https://x/p.html", "linkArquivoPDF": None},
                                     {"idDocumento": 12, "tipo": "Ata de Reunião de Comissão", "descricao": "Ata", "linkArquivo": None, "linkArquivoPDF": None},
                                     {"idDocumento": 13, "tipo": "Comunicado de colegiado", "descricao": "Comunicado", "linkArquivo": "https://x/c.docx"}]}
    itens = sp.itens_comissoes([reuniao])
    assert [(i["id"], i["tipo"], i["data"], i["titulo"], i["fonte"]) for i in itens] == [("11", "ordem-do-dia", "2026-11-04", "CCJR - Reunião de Pauta nº 7", "https://x/p.html")]


def test_pautas_e_atas_so_relem_o_recente(tmp_path, monkeypatch):
    monkeypatch.setattr(sp, "PASTA", tmp_path)
    sessoes = [{"id": 1, "titulo": "1ª Sessão", "dtInicio": "2026-09-01T14:00"}, {"id": 2, "titulo": "2ª Sessão", "dtInicio": "2026-10-30T14:00"}]
    lidas = []

    def paginas(s, caminho, **params):
        return iter(sessoes if caminho.startswith("/sessoes") and params["ano"] == 2026 else [])

    def ler(s, sessao):
        lidas.append(sessao["id"])
        return [{"id": str(sessao["id"]), "reuniao": f"s{sessao['id']}", "origem": "plenario", "tipo": "atas", "titulo": sessao["titulo"], "data": sessao["dtInicio"][:10],
                 "arquivos": [], "fonte": "https://x"}]

    monkeypatch.setattr(sp, "paginas", paginas)
    monkeypatch.setattr(sp, "ler_sessao", ler)
    sp.coletar_pautas_atas(None, date(2026, 11, 2))
    assert sorted(lidas) == [1, 2]
    lidas.clear()
    sp.coletar_pautas_atas(None, date(2026, 11, 3))
    assert lidas == [2]
    assert set(json.loads((tmp_path / "pautas_2026.json").read_text(encoding="utf-8"))["itens"]) == {"atas|1", "atas|2"}


def test_pautas_e_atas_ano_encerrado_nao_e_lido(tmp_path, monkeypatch):
    monkeypatch.setattr(sp, "PASTA", tmp_path)
    (tmp_path / "pautas_2023.json").write_text('{"itens":{"atas|9":{"origem":"plenario","tipo":"atas","id":"9"}},"lidas":{"9":"2024-01-01"},"falhas":{}}', encoding="utf-8")
    anos = []
    monkeypatch.setattr(sp, "paginas", lambda s, caminho, **params: anos.append(params["ano"]) or iter([]))
    sp.coletar_pautas_atas(None, date(2026, 11, 2))
    assert 2023 not in anos and set(anos) == {2024, 2025, 2026}
    assert "atas|9" in json.loads((tmp_path / "pautas_2023.json").read_text(encoding="utf-8"))["itens"]


def test_contratos_do_contrato():
    assert sp._conferir_contratos(amostra("contratos")) == ([], [])


def test_parse_listagem_separa_tipo_encerrado_e_aditamento():
    pagina = (
        '<div class="modulo_atas" style="display: none"><li class="card"><a href="/alesp/contratos/detalhe/?detContrato=' + "a" * 32 + '"> 1. <strong>Processo Digital 188 / 2026</strong></a>'
        '<b class="badge badge-secondary">Pregão para Registro de Preço</b><i style="color: #666">Leite &amp; derivados</i>'
        '<a href="https://www.al.sp.gov.br/repositorio/contratos/188-2026 ATA Leite.pdf">pdf</a>'
        '<ul class="tree"><li><a href="/alesp/contratos/detalhe/?detContrato=' + "b" * 32 + '"><strong>Processo Digital 188 / 2026 - 1º Aditamento</strong></a></li></ul></div>'
        '<div class="modulo_contratos_encerrado" style="display: none"><li class="card"><a href="/alesp/contratos/detalhe/?detContrato=' + "c" * 32 + '">'
        '<strong>Processo Digital 7 / 2021</strong></a><b class="badge">Pregão</b><i style="color: #666">Obra</i></div>'
        '<div id="blocoConvenio"><li class="card"><a href="https://www.al.sp.gov.br/alesp/convenio/?idContrato=1"><strong>Processo 1 / 2025</strong></a></div>'
    )
    a, c = sp.parse_listagem(pagina)
    assert (a["modulo"], a["encerrado"], a["numero"], a["ano"], a["aditamentos"], a["objeto"]) == ("atas", False, 188, 2026, 1, "Leite & derivados")
    assert a["pdf"] == "https://www.al.sp.gov.br/repositorio/contratos/188-2026%20ATA%20Leite.pdf" and a["modalidade"] == "Pregão para Registro de Preço"
    assert (c["modulo"], c["encerrado"], c["ano"], c["pdf"]) == ("contratos", True, 2021, None)


def detalhe_html(contratada="MADARP LTDA. - 54.456.948/0001-85", valor="R$ 67.200,00"):
    linhas = {"PROCESSO": "144 / 2026", "CONTRATADA": contratada, "OBJETO": "Locação de contêineres", "MODALIDADE": "Pregão", "VIG&Ecirc;NCIA": "de 17/08/2026 a 30/06/2027",
              "VALOR TOTAL": valor, "ASSINATURA": "14/08/2026", "No. DO EMPENHO": "2026NE00712"}
    corpo = "".join(f"<tr><td><b>{k}</b></td><td><font>{v}</font></td></tr>" for k, v in linhas.items())
    corpo += '<tr><td><b>DOCUMENTOS</b></td><td><a href="https://www.al.sp.gov.br/repositorio/contratos/144-2026 Contrato.pdf"></a></td></tr>'
    return f'<table class="tabela"><tbody>{corpo}</tbody></table><h6>Informações Financeiras</h6><table><tr><td>1</td><td>2</td></tr></table>'


def test_item_contrato_separa_cnpj_valor_e_vigencia():
    lista = {"hash": "a" * 32, "numero": 144, "ano": 2026, "modulo": "contratos", "encerrado": False, "modalidade": "Pregão", "objeto": "x", "pdf": None, "aditamentos": 0}
    iid, item = sp.item_contrato(lista, sp.parse_detalhe(detalhe_html()))
    assert iid.startswith("ctr_") and item["tipo"] == "contrato" and item["cnpj"] == "54456948000185" and item["fornecedor"] == "MADARP LTDA."
    assert (item["valor"], item["inicio"], item["fim"], item["assinatura"], item["numero"]) == (67200.0, "2026-08-17", "2027-06-30", "2026-08-14", "144/2026")
    assert item["arquivos"][0]["url"].endswith("144-2026%20Contrato.pdf") and item["fonte"].endswith("detContrato=" + "a" * 32)
    ata = sp.item_contrato({**lista, "modulo": "atas"}, sp.parse_detalhe(detalhe_html(valor="Sem Valor Registrado")))[1]
    assert ata["tipo"] == "ata_registro" and ata["valor"] is None
    assert sp.item_contrato(lista, sp.parse_detalhe(detalhe_html(contratada="JOAO DA SILVA")))[1]["cnpj"] is None


class RespostaFalsa:
    def __init__(self, conteudo):
        self.content = conteudo

    def raise_for_status(self):
        pass


def test_coletar_contratos_incremental(tmp_path, monkeypatch):
    monkeypatch.setattr(sp, "PASTA", tmp_path)
    monkeypatch.setattr(sp.time, "sleep", lambda x: None)
    cartao = ('<li class="card"><a href="/alesp/contratos/detalhe/?detContrato={h}"><strong>Processo Digital {n} / 2026</strong></a>'
              '<b class="badge">Pregão</b><i style="color: #666">Obj {n}</i>')
    pagina = {"texto": '<div class="modulo_contratos" style="display: none">' + cartao.format(h="a" * 32, n=1) + "</div>"}
    pedidos = []

    class Sessao:
        def get(self, url, timeout):
            pedidos.append(url[-32:])
            return RespostaFalsa(detalhe_html().encode("latin-1"))

    monkeypatch.setattr(sp, "baixar", lambda s, url: pagina["texto"].encode("latin-1"))
    sp.coletar_contratos(Sessao(), date(2026, 11, 2))
    assert pedidos == ["a" * 32]
    pedidos.clear()
    pagina["texto"] = '<div class="modulo_contratos" style="display: none">' + cartao.format(h="a" * 32, n=1) + cartao.format(h="b" * 32, n=2) + "</div>"
    sp.coletar_contratos(Sessao(), date(2026, 11, 3))
    assert pedidos == ["b" * 32]
    itens = json.loads((tmp_path / "orgao_2026.json").read_text(encoding="utf-8"))["itens"]
    assert len(itens) == 2 and {i["idFonte"] for i in itens.values()} == {"a" * 32, "b" * 32}


def test_coletar_contratos_pagina_vazia_nao_apaga_arquivo(tmp_path, monkeypatch):
    monkeypatch.setattr(sp, "PASTA", tmp_path)
    monkeypatch.setattr(sp, "baixar", lambda s, url: b"<html></html>")
    (tmp_path / "orgao_2026.json").write_text('{"itens":{"ctr_x":{"idFonte":"z"}},"lidos":{}}', encoding="utf-8")
    with pytest.raises(RuntimeError):
        sp.coletar_contratos(None, date(2026, 11, 2))
    assert "ctr_x" in json.loads((tmp_path / "orgao_2026.json").read_text(encoding="utf-8"))["itens"]


def test_regras_do_contrato():
    assert sp._conferir_regras(amostra("regras")) == ([], [])
    regra = sp.regras_da_verba(amostra("regras")["trecho"])
    assert [d["ano"] for d in regra["documentos"]] == [2002, 2001, 2002] and regra["ano"] == 2002
    assert regra["documentos"][0]["url"] == "https://www.al.sp.gov.br/norma/?id=234"
    assert sp.regras_da_verba("<p>sem links</p>") is None
