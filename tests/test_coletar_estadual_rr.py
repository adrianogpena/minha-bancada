import json
import zipfile
from datetime import date
from io import BytesIO

import pytest

import coletar_estadual_rr as rr
import estaduais_comum as comum
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"

DEPUTADOS = [
    {"id": "angela", "nome": "Angela Águida Portella", "nomeCivil": "Angela Águida Portella Alves"},
    {"id": "joilma", "nome": "Joilma Teodora", "nomeCivil": "Joilma Teodora de Araújo Silva"},
    {"id": "marcos", "nome": "Marcos Jorge", "nomeCivil": "Marcos Jorge de Lima"},
]

NS_TABELA = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
NS_TEXTO = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"


def amostra(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


def odt(linhas):
    corpo = "".join("<table:table-row>" + "".join(f"<table:table-cell><text:p>{c}</text:p></table:table-cell>" for c in linha) + "</table:table-row>" for linha in linhas)
    xml = (f'<?xml version="1.0"?><office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:table="{NS_TABELA}" '
           f'xmlns:text="{NS_TEXTO}"><office:body><office:text><table:table>{corpo}</table:table></office:text></office:body></office:document-content>')
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("content.xml", xml)
    return buf.getvalue()


def xlsx(linhas):
    strings, celulas = [], []
    for n, linha in enumerate(linhas, 1):
        cs = ""
        for i, v in enumerate(linha):
            if v == "":
                continue
            strings.append(v)
            cs += f'<c r="{chr(65 + i)}{n}" t="s"><v>{len(strings) - 1}</v></c>'
        celulas.append(f'<row r="{n}">{cs}</row>')
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/sharedStrings.xml", f'<sst xmlns="{ns}">' + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{ns}"><sheetData>{"".join(celulas)}</sheetData></worksheet>')
    return buf.getvalue()


def test_cartoes_e_ficha_do_contrato():
    a = amostra("estadual_rr_deputados")
    cartoes = rr.cartoes(a["lista"])
    assert len(cartoes) == 3 and cartoes[0]["url"] == f"{rr.SITE}/deputados/{cartoes[0]['slug']}/" and cartoes[0]["foto"].startswith("https://")
    ficha = rr.parse_ficha(a["ficha"])
    assert ficha["nome"] and ficha["nomeCivil"].startswith(ficha["nome"].split()[0]) and ficha["partido"] and "@" in ficha["email"]
    assert rr._conferir_deputados(a) == ([], [])


def test_entradas_da_listagem_do_contrato():
    a = amostra("estadual_rr_listagem")
    pastas, _ = rr.entradas(a["raiz"])
    assert [n for n, _ in pastas] == ["Ano 2025", "Ano 2026"]
    _, arquivos = rr.entradas(a["pasta"])
    assert {x["tipo"] for x in arquivos} == {"odt", "pdf"} and all("&#038;" not in x["url"] and "wpdf_download" in x["url"] for x in arquivos)
    assert rr._conferir_listagem(a) == ([], [])


def test_numero_do_mes_e_ano_da_pasta():
    assert rr.numero_do_mes("01 - Janeiro de 2026") == 1
    assert rr.numero_do_mes("09-Setembro de 2025") == 9
    assert rr.numero_do_mes("04- Abril de 2026") == 4
    assert rr.numero_do_mes("Março") == 3
    assert rr.ano_da_pasta("Ano 2026") == 2026


def test_nome_do_arquivo():
    assert rr.nome_do_arquivo("Dep. Angela Aguida Portela Alves -Janeiro 2026.odt") == "Angela Aguida Portela Alves"
    assert rr.nome_do_arquivo("Dep.Tayla Ribeiro Peres Silva - Janeiro 2026.pdf") == "Tayla Ribeiro Peres Silva"
    assert rr.nome_do_arquivo("RESUMO GERAL.pdf") is None


def test_parse_verba_do_contrato():
    a = amostra("estadual_rr_verba")
    itens = rr.parse_verba(a["linhas"])
    assert itens and all(i["valor"] > 0 and i["grupo"] for i in itens)
    assert {i["item"]: i["categoria"] for i in itens}["4.1"] == "Consultoria e assessoria de imprensa"
    assert rr._conferir_verba(a) == ([], [])


def test_linhas_odf_le_tabela_e_ignora_linhas_vazias():
    conteudo = odt([["ITEM", "DESCRICAO", "VALOR"], ["4.1", "Consultoria", "5.000,00"], ["", ""]])
    assert rr.linhas_odf(conteudo) == [["ITEM", "DESCRICAO", "VALOR"], ["4.1", "Consultoria", "5.000,00"]]


def test_itens_verba_liga_por_nome_e_usa_pdf_como_fonte():
    modelo = [["ITEM", "DESCRICAO", "VALOR"], ["4.1", "x", "5.000,00"], ["4.2", "y", ""], ["6.1", "z", "7.500,00"]]
    arquivos = [{"nome": "Dep. Angela Aguida Portela Alves -Janeiro 2026.odt", "tipo": "odt", "url": "http://x/a.odt"},
                {"nome": "Dep. Angela Aguida Portela Alves -Janeiro 2026.pdf", "tipo": "pdf", "url": "http://x/a.pdf"},
                {"nome": "Dep. Desconhecido Fulano - Janeiro 2026.odt", "tipo": "odt", "url": "http://x/d.odt"}]
    baixados = []

    def baixar(url):
        baixados.append(url)
        return odt(modelo)

    itens = rr.itens_verba(arquivos, baixar, DEPUTADOS, 2026, 1)
    assert baixados == ["http://x/a.odt"]
    assert [(i["idDeputado"], i["mes"], i["item"], i["valor"], i["fonte"]) for i in itens] == [
        ("angela", 1, "4.1", 5000.0, "http://x/a.pdf"), ("angela", 1, "6.1", 7500.0, "http://x/a.pdf")]
    assert itens[0]["categoria"] == "Consultoria e assessoria de imprensa" and itens[0]["fornecedor"] is None


def test_periodo_para_datas():
    assert rr.periodo_para_datas("25/02 A 01/03/2026") == ("2026-02-25", "2026-03-01")
    assert rr.periodo_para_datas("17 A 20/07/26") == ("2026-07-17", "2026-07-20")
    assert rr.periodo_para_datas("15 E 16/6/2026") == ("2026-06-15", "2026-06-16")
    assert rr.periodo_para_datas("46197") == ("2026-06-24", "2026-06-24")
    assert rr.periodo_para_datas("30 A 02/03/2026") == (None, "2026-03-02")
    assert rr.periodo_para_datas("sem data") == (None, None)


def test_registros_e_itens_de_diarias_do_contrato():
    a = amostra("estadual_rr_diarias")
    registros = rr.registros_diarias(a["linhas"])
    assert registros and all(r["valor"] for r in registros)
    itens = rr.itens_diarias(registros, DEPUTADOS, "http://fonte")
    assert {i["idDeputado"] for i in itens} <= {"joilma", "marcos"} and itens
    assert all(i["data"] and i["fonte"] == "http://fonte" for i in itens)
    assert rr._conferir_diarias(a) == ([], [])


def test_registros_diarias_so_de_deputados():
    linhas = [["MAT", "NOME", "CARGO", "DESTINO", "FINALIDADE", "PERÍODO", "PGTO", "VALOR"],
              ["1", "JOILMA TEODORA DE ARAUJO SILVA", "DEPUTADA", "BRASÍLIA- DF", "REUNIAO", "05/02/2026", "45720", "1250"],
              ["2", "FULANO", "SG- I SUP. GERAL", "BRASÍLIA- DF", "VISITA", "05/02/2026", "45720", "800"]]
    registros = rr.registros_diarias(linhas)
    assert [r["nome"] for r in registros] == ["JOILMA TEODORA DE ARAUJO SILVA"]
    assert rr.registros_diarias([["x"]]) == []


def test_linhas_xlsx_preenche_colunas_vazias():
    linhas = rr.linhas_xlsx(xlsx([["MAT", "NOME", "CARGO"], ["1", "", "DEPUTADO"]]))
    assert linhas == [["MAT", "NOME", "CARGO"], ["1", "", "DEPUTADO"]]


def test_ligar_usa_primeiro_e_ultimo_nome():
    assert rr.ligar(["Angela Aguida Portela Alves", "Marcos Jorge de Lima", "Alguem Qualquer"], DEPUTADOS) == {
        "Angela Aguida Portela Alves": "angela", "Marcos Jorge de Lima": "marcos"}


def test_coletar_grava_deputados_verbas_e_diarias(tmp_path, monkeypatch):
    hoje = date.today()
    ano = hoje.year
    verba = odt([["ITEM", "DESCRICAO", "VALOR"], ["4.1", "x", "5.000,00"]])
    planilha = xlsx([["NOME", "CARGO", "DESTINO", "FINALIDADE", "PERÍODO", "VALOR"],
                     ["JOILMA TEODORA DE ARAUJO SILVA", "DEPUTADA", "BRASÍLIA- DF", "REUNIAO", f"05/02/{ano}", "1250"]])
    ficha = ('<title>Joilma Teodora | ALE-RR</title><h1>Joilma Teodora</h1><meta property="og:description" content="Nome: Joilma Teodora de Araújo Silva '
             'Data de Nascimento: 01-01 Partido: PP Gabinete: 1 e-mail: j@al.rr.leg.br" /><a href="mailto:j@al.rr.leg.br">')
    lista = (f'<a href="{rr.SITE}/deputados/joilma/" target="_self"><img src="https://al.rr.leg.br/f.jpg" />')

    def pagina_arquivos(ano_pasta, sid):
        return f'<script>var wpdf_obj = {{"wpdf_nonce":"abc"}};</script><div data-sid="{sid}"></div><li data-type="folder" data-name="{ano_pasta}" data-path="{ano_pasta}/"></li>'

    pastas = {f"Ano {ano}/": f'<li data-type="folder" data-name="02-Fevereiro" data-path="Ano {ano}/02-Fevereiro/"></li>'}
    arquivos_verba = (f'<li class="file_record" data-name="Dep. Joilma Teodora de Araujo Silva - Fevereiro {ano}.odt" data-file-type="odt"><a href="http://x/v.odt?wpdf_download=true&#038;i=1"></a></li>'
                      f'<li class="file_record" data-name="Dep. Joilma Teodora de Araujo Silva - Fevereiro {ano}.pdf" data-file-type="pdf"><a href="http://x/v.pdf?wpdf_download=true&#038;i=2"></a></li>')
    arquivos_diaria = '<li class="file_record" data-name="DEMONSTRATIVO FEV.xlsx" data-file-type="xlsx"><a href="http://x/d.xlsx?wpdf_download=true"></a></li>'

    class Resp:
        def __init__(self, texto=None, conteudo=None, dados=None):
            self.text, self.content, self._dados = texto, conteudo, dados

        def raise_for_status(self):
            pass

        def json(self):
            return self._dados

    class Sessao:
        def get(self, url, timeout=None):
            if url == rr.LISTA_DEPUTADOS:
                return Resp(texto=lista)
            if url.endswith("/deputados/joilma/"):
                return Resp(texto=ficha)
            if url == rr.VERBAS_PAGINA:
                return Resp(texto=pagina_arquivos(f"Ano {ano}", "9"))
            if url == rr.DIARIAS_PAGINA:
                return Resp(texto=pagina_arquivos(f"Ano {ano}", "8"))
            if url.startswith("http://x/v.odt"):
                return Resp(conteudo=verba)
            if url.startswith("http://x/d.xlsx"):
                return Resp(conteudo=planilha)
            raise AssertionError(url)

        def post(self, url, data=None, timeout=None):
            caminho = data["folder_path"]
            if caminho == f"Ano {ano}/":
                return Resp(dados={"inner_content": pastas[caminho]})
            return Resp(dados={"inner_content": arquivos_verba if data["sid"] == "9" else arquivos_diaria})

    sessao = Sessao()
    monkeypatch.setattr(comum, "DADOS", tmp_path)
    monkeypatch.setattr(comum, "sessao", lambda: sessao)
    rr.coletar()
    pasta = tmp_path / "RR"
    deps = json.loads((pasta / "deputados.json").read_text(encoding="utf-8"))
    assert deps["host"] is None and deps["deputados"][0]["nome"] == "Joilma Teodora" and deps["deputados"][0]["partido"] == "PP"
    verbas = json.loads((pasta / f"verbas_{ano}.json").read_text(encoding="utf-8"))
    assert verbas["mesesColetados"] == [2] and verbas["itens"][0]["idDeputado"] == "joilma" and verbas["itens"][0]["valor"] == 5000.0
    assert verbas["itens"][0]["fonte"] == "http://x/v.pdf?wpdf_download=true&i=2"
    diarias = json.loads((pasta / f"diarias_{ano}.json").read_text(encoding="utf-8"))
    assert diarias["itens"][0]["data"] == f"{ano}-02-05" and diarias["itens"][0]["valor"] == 1250.0


CAB_PESSOAL = ["Matrícula", "Nome", "Desc. Vínculo", "Dt. Admissão", "Cargo", "Função", "Setor", "Unidade"]


def test_gabinete_do_contrato():
    a = amostra("estadual_rr_gabinete")
    assert rr._conferir_gabinete(a) == ([], [])


def test_servidores_do_gabinete_liga_ao_deputado_e_ignora_outros_setores():
    linhas = [CAB_PESSOAL,
              ["36499", "ABADI JONATHAN ALMEIDA", "COMISSIONADOS", "01/04/2026", "FS-11 Secretario Parlamentar ", "x", "GAB. DEP. JOILMA TEODORA", "DEP. JOILMA TEODORA"],
              ["36499", "ABADI JONATHAN ALMEIDA", "COMISSIONADOS", "01/04/2026", "FS-11 Secretario Parlamentar ", "x", "GAB. DEP. JOILMA TEODORA", "DEP. JOILMA TEODORA"],
              ["3416252", "ABRAAO DE CASTELO", "ADIDOS/ CEDIDOS/REMOVIDOS", "13/08/2024", "MOTORISTA", "MOTORISTA", "GAB. DEP. MARCOS JORGE", "DEP. MARCOS JORGE"],
              ["10", "FULANO", "COMISSIONADOS", "01/01/2026", "FS-1 Chefe", "x", "GAB. DEP. SEM PAR NENHUM", "x"],
              ["11", "CICLANO", "COMISSIONADOS", "01/01/2026", "FS-1 Chefe", "x", "GABINETE DA PRESIDENCIA ", "x"]]
    itens = rr.servidores_do_gabinete(linhas, DEPUTADOS)
    assert [(i["idDeputado"], i["matricula"], i["nome"], i["simbolo"], i["cargo"], i["admissao"]) for i in itens] == [
        ("joilma", "36499", "Abadi Jonathan Almeida", "FS-11", "Secretario Parlamentar", "2026-04-01"),
        ("marcos", "3416252", "Abraao de Castelo", None, "MOTORISTA", "2024-08-13")]
    assert itens[0]["id"].startswith("srv_") and itens[0]["id"] == rr.servidores_do_gabinete(linhas[:2], DEPUTADOS)[0]["id"]
    assert rr.servidores_do_gabinete([["x"]], DEPUTADOS) == []


def arq(nome):
    return {"nome": nome, "tipo": "pdf", "url": f"http://x/{nome}"}


def test_contratos_do_contrato():
    a = amostra("estadual_rr_contratos")
    assert rr._conferir_contratos(a) == ([], [])


def test_contratos_da_pasta_um_por_numero_com_links_e_sem_fornecedor():
    pasta = "Processo Eletrônico nº 97-2024"
    arquivos = [arq("CONTRATO 11-2025.pdf"), arq("CONTRATO 11-2025 PUBLICACAO DO CONTRATO.pdf"), arq("CONTRATO 12-2025.pdf"),
                arq("PRIMEIRO TERMO ADITIVO CONTRATO 12-2025.pdf"), arq("PUBLICAÇÃO DO CONTRATO 83-2025.pdf")]
    itens = rr.contratos_da_pasta(pasta, arquivos, "http://fonte")
    por_numero = {i["numero"]: i for i in itens.values()}
    assert sorted(por_numero) == ["11/2025", "12/2025"] and all(k.startswith("ctr_") for k in itens)
    assert [x["nome"] for x in por_numero["11/2025"]["arquivos"]] == ["Contrato", "Publicação: contrato"]
    assert [x["nome"] for x in por_numero["12/2025"]["arquivos"]] == ["Contrato", "Termo aditivo"]
    assert por_numero["11/2025"]["processo"] == "97/2024" and por_numero["11/2025"]["fornecedor"] is None and por_numero["11/2025"]["tipo"] == "contrato"
    assert rr.contratos_da_pasta(pasta, arquivos, "http://fonte") == itens


def test_contratos_da_pasta_publicacao_com_numero_de_processo_vai_para_o_unico_contrato_e_empenho_nao_gera_item():
    unico = rr.contratos_da_pasta("Processo Eletrônico nº 83-2025", [arq("CONTRATO 23-2025.pdf"), arq("PUBLICACAO DO CONTRATO 83-2025.pdf")], "f")
    assert [len(i["arquivos"]) for i in unico.values()] == [2]
    assert rr.contratos_da_pasta("Processo Eletrônico nº 51-2026", [arq("EMPENHO 767-2026.pdf")], "f") == {}


def test_licitacoes_do_contrato():
    a = amostra("estadual_rr_licitacoes")
    assert rr._conferir_licitacoes(a) == ([], [])


def test_itens_licitacoes_colunas_pelo_cabecalho():
    licitacoes = [["LICITAÇÕES - 2026"], ["SETEMBRO"],
                  ["Nº DO PROCESSO", "Nº DO EDITAL", "MODALIDADE/ FORMA/ PROCEDIMENTO", "OBJETO", "DESPESA MÁXIMA ACEITÁVEL / VALOR ESTIMADO",
                   "VENCEDOR (ES)", "DATA", "VALOR HOMOLOGADO", "SITUAÇÃO"],
                  ["18/2025", "90014/2025", "PREGÃO ELETRÔNICO", "Conexão de dados", "5007156.84", "LOTE ÚNICO: GRZ LTDA CNPJ: 07.872.397/0001-50", "46044", "2770116", "HOMOLOGADO"],
                  ["22/2025", "90003/2025", "PREGÃO ELETRÔNICO", "Outsourcing", "7585200", "DOALE ED.Nº 4724", "46288", "-", "ABERTO"],
                  ["Fonte da informação: SCP"]]
    itens = rr.itens_licitacoes(licitacoes, "licitacao", "http://pdf", 9)
    assert len(itens) == 2 and all(k.startswith("lic_") for k in itens)
    homologada, aberta = sorted(itens.values(), key=lambda i: i["processo"])
    assert (homologada["cnpj"], homologada["data"], homologada["valorEstimado"], homologada["valorHomologado"], homologada["edital"]) == (
        "07872397000150", "2026-01-22", 5007156.84, 2770116.0, "90014/2025")
    assert (aberta["vencedor"], aberta["referenciaDiario"], aberta["valorHomologado"], aberta["fonte"]) == (None, "DOALE ED.Nº 4724", None, "http://pdf")


def test_itens_licitacoes_contratacao_direta_distingue_procedimentos_do_mesmo_processo():
    linhas = [["DISPENSAS / INEXIGIBILIDADES"],
              ["PROCEDIMENTO", "PROCESSO", "MODALIDADE/ FORMA/ PROCEDIMENTO", "OBJETO", "VENCEDOR (ES)", "DATA", "VALOR HOMOLOGADO", "SITUAÇÃO"],
              ["001/2024", "23/2024", "DISPENSA ELETRÔNICA", "Materiais", "-", "29/01/2025", "-", "REVOGADA"],
              ["001/2025", "23/2024", "DISPENSA ELETRÔNICA", "Materiais", "-", "45702", "54128.88", "ABERTA"]]
    itens = rr.itens_licitacoes(linhas, "contratacao_direta", "f", 1)
    assert sorted((i["procedimento"], i["data"], i["valorHomologado"]) for i in itens.values()) == [
        ("001/2024", "2025-01-29", None), ("001/2025", "2025-02-14", 54128.88)]
    assert rr.itens_licitacoes([["x"]], "licitacao", "f", 1) == {}


def test_coletar_grava_gabinete_contratos_e_licitacoes(tmp_path, monkeypatch):
    hoje = date.today()
    ano = hoje.year
    pessoal = xlsx([CAB_PESSOAL, ["36499", "ABADI JONATHAN", "COMISSIONADOS", "01/04/2026", "FS-11 Secretario", "x", "GAB. DEP. JOILMA TEODORA", "x"]])
    direta = xlsx([["PROCEDIMENTO", "PROCESSO", "MODALIDADE", "OBJETO", "VENCEDOR (ES)", "DATA", "VALOR HOMOLOGADO", "SITUAÇÃO"],
                   ["001/2026", "271/2025", "DISPENSA", "Limpeza", "NEW SERVICE LTDA", "46036", "4854031.68", "HOMOLOGADA"]])

    def pagina(sid):
        return f'<script>var w = {{"wpdf_nonce":"abc"}};</script><div data-sid="{sid}"></div><li data-type="folder" data-name="Ano {ano}" data-path="Ano {ano}/"></li>'

    def li(nome, tipo, url):
        return f'<li class="file_record" data-name="{nome}" data-file-type="{tipo}"><a href="http://x/{url}?wpdf_download=true"></a></li>'

    mes = f'<li data-type="folder" data-name="3-Março" data-path="Ano {ano}/3-Março/"></li>'
    arquivos = {"7": li("CONSULTA SERVIDORES.xlsx", "xlsx", "p.xlsx"),
                "5": li("CONTRATACOES DIRETAS MARCO.xlsx", "xlsx", "d.xlsx") + li("CONTRATACOES DIRETAS MARCO.pdf", "pdf", "d.pdf")}
    contratos = {f"Ano {ano}/": f'<li data-type="folder" data-name="Processo Eletrônico nº 5-2025" data-path="Ano {ano}/P5/"></li>',
                 f"Ano {ano}/P5/": li("CONTRATO 02-2026.pdf", "pdf", "c.pdf") + li("PUBLICACAO DO CONTRATO 02-2026.pdf", "pdf", "cp.pdf")}
    paginas = {rr.GESTAO_PAGINA: "7", rr.CONTRATOS_PAGINA: "6", rr.LICITACOES_PAGINA: "5"}
    ficha = ('<title>Joilma Teodora | ALE-RR</title><h1>Joilma Teodora</h1><meta property="og:description" content="Nome: Joilma Teodora de Araújo Silva '
             'Data de Nascimento: 01-01 Partido: PP Gabinete: 1 e-mail: j@al.rr.leg.br" />')

    class Resp:
        def __init__(self, texto=None, conteudo=None, dados=None):
            self.text, self.content, self._dados = texto, conteudo, dados

        def raise_for_status(self):
            pass

        def json(self):
            return self._dados

    class Sessao:
        def get(self, url, timeout=None):
            if url == rr.LISTA_DEPUTADOS:
                return Resp(texto=f'<a href="{rr.SITE}/deputados/joilma/" target="_self"><img src="https://al.rr.leg.br/f.jpg" />')
            if url.endswith("/deputados/joilma/"):
                return Resp(texto=ficha)
            if url in paginas:
                return Resp(texto=pagina(paginas[url]))
            if url.startswith("http://x/p.xlsx"):
                return Resp(conteudo=pessoal)
            if url.startswith("http://x/d.xlsx"):
                return Resp(conteudo=direta)
            raise AssertionError(url)

        def post(self, url, data=None, timeout=None):
            caminho, sid = data["folder_path"], data["sid"]
            if sid == "6":
                return Resp(dados={"inner_content": contratos[caminho]})
            if caminho == f"Ano {ano}/":
                return Resp(dados={"inner_content": mes})
            return Resp(dados={"inner_content": arquivos[sid]})

    sessao = Sessao()
    monkeypatch.setattr(comum, "DADOS", tmp_path)
    monkeypatch.setattr(comum, "sessao", lambda: sessao)
    monkeypatch.setattr(rr, "coletar_verbas", lambda *a: None)
    monkeypatch.setattr(rr, "coletar_diarias", lambda *a: None)
    rr.coletar()
    pasta = tmp_path / "RR"
    gabinete = json.loads((pasta / "gabinete.json").read_text(encoding="utf-8"))
    assert gabinete["fonte"] == rr.GESTAO_PAGINA and gabinete["referencia"] == f"{ano}-03"
    assert [(i["idDeputado"], i["matricula"], i["simbolo"]) for i in gabinete["itens"]] == [("joilma", "36499", "FS-11")]
    orgao = json.loads((pasta / f"orgao_{ano}.json").read_text(encoding="utf-8"))
    (contrato,) = orgao["itens"].values()
    assert contrato["numero"] == "02/2026" and contrato["fonte"] == rr.CONTRATOS_PAGINA
    assert [a["nome"] for a in contrato["arquivos"]] == ["Contrato", "Publicação: contrato"]
    licitacoes = json.loads((pasta / f"licitacoes_{ano}.json").read_text(encoding="utf-8"))
    (direta_item,) = licitacoes["itens"].values()
    assert licitacoes["referencia"] == {"contratacao_direta": f"{ano}-03"} and direta_item["fonte"] == "http://x/d.pdf?wpdf_download=true"
    assert direta_item["vencedor"] == "NEW SERVICE LTDA" and direta_item["data"] == "2026-01-14"


class Resposta:
    def __init__(self, texto=None, conteudo=None, dados=None):
        self.text, self.content, self._dados = texto, conteudo, dados

    def raise_for_status(self):
        pass

    def json(self):
        return self._dados


class SessaoArquivos:
    def __init__(self, conteudos=None, paginas=None):
        self.conteudos, self.paginas, self.posts = conteudos or {}, paginas or {}, []

    def get(self, url, timeout=None):
        if url in self.paginas:
            return Resposta(texto=self.paginas[url])
        return Resposta(conteudo=self.conteudos[url])

    def post(self, url, data=None, timeout=None):
        self.posts.append((url, data))
        return Resposta(dados={"inner_content": self.paginas[data["folder_path"]]})


def instalar_listas(monkeypatch, raizes, pastas):
    chamadas = []

    class ListaFalsa:
        def __init__(self, s, pagina):
            self.s, self.raiz = s, raizes[pagina]

        def pasta(self, caminho):
            chamadas.append(caminho)
            return pastas[caminho]

    monkeypatch.setattr(rr, "Lista", ListaFalsa)
    return chamadas


def arquivo(nome, tipo, url=None):
    return {"nome": nome, "tipo": tipo, "url": url or f"http://x/{nome}"}


def test_cartoes_remove_duplicados_e_decodifica_foto():
    html = (f'<a href="{rr.SITE}/deputados/ana-lima/" class="x"><img alt="" src="https://al.rr.leg.br/a.jpg?x=1&#038;y=2" /></a>'
            f'<a href="{rr.SITE}/deputados/ana-lima/"><img src="https://al.rr.leg.br/outra.jpg" /></a>'
            f'<a href="{rr.SITE}/deputados/bia/"><img src="https://al.rr.leg.br/b.jpg" /></a><a href="{rr.SITE}/outra/">x</a>')
    achados = rr.cartoes(html)
    assert [c["slug"] for c in achados] == ["ana-lima", "bia"]
    assert achados[0]["foto"] == "https://al.rr.leg.br/a.jpg?x=1&y=2" and achados[0]["url"] == f"{rr.SITE}/deputados/ana-lima/"
    assert rr.cartoes("") == []


def test_parse_ficha_usa_titulo_sem_h1_e_aceita_ficha_vazia():
    sem_h1 = ('<title>Ana Lima | ALE-RR</title><meta property="og:description" content="Nome: Ana Lima Souza Data de Nascimento: 01 '
              'Partido: Partido Progressista Gabinete: 2 e-mail: a@al.rr.leg.br" />')
    f = rr.parse_ficha(sem_h1)
    assert f["nome"] == "Ana Lima" and f["nomeCivil"] == "Ana Lima Souza" and f["email"] == "a@al.rr.leg.br"
    assert rr.parse_ficha("<html></html>") == {"nome": None, "nomeCivil": None, "partido": None, "email": None}


def test_coletar_deputados_ignora_ficha_sem_nome_e_usa_nome_como_civil():
    lista = (f'<a href="{rr.SITE}/deputados/ana/"><img src="https://al.rr.leg.br/a.jpg" /></a>'
             f'<a href="{rr.SITE}/deputados/vazio/"><img src="https://al.rr.leg.br/v.jpg" /></a>')
    paginas = {rr.LISTA_DEPUTADOS: lista, f"{rr.SITE}/deputados/ana/": "<h1>Ana Lima</h1>", f"{rr.SITE}/deputados/vazio/": "<html></html>"}
    deputados = rr.coletar_deputados(SessaoArquivos(paginas=paginas))
    assert deputados == [{"id": "ana", "nome": "Ana Lima", "nomeCivil": "Ana Lima", "foto": "https://al.rr.leg.br/a.jpg", "email": None,
                          "titular": True, "partido": None, "fonte": f"{rr.SITE}/deputados/ana/"}]


def test_credenciais_e_erro_sem_lista_de_arquivos():
    assert rr.credenciais('x "wpdf_nonce":"ab12" y <div data-sid="42">') == ("ab12", "42")
    with pytest.raises(RuntimeError, match="wpdf_nonce"):
        rr.credenciais('<div data-sid="42">')
    with pytest.raises(RuntimeError):
        rr.credenciais('"wpdf_nonce":"ab12"')


def test_entradas_ignora_arquivo_sem_link_de_download_e_decodifica():
    html = ('<li data-type="folder" data-name="03 - Mar&#231;o" data-path="Ano 2026/03/"></li>'
            '<li class="file_record" data-name="A &amp; B.PDF" data-file-type="PDF"><a href="http://x/a?wpdf_download=1&#038;i=2"></a></li>'
            '<li class="file_record" data-name="sem.pdf" data-file-type="pdf"><a href="http://x/sem.pdf"></a></li>')
    pastas, arquivos = rr.entradas(html)
    assert pastas == [("03 - Março", "Ano 2026/03/")]
    assert arquivos == [{"nome": "A & B.PDF", "tipo": "pdf", "url": "http://x/a?wpdf_download=1&i=2"}]


def test_lista_le_credenciais_raiz_e_posta_a_pasta():
    pagina = ('<script>{"wpdf_nonce":"n1"}</script><div data-sid="4"></div>'
              '<li data-type="folder" data-name="Ano 2026" data-path="Ano 2026/"></li>')
    interno = ('<li data-type="folder" data-name="03-Março" data-path="Ano 2026/03-Março/"></li>'
               '<li class="file_record" data-name="a.odt" data-file-type="odt"><a href="http://x/a?wpdf_download=1"></a></li>')
    sessao = SessaoArquivos(paginas={rr.VERBAS_PAGINA: pagina, "Ano 2026/": interno})
    lista = rr.Lista(sessao, rr.VERBAS_PAGINA)
    assert (lista.nonce, lista.sid, lista.raiz[0]) == ("n1", "4", [("Ano 2026", "Ano 2026/")])
    pastas, arquivos = lista.pasta("Ano 2026/")
    assert pastas == [("03-Março", "Ano 2026/03-Março/")] and arquivos[0]["nome"] == "a.odt"
    url, data = sessao.posts[0]
    assert url == rr.AJAX
    assert data == {"action": "wpdf_load_folder_data", "folder_name": "Ano 2026", "folder_path": "Ano 2026/", "sid": "4", "wpdf_nonce": "n1"}


def test_numero_do_mes_e_ano_da_pasta_invalidos():
    assert rr.numero_do_mes("13 - Mês") is None
    assert rr.numero_do_mes("00 - Zero") is None
    assert rr.numero_do_mes("2026") is None
    assert rr.numero_do_mes("") is None
    assert rr.ano_da_pasta("Contratos") is None
    assert rr.ano_da_pasta("") is None


def test_linhas_odf_colunas_repetidas():
    corpo = ('<table:table-row><table:table-cell table:number-columns-repeated="3"><text:p>x</text:p></table:table-cell>'
             '<table:table-cell table:number-columns-repeated="200"/></table:table-row>'
             '<table:table-row><table:table-cell table:number-columns-repeated="60"><text:p>y</text:p></table:table-cell></table:table-row>'
             '<table:table-row><table:table-cell/><table:table-cell/></table:table-row>')
    xml = (f'<?xml version="1.0"?><office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:table="{NS_TABELA}" '
           f'xmlns:text="{NS_TEXTO}"><office:body><office:text><table:table>{corpo}</table:table></office:text></office:body></office:document-content>')
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("content.xml", xml)
    assert rr.linhas_odf(buf.getvalue()) == [["x", "x", "x", ""], ["y"]]


def test_linhas_planilha_escolhe_leitor_pelo_tipo():
    assert rr.linhas_planilha(xlsx([["A", "B"]]), "xlsx") == [["A", "B"]]
    assert rr.linhas_planilha(odt([["A", "B"]]), "ods") == [["A", "B"]]


def test_parse_verba_ignora_valor_zero_codigo_invalido_e_usa_rotulo_da_fonte():
    linhas = [["4.1", "x", "0,00"], ["TOTAL", "x", "9,00"], ["4.1", "x"], ["9.9", " Item novo ", "10,50"], [" 2.1 ", "x", "1.000,00"]]
    itens = rr.parse_verba(linhas)
    assert [(i["item"], i["categoria"], i["grupo"], i["valor"]) for i in itens] == [
        ("9.9", "Item novo", "Especialização de servidores de gabinete", 10.5), ("2.1", "Aluguel de imóveis", "Manutenção de escritório", 1000.0)]


def test_nome_do_arquivo_sem_ponto_e_sem_nome():
    assert rr.nome_do_arquivo("Dep Fulano de Tal - Maio 2026.odt") == "Fulano de Tal"
    assert rr.nome_do_arquivo("Dep. Fulano - 2026.odt") is None


def test_itens_verba_avisa_nome_sem_deputado_e_ignora_nome_so_com_pdf(capsys):
    arquivos = [arquivo("Dep. Desconhecido Fulano - Janeiro 2026.odt", "odt"), arquivo("Dep. Marcos Jorge de Lima - Janeiro 2026.pdf", "pdf"),
                arquivo("Dep. Angela Aguida Portela Alves - Janeiro 2026.odt", "odt", "http://x/a.odt"), arquivo("RESUMO.pdf", "pdf"),
                arquivo("Dep. Joilma Teodora - Janeiro 2026.xlsx", "xlsx")]
    itens = rr.itens_verba(arquivos, lambda url: odt([["4.1", "x", "100,00"]]), DEPUTADOS, 2026, 1)
    assert [(i["idDeputado"], i["fonte"]) for i in itens] == [("angela", "http://x/a.odt")]
    assert "verba de 'Desconhecido Fulano' não casou" in capsys.readouterr().err


def test_periodo_para_datas_virada_de_mes_e_invalidos():
    assert rr.periodo_para_datas("30 A 02/01/2026") == ("2025-12-30", "2026-01-02")
    assert rr.periodo_para_datas("31 A 02/03/2026") == (None, "2026-03-02")
    assert rr.periodo_para_datas("31/02/2026") == (None, None)
    assert rr.periodo_para_datas("05/02") == (None, None)
    assert rr.periodo_para_datas("05/02/2026") == ("2026-02-05", "2026-02-05")
    assert rr.periodo_para_datas("") == (None, None)
    assert rr.periodo_para_datas(None) == (None, None)
    assert rr.periodo_para_datas("46197.0") == ("2026-06-24", "2026-06-24")
    assert rr.periodo_para_datas("28/12 A 02/01/2026") == ("2025-12-28", "2026-01-02")


def test_registros_diarias_cabecalho_deslocado_e_colunas_faltando():
    linhas = [["Diárias de fevereiro"], ["NOME", "CARGO", "DESTINO"], ["JOILMA", "Deputado(a)", "BRASÍLIA"], ["", "DEPUTADA", "X"], ["ANA", "ASSESSOR", "Y"]]
    assert rr.registros_diarias(linhas) == [{"nome": "JOILMA", "destino": "BRASÍLIA", "motivo": "", "periodo": "", "valor": None}]


def test_itens_diarias_avisa_sem_deputado_e_usa_fim_quando_sem_inicio(capsys):
    registros = [{"nome": "JOILMA TEODORA DE ARAUJO SILVA", "destino": "", "motivo": "", "periodo": "31 A 02/03/2026", "valor": 100.0},
                 {"nome": "FULANO DESCONHECIDO", "destino": "X", "motivo": "Y", "periodo": "05/02/2026", "valor": 1.0}]
    itens = rr.itens_diarias(registros, DEPUTADOS, "http://f")
    assert itens == [{"idDeputado": "joilma", "data": "2026-03-02", "dataFim": "2026-03-02", "destino": None, "motivo": None, "valor": 100.0, "fonte": "http://f"}]
    assert "diária de 'FULANO DESCONHECIDO' não casou" in capsys.readouterr().err


def test_titulo_e_simbolo_do_cargo():
    assert rr.titulo("MARIA DA SILVA E SOUZA") == "Maria da Silva e Souza"
    assert rr.titulo("DE ANA") == "De Ana"
    assert rr.titulo(None) == ""
    assert rr.simbolo_do_cargo("FS-11 Secretario  Parlamentar ") == ("FS-11", "Secretario Parlamentar")
    assert rr.simbolo_do_cargo("MOTORISTA") == (None, "MOTORISTA")
    assert rr.simbolo_do_cargo(None) == (None, None)


def test_servidores_do_gabinete_ignora_linha_sem_matricula_ou_nome_e_ordena():
    gab = "GAB. DEP. JOILMA TEODORA"
    linhas = [CAB_PESSOAL,
              ["", "SEM MATRICULA", "C", "01/04/2026", "FS-1 A", "x", gab, "x"],
              ["5", "", "C", "01/04/2026", "FS-1 A", "x", gab, "x"],
              ["7", "ZE", "C", "01/04/2026", "FS-2 B", "x", gab, "x"],
              ["6", "ANA", "C", "01/04/2026", "FS-1 B", "x", gab, "x"]]
    assert [i["matricula"] for i in rr.servidores_do_gabinete(linhas, DEPUTADOS)] == ["6", "7"]


def test_coletar_gabinete_usa_planilha_do_mes_mais_novo_que_tem_servidores(tmp_path, monkeypatch, capsys):
    pessoal = xlsx([CAB_PESSOAL, ["36499", "ABADI JONATHAN", "COMISSIONADOS", "01/04/2026", "FS-11 Secretario", "x", "GAB. DEP. JOILMA TEODORA", "x"]])
    raizes = {rr.GESTAO_PAGINA: ([("Ano 2026", "G26/")], [])}
    pastas = {"G26/": ([("01 - Janeiro", "G1/"), ("02 - Fevereiro", "G2/")], []),
              "G1/": ([], [arquivo("CONSULTA SERVIDORES.xlsx", "xlsx", "http://x/p.xlsx")]),
              "G2/": ([], [arquivo("Resumo.pdf", "pdf"), arquivo("OUTRA.xlsx", "xlsx")])}
    instalar_listas(monkeypatch, raizes, pastas)
    rr.coletar_gabinete(SessaoArquivos({"http://x/p.xlsx": pessoal}), DEPUTADOS, tmp_path, date(2026, 6, 1))
    grav = json.loads((tmp_path / "gabinete.json").read_text(encoding="utf-8"))
    assert grav["referencia"] == "2026-01" and grav["coletadoEm"] == "2026-06-01" and grav["fonte"] == rr.GESTAO_PAGINA
    assert [i["idDeputado"] for i in grav["itens"]] == ["joilma"]
    assert "gabinetes 1 servidores de 1 deputados (01/2026)" in capsys.readouterr().out


def test_coletar_gabinete_falha_sem_planilha_ou_sem_servidor_ligado(tmp_path, monkeypatch):
    raizes = {rr.GESTAO_PAGINA: ([("Ano 2026", "G26/")], [])}
    pastas = {"G26/": ([("01 - Janeiro", "G1/")], []), "G1/": ([], [arquivo("Resumo.pdf", "pdf")])}
    instalar_listas(monkeypatch, raizes, pastas)
    with pytest.raises(RuntimeError, match="sem planilha"):
        rr.coletar_gabinete(SessaoArquivos(), DEPUTADOS, tmp_path, date(2026, 6, 1))
    pastas["G1/"] = ([], [arquivo("CONSULTA SERVIDORES.xlsx", "xlsx", "http://x/p.xlsx")])
    outro = xlsx([CAB_PESSOAL, ["1", "FULANO", "C", "01/04/2026", "FS-1 A", "x", "GAB. DEP. SEM PAR NENHUM", "x"]])
    with pytest.raises(RuntimeError, match="nenhum servidor"):
        rr.coletar_gabinete(SessaoArquivos({"http://x/p.xlsx": outro}), DEPUTADOS, tmp_path, date(2026, 6, 1))
    assert not (tmp_path / "gabinete.json").exists()


def test_rotulo_do_arquivo():
    assert rr.rotulo_do_arquivo("PRIMEIRO TERMO ADITIVO CONTRATO 12-2025.pdf") == "Termo aditivo"
    assert rr.rotulo_do_arquivo("TERMO DE APOSTILAMENTO 12-2025.pdf") == "Termo de apostilamento"
    assert rr.rotulo_do_arquivo("TERMO DE RERRATIFICAÇÃO.pdf") == "Termo de rerratificação"
    assert rr.rotulo_do_arquivo("CONTRATO 11-2025.pdf") == "Contrato"
    assert rr.rotulo_do_arquivo("EMPENHO 767-2026.pdf") == "Documento"
    assert rr.rotulo_do_arquivo("PUBLICACAO DO ADITIVO.pdf") == "Publicação: termo aditivo"
    assert rr.rotulo_do_arquivo("PUBLICACAO.pdf") == "Publicação: documento"


def test_contratos_da_pasta_documento_de_outro_numero_com_varios_contratos_e_pasta_sem_processo():
    arquivos = [arq("CONTRATO 11-2025.pdf"), arq("CONTRATO 12-2025.pdf"), arq("TERMO ADITIVO CONTRATO 99-2025.pdf"), arq("SOLTO.pdf"),
                arquivo("CONTRATO 13-2025.docx", "docx")]
    itens = rr.contratos_da_pasta("Pasta sem numero", arquivos, "http://fonte")
    assert sorted(i["numero"] for i in itens.values()) == ["11/2025", "12/2025"]
    assert all(len(i["arquivos"]) == 1 and i["processo"] is None for i in itens.values())
    assert rr.contratos_da_pasta("Pasta", [], "f") == {}
    assert rr.contratos_da_pasta("Pasta", [arquivo("CONTRATO 5-2025.docx", "docx")], "f") == {}


def test_contratos_da_pasta_ordena_por_ano_e_numero_e_normaliza_zeros():
    itens = rr.contratos_da_pasta("Processo nº 007-2024", [arq("CONTRATO 0003-2025.pdf"), arq("CONTRATO 10-2024.pdf")], "f")
    assert [i["numero"] for i in itens.values()] == ["10/2024", "03/2025"]
    assert {i["processo"] for i in itens.values()} == {"7/2024"}


def test_coletar_contratos_pula_ano_encerrado_e_pasta_sem_ano_e_avisa_falha_sem_perder_arquivo(tmp_path, monkeypatch, capsys):
    hoje = date(2025, 6, 1)
    (tmp_path / "orgao_2022.json").write_text("{}", encoding="utf-8")
    anterior = {"coletadoEm": "2025-01-01", "fonte": rr.CONTRATOS_PAGINA, "itens": {"ctr_x": {"numero": "1/2025"}}}
    comum.salvar(tmp_path / "orgao_2025.json", anterior)
    raizes = {rr.CONTRATOS_PAGINA: ([("Ano 2022", "C22/"), ("Outros", "CX/"), ("Ano 2025", "C25/"), ("Ano 2024", "C24/")], [])}
    pastas = {"C25/": ([("Processo nº 1-2025", "P1/")], []), "P1/": ([], [arq("EMPENHO 1-2025.pdf")]),
              "C24/": ([("Processo nº 5-2024", "P5/")], []), "P5/": ([], [arq("CONTRATO 02-2024.pdf")])}
    chamadas = instalar_listas(monkeypatch, raizes, pastas)
    rr.coletar_contratos(object(), tmp_path, hoje)
    assert "C22/" not in chamadas and "CX/" not in chamadas
    assert json.loads((tmp_path / "orgao_2025.json").read_text(encoding="utf-8")) == anterior
    assert "RR: contratos 2025: 2025 sem contrato na lista; mantém o arquivo anterior" in capsys.readouterr().err
    novo = json.loads((tmp_path / "orgao_2024.json").read_text(encoding="utf-8"))
    assert [i["numero"] for i in novo["itens"].values()] == ["02/2024"] and novo["coletadoEm"] == "2025-06-01"


def test_contratos_do_ano_sem_contrato_e_sem_arquivo_anterior_grava_vazio(tmp_path, monkeypatch, capsys):
    instalar_listas(monkeypatch, {"p": ([], [])}, {"C25/": ([], [])})
    arq_ano = tmp_path / "orgao_2025.json"
    rr.contratos_do_ano(rr.Lista(None, "p"), "C25/", 2025, arq_ano, date(2025, 6, 1))
    assert json.loads(arq_ano.read_text(encoding="utf-8")) == {"coletadoEm": "2025-06-01", "fonte": rr.CONTRATOS_PAGINA, "itens": {}}
    assert "2025 contratos 0 do órgão" in capsys.readouterr().out


def test_tipo_da_planilha():
    assert rr.tipo_da_planilha("CONTRATACOES DIRETAS FEV.xlsx") == "contratacao_direta"
    assert rr.tipo_da_planilha("licitações fev.XLSX") == "licitacao"
    assert rr.tipo_da_planilha("LICITACOES FEV.pdf") is None
    assert rr.tipo_da_planilha("OUTRA.xlsx") is None


def test_cnpj_do_texto():
    assert rr.cnpj_do_texto("LOTE: GRZ LTDA CNPJ: 07.872.397/0001-50") == "07872397000150"
    assert rr.cnpj_do_texto("A 07.872.397/0001-50 e B 07.872.397/0001-50") == "07872397000150"
    assert rr.cnpj_do_texto("A 07.872.397/0001-50 e B 11.222.333/0001-81") is None
    assert rr.cnpj_do_texto("CNPJ 07.872.397/0001-51") is None
    assert rr.cnpj_do_texto("sem documento") is None
    assert rr.cnpj_do_texto(None) is None


def test_itens_licitacoes_repetido_acrescenta_edital_ignora_linha_incompleta_e_traco():
    linhas = [["PROCESSO", "EDITAL", "OBJETO", "VENCEDOR (ES)", "VALOR HOMOLOGADO", "DATA", "SITUAÇÃO"],
              ["1/2026", "E1", "Obj A", "-", "-", "05/02/2026", "ABERTA"],
              ["1/2026", "E2", "Obj B", "EMPRESA X", "1.500,00", "", "HOMOLOGADA"],
              ["2/2026", "E3", "", "Y", "1", "", "X"],
              ["", "E4", "Obj C", "Y", "1", "", "X"]]
    itens = rr.itens_licitacoes(linhas, "licitacao", "f", 3)
    por_idf = {i["idFonte"]: i for i in itens.values()}
    assert sorted(por_idf) == ["1/2026", "1/2026|E2"]
    assert por_idf["1/2026"]["vencedor"] is None and por_idf["1/2026"]["valorHomologado"] is None and por_idf["1/2026"]["data"] == "2026-02-05"
    assert por_idf["1/2026|E2"]["vencedor"] == "EMPRESA X" and por_idf["1/2026|E2"]["valorHomologado"] == 1500.0
    assert por_idf["1/2026|E2"]["data"] is None and por_idf["1/2026|E2"]["mes"] == 3 and por_idf["1/2026|E2"]["procedimento"] is None


def test_coletar_licitacoes_le_mes_mais_novo_de_cada_tipo_e_usa_pdf_como_fonte(tmp_path, monkeypatch, capsys):
    hoje = date(2026, 6, 1)
    (tmp_path / "licitacoes_2023.json").write_text("{}", encoding="utf-8")
    anterior = {"coletadoEm": "2026-01-01", "itens": {"lic_x": {}}}
    comum.salvar(tmp_path / "licitacoes_2025.json", anterior)
    lic = xlsx([["PROCESSO", "OBJETO", "DATA", "SITUAÇÃO"], ["1/2026", "Obj jan", "46044", "ABERTA"]])
    direta = xlsx([["PROCEDIMENTO", "PROCESSO", "OBJETO", "VENCEDOR (ES)", "DATA", "SITUAÇÃO"], ["001/2026", "3/2026", "Limpeza", "DOALE ED 1", "46044", "HOMOLOGADA"]])
    raizes = {rr.LICITACOES_PAGINA: ([("Ano 2023", "L23/"), ("Ano 2024", "L24/"), ("Ano 2025", "L25/"), ("Ano 2026", "L26/")], [])}
    pastas = {"L23/": ([("12 - Dezembro", "L23/12")], []), "L24/": ([("03 - Março", "L24/3")], []), "L25/": ([("03 - Março", "L25/3")], []),
              "L26/": ([("01 - Janeiro", "L26/1"), ("02 - Fevereiro", "L26/2")], []),
              "L24/3": ([], [arquivo("x.pdf", "pdf")]), "L25/3": ([], []),
              "L26/1": ([], [arquivo("LICITACOES JAN.xlsx", "xlsx", "http://x/l.xlsx")]),
              "L26/2": ([], [arquivo("CONTRATACOES DIRETAS FEV.xlsx", "xlsx", "http://x/d.xlsx"), arquivo("CONTRATACOES DIRETAS FEV.pdf", "pdf", "http://x/d.pdf")])}
    chamadas = instalar_listas(monkeypatch, raizes, pastas)
    rr.coletar_licitacoes(SessaoArquivos({"http://x/l.xlsx": lic, "http://x/d.xlsx": direta}), tmp_path, hoje)
    assert "L23/12" not in chamadas and {"L26/1", "L26/2", "L24/3", "L25/3"} <= set(chamadas)
    grav = json.loads((tmp_path / "licitacoes_2026.json").read_text(encoding="utf-8"))
    assert grav["referencia"] == {"contratacao_direta": "2026-02", "licitacao": "2026-01"} and grav["fonte"] == rr.LICITACOES_PAGINA
    por_tipo = {i["tipo"]: i for i in grav["itens"].values()}
    assert por_tipo["licitacao"]["fonte"] == "http://x/l.xlsx" and por_tipo["contratacao_direta"]["fonte"] == "http://x/d.pdf"
    assert por_tipo["contratacao_direta"]["referenciaDiario"] == "DOALE ED 1" and por_tipo["licitacao"]["mes"] == 1
    assert not (tmp_path / "licitacoes_2024.json").exists()
    assert json.loads((tmp_path / "licitacoes_2025.json").read_text(encoding="utf-8")) == anterior
    captura = capsys.readouterr()
    assert "RR: licitações 2025: 2025 sem planilha de licitações na lista; mantém o arquivo anterior" in captura.err
    assert "2026 licitações 1 e contratações diretas 1 do órgão" in captura.out


def test_licitacoes_do_ano_para_no_mes_que_completa_os_dois_tipos(tmp_path, monkeypatch):
    lic = xlsx([["PROCESSO", "OBJETO"], ["1/2026", "A"]])
    direta = xlsx([["PROCEDIMENTO", "PROCESSO", "OBJETO"], ["001/2026", "2/2026", "B"]])
    chamadas = instalar_listas(monkeypatch, {"p": ([], [])}, {
        "M3": ([], [arquivo("LICITACOES.xlsx", "xlsx", "http://x/l.xlsx"), arquivo("DIRETAS.xlsx", "xlsx", "http://x/d.xlsx")]), "M2": ([], [])})
    conteudos = {"http://x/l.xlsx": lic, "http://x/d.xlsx": direta}
    arq_ano = tmp_path / "licitacoes_2026.json"
    rr.licitacoes_do_ano(rr.Lista(None, "p"), conteudos.__getitem__, 2026, [(3, "M3"), (2, "M2")], arq_ano, date(2026, 6, 1))
    assert chamadas == ["M3"]
    assert json.loads(arq_ano.read_text(encoding="utf-8"))["referencia"] == {"licitacao": "2026-03", "contratacao_direta": "2026-03"}


def test_coletar_verbas_incremental_substitui_meses_recentes_e_pula_antigos(tmp_path, monkeypatch, capsys):
    hoje = date(2026, 6, 15)
    existente = {"itens": [{"idDeputado": "marcos", "mes": 1, "item": "1.1", "valor": 1.0}, {"idDeputado": "angela", "mes": 5, "item": "9.9", "valor": 2.0}],
                 "mesesColetados": [1, 5]}
    comum.salvar(tmp_path / "verbas_2026.json", existente)
    raizes = {rr.VERBAS_PAGINA: ([("Ano 2026", "V26/")], [])}
    pastas = {"V26/": ([(f"{m:02d} - Mes", f"V{m}") for m in range(1, 6)], []),
              "V2": ([], []), "V4": ([], [arquivo("RESUMO GERAL.pdf", "pdf")]),
              "V3": ([], [arquivo("Dep. Marcos Jorge de Lima - Março 2026.odt", "odt", "http://x/m.odt")]),
              "V5": ([], [arquivo("Dep. Angela Aguida Portela Alves - Maio 2026.odt", "odt", "http://x/a.odt")])}
    chamadas = instalar_listas(monkeypatch, raizes, pastas)
    conteudos = {"http://x/m.odt": odt([["6.1", "z", "7.500,00"]]), "http://x/a.odt": odt([["4.1", "x", "5.000,00"]])}
    rr.coletar_verbas(SessaoArquivos(conteudos), DEPUTADOS, tmp_path, hoje)
    assert "V1" not in chamadas and {"V2", "V3", "V4", "V5"} <= set(chamadas)
    grav = json.loads((tmp_path / "verbas_2026.json").read_text(encoding="utf-8"))
    assert grav["mesesColetados"] == [1, 3, 4, 5] and grav["coletadoEm"] == "2026-06-15" and grav["fonte"] == rr.VERBAS_PAGINA
    assert [(i["mes"], i["idDeputado"], i["item"], i["valor"]) for i in grav["itens"]] == [
        (1, "marcos", "1.1", 1.0), (3, "marcos", "6.1", 7500.0), (5, "angela", "4.1", 5000.0)]
    assert "verbas 2026 3 lançamentos em 4 meses" in capsys.readouterr().out


def test_coletar_diarias_divide_por_ano_da_data_pula_encerrado_e_sem_efeito(tmp_path, monkeypatch, capsys):
    hoje = date(2026, 6, 15)
    (tmp_path / "diarias_2023.json").write_text('{"itens":[]}', encoding="utf-8")
    cab = ["NOME", "CARGO", "DESTINO", "FINALIDADE", "PERÍODO", "VALOR"]
    jan = xlsx([cab, ["JOILMA TEODORA DE ARAUJO SILVA", "DEPUTADA", "BRASÍLIA", "REUNIAO", "05/02/2026", "1250"],
                ["JOILMA TEODORA DE ARAUJO SILVA", "DEPUTADA", "BRASÍLIA", "REUNIAO", "28/12/2025", "300"],
                ["MARCOS JORGE DE LIMA", "DEPUTADO", "BRASÍLIA", "REUNIAO", "05/03/2023", "10"],
                ["FULANO DESCONHECIDO", "DEPUTADO", "BRASÍLIA", "REUNIAO", "05/02/2026", "10"],
                ["ASSESSOR X", "ASSESSOR", "BRASÍLIA", "REUNIAO", "05/02/2026", "10"]])
    fev = odt([cab, ["MARCOS JORGE DE LIMA", "DEPUTADO", "BOA VISTA", "VISITA", "46100", "900"]])
    raizes = {rr.DIARIAS_PAGINA: ([("Ano 2023", "D23/"), ("Ano 2026", "D26/")], [])}
    pastas = {"D23/": ([("10 - Outubro", "D23/10")], []), "D26/": ([("01 - Janeiro", "D1"), ("02 - Fevereiro", "D2")], []),
              "D1": ([], [arquivo("SEM EFEITO.pdf", "pdf", "http://x/se.pdf"), arquivo("DIARIAS JAN.pdf", "pdf", "http://x/j.pdf"),
                          arquivo("DIARIAS JAN.xlsx", "xlsx", "http://x/j.xlsx"), arquivo("DIARIAS SEM EFEITO.xlsx", "xlsx", "http://x/se.xlsx")]),
              "D2": ([], [arquivo("DIARIAS FEV.ods", "ods", "http://x/f.ods")])}
    chamadas = instalar_listas(monkeypatch, raizes, pastas)
    rr.coletar_diarias(SessaoArquivos({"http://x/j.xlsx": jan, "http://x/f.ods": fev}), DEPUTADOS, tmp_path, hoje)
    assert "D23/10" not in chamadas
    d26 = json.loads((tmp_path / "diarias_2026.json").read_text(encoding="utf-8"))
    assert [(i["data"], i["idDeputado"], i["fonte"]) for i in d26["itens"]] == [
        ("2026-02-05", "joilma", "http://x/j.pdf"), ("2026-03-19", "marcos", "http://x/f.ods")]
    d25 = json.loads((tmp_path / "diarias_2025.json").read_text(encoding="utf-8"))
    assert [(i["data"], i["valor"]) for i in d25["itens"]] == [("2025-12-28", 300.0)]
    assert (tmp_path / "diarias_2023.json").read_text(encoding="utf-8") == '{"itens":[]}'
    captura = capsys.readouterr()
    assert "diária de 'FULANO DESCONHECIDO' não casou" in captura.err
    assert "diárias 2026 2 registros" in captura.out and "diárias 2025 1 registros" in captura.out


def test_coletar_lista_de_deputados_vazia_avisa_e_nao_coleta_mais_nada(tmp_path, monkeypatch, capsys):
    chamadas = []
    monkeypatch.setattr(comum, "DADOS", tmp_path)
    monkeypatch.setattr(comum, "sessao", lambda: object())
    monkeypatch.setattr(rr, "coletar_deputados", lambda s: [])
    for nome in ("coletar_verbas", "coletar_diarias", "coletar_gabinete", "coletar_contratos", "coletar_licitacoes"):
        monkeypatch.setattr(rr, nome, lambda *a, nome=nome: chamadas.append(nome))
    rr.coletar()
    assert chamadas == [] and not (tmp_path / "RR").exists()
    assert "RR: lista de deputados vazia" in capsys.readouterr().err


def test_coletar_falha_em_uma_etapa_nao_derruba_as_outras(tmp_path, monkeypatch, capsys):
    chamadas = []
    sessao = object()
    monkeypatch.setattr(comum, "DADOS", tmp_path)
    monkeypatch.setattr(comum, "sessao", lambda: sessao)
    monkeypatch.setattr(rr, "coletar_deputados", lambda s: DEPUTADOS)
    monkeypatch.setattr(rr, "coletar_verbas", lambda s, deps, pasta, hoje: chamadas.append(("verbas", s, deps, pasta)))
    monkeypatch.setattr(rr, "coletar_diarias", lambda s, deps, pasta, hoje: chamadas.append(("diarias", s, deps, pasta)))

    def gabinete(*a):
        raise RuntimeError("pessoal fora do ar")

    monkeypatch.setattr(rr, "coletar_gabinete", gabinete)
    monkeypatch.setattr(rr, "coletar_contratos", lambda s, pasta, hoje: chamadas.append(("contratos", pasta)))
    monkeypatch.setattr(rr, "coletar_licitacoes", lambda s, pasta, hoje: chamadas.append(("licitacoes", pasta)))
    rr.coletar()
    assert [c[0] for c in chamadas] == ["verbas", "diarias", "contratos", "licitacoes"]
    assert chamadas[0][1:] == (sessao, DEPUTADOS, tmp_path / "RR")
    assert "RR: gabinete: pessoal fora do ar" in capsys.readouterr().err
    assert json.loads((tmp_path / "RR" / "deputados.json").read_text(encoding="utf-8"))["legislatura"] == "2023-2027"


def test_conferir_verba_sinaliza_item_novo_e_demonstrativo_vazio():
    falhas, avisos = rr._conferir_verba({"arquivo": "Dep. Ana - Maio 2026.odt", "linhas": [["9.9", "Novo", "10,00"]]})
    assert falhas == [] and avisos == ["item de despesa novo: 9.9"]
    falhas, _ = rr._conferir_verba({"arquivo": "RESUMO.odt", "linhas": [["x"]]})
    assert falhas == ["nome do ODT fora do padrão", "demonstrativo sem item de despesa com valor"]


def test_conferir_listagem_sem_pastas_arquivos_e_nome_fora_do_padrao():
    falhas, _ = rr._conferir_listagem({"raiz": "", "pasta": ""})
    assert falhas == ["lista de arquivos sem pastas por ano", "pasta mensal sem arquivos com link de download"]
    pasta = '<li class="file_record" data-name="RESUMO.pdf" data-file-type="pdf"><a href="http://x/r?wpdf_download=1"></a></li>'
    falhas, _ = rr._conferir_listagem({"raiz": '<li data-type="folder" data-name="Ano 2026" data-path="A/"></li>', "pasta": pasta})
    assert falhas == ["nome de arquivo fora do padrão 'Dep. Nome - Mês Ano': RESUMO.pdf"]


def test_conferir_diarias_sinaliza_periodo_ilegivel_e_sem_valor():
    linhas = [["NOME", "CARGO", "DESTINO", "FINALIDADE", "PERÍODO", "VALOR"], ["ANA", "DEPUTADA", "X", "Y", "sem data", ""]]
    falhas, _ = rr._conferir_diarias({"linhas": linhas})
    assert falhas == ["período ilegível: 'sem data'", "diária sem valor"]
    falhas, _ = rr._conferir_diarias({"linhas": [["x"]]})
    assert falhas == ["planilha de diárias sem linha de deputado (cabeçalho NOME/CARGO/DESTINO mudou?)"]


def test_conferir_gabinete_sem_cabecalho_e_sem_servidor():
    falhas, _ = rr._conferir_gabinete({"linhas": [["x"]]})
    assert falhas == ["planilha de pessoal sem o cabeçalho (Matrícula, Nome, Setor...)"]
    falhas, _ = rr._conferir_gabinete({"linhas": [CAB_PESSOAL]})
    assert falhas == ["planilha de pessoal sem servidor em setor 'GAB. DEP. <nome>'"]


def test_conferir_contratos_sem_contrato_e_sem_publicacao():
    falhas, _ = rr._conferir_contratos({"pasta": "Processo nº 1-2025", "arquivos": [arq("EMPENHO 1-2025.pdf")]})
    assert falhas == ["pasta de processo sem arquivo 'CONTRATO NN-AAAA'"]
    falhas, avisos = rr._conferir_contratos({"pasta": "Processo nº 1-2025", "arquivos": [arq("CONTRATO 1-2025.pdf")]})
    assert falhas == [] and avisos == ["pasta sem PDF de publicação"]


def test_conferir_licitacoes_sinaliza_planilha_sem_linhas_procedimento_e_data():
    vazio = {"linhas": [["x"]]}
    falhas, _ = rr._conferir_licitacoes({"licitacao": vazio, "contratacao_direta": vazio})
    assert falhas == ["planilha de licitacao sem linha com objeto e processo (cabeçalho mudou?)",
                      "planilha de contratacao_direta sem linha com objeto e processo (cabeçalho mudou?)"]
    lic = {"linhas": [["PROCESSO", "OBJETO", "MODALIDADE", "SITUAÇÃO", "DATA"], ["1/2026", "Obj", "PREGÃO", "ABERTA", "46044"]]}
    direta = {"linhas": [["PROCESSO", "OBJETO", "MODALIDADE", "SITUAÇÃO"], ["2/2026", "Obj", "DISPENSA", "ABERTA"]]}
    falhas, _ = rr._conferir_licitacoes({"licitacao": lic, "contratacao_direta": direta})
    assert falhas == ["contratação direta sem número do procedimento", "contratacao_direta: nenhuma data legível"]
