import json
import zipfile
from datetime import date
from io import BytesIO

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
    corpo = "".join("<table:table-row>" + "".join(f"<table:table-cell><text:p>{c}</text:p></table:table-cell>" for c in l) + "</table:table-row>" for l in linhas)
    xml = (f'<?xml version="1.0"?><office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:table="{NS_TABELA}" '
           f'xmlns:text="{NS_TEXTO}"><office:body><office:text><table:table>{corpo}</table:table></office:text></office:body></office:document-content>')
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("content.xml", xml)
    return buf.getvalue()


def xlsx(linhas):
    strings, celulas = [], []
    for n, l in enumerate(linhas, 1):
        cs = ""
        for i, v in enumerate(l):
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
    arquivos_diaria = f'<li class="file_record" data-name="DEMONSTRATIVO FEV.xlsx" data-file-type="xlsx"><a href="http://x/d.xlsx?wpdf_download=true"></a></li>'

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
