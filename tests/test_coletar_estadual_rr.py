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
