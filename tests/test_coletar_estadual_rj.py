import json
import zipfile
from io import BytesIO

import coletar_estadual_rj as rj
import estaduais_comum as comum
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"

DEPUTADOS = [
    {"id": "1", "nome": "Alan Lopes", "nomeCivil": "Alan Lopes Santana"},
    {"id": "2", "nome": "Jair Bittencourt", "nomeCivil": "Jair de Siqueira Bittencourt Junior"},
    {"id": "3", "nome": "Dr Deodalto", "nomeCivil": "Deodalto Jose Ferreira"},
    {"id": "4", "nome": "Yuri", "nomeCivil": "Yuri Lucas Carius de Moura Almeida"},
]


def amostra(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


def test_ligar_casa_nome_parcial_dentro_do_nome_civil():
    ligados = rj.ligar(["ALAN LOPES", "Dr. Deodalto", "Yuri Moura", "Marcelo Dino"], DEPUTADOS)
    assert ligados == {"ALAN LOPES": "1", "Dr. Deodalto": "3", "Yuri Moura": "4"}


def test_ligar_nome_ambiguo_fica_de_fora():
    deputados = DEPUTADOS + [{"id": "5", "nome": "Alan Silva", "nomeCivil": "Alan Pereira Silva"}]
    assert "Alan" not in rj.ligar(["Alan"], deputados)


def test_links_presenca_e_periodo():
    html = '<a href="/ordemdia.nsf/x/abc?OpenDocument">10/15/2026</a> <a href="/ordemdia.nsf/presint?OpenForm">x</a>'
    assert rj.links_presenca(html) == [{"url": f"{rj.PRESENCA_BASE}/ordemdia.nsf/x/abc?OpenDocument", "data": "2026-10-15"}]
    assert rj.periodo_do_mes(9, "2026-10-15") == "2026-09"
    assert rj.periodo_do_mes(12, "2027-01-08") == "2026-12"


def test_parse_presenca_do_contrato():
    a = amostra("estadual_rj_presenca")
    doc = rj.parse_presenca(a["html"], a["publicado"])
    assert doc["periodo"] == "2026-09"
    assert doc["totalSessoes"] == 14
    assert doc["faltas"] == {"ALAN LOPES": 1, "JAIR BITTENCOURT": 1}
    falhas, avisos = rj._conferir_presenca(a)
    assert falhas == [] and avisos == []


def test_itens_presenca_calcula_presentes():
    doc = {"periodo": "2026-09", "totalSessoes": 14, "faltas": {"ALAN LOPES": 1, "DESCONHECIDO": 3}}
    itens = rj.itens_presenca(doc, "http://fonte", DEPUTADOS)
    assert itens == [{"idDeputado": "1", "periodo": "2026-09", "presente": 13, "ausente": 1, "licenca": None, "totalSessoes": 14, "fonte": "http://fonte"}]


def test_links_emendas_por_ano_do_contrato():
    links = rj.links_emendas(amostra("estadual_rj_emendas")["pagina"])
    assert set(links) >= {2026} and links[2026].startswith(rj.TRANSPARENCIA + "/download-spic?file=")


def test_emendas_da_aba_e_itens_do_contrato():
    a = amostra("estadual_rj_emendas")
    regs = rj.emendas_da_aba(a["linhas"])
    assert [r["autor"] for r in regs] == ["Alan Lopes", "Alan Lopes"]
    itens = rj.itens_emendas(regs, DEPUTADOS, rj.EMENDAS_URL, 2026)
    assert len(itens) == 2 and itens[0]["idDeputado"] == "1" and itens[0]["ano"] == 2026
    assert itens[0]["valor"] == 950367.0 and itens[0]["fonte"] == rj.EMENDAS_URL
    assert rj._conferir_emendas(a) == ([], [])


def xlsx(linhas):
    strings, celulas = [], []
    for i, linha in enumerate(linhas, 1):
        cs = ""
        for col, v in linha.items():
            strings.append(v)
            cs += f'<c r="{col}{i}" t="s"><v>{len(strings) - 1}</v></c>'
        celulas.append(f'<row r="{i}">{cs}</row>')
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Impositivas" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{ns}"><sheetData>{"".join(celulas)}</sheetData></worksheet>')
        z.writestr("xl/sharedStrings.xml", f'<sst xmlns="{ns}">' + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>")
    return buf.getvalue()


def test_ler_xlsx():
    abas = rj.ler_xlsx(xlsx([{"A": "Emenda", "B": "Autor"}, {"A": "7", "B": "Alan Lopes"}]))
    assert abas == {"Impositivas": [{"A": "Emenda", "B": "Autor"}, {"A": "7", "B": "Alan Lopes"}]}


class Resposta:
    def __init__(self, conteudo):
        self.content = conteudo

    def raise_for_status(self):
        pass


class Sessao:
    def __init__(self, paginas):
        self.paginas = paginas

    def get(self, url, timeout=None):
        return Resposta(self.paginas[url])


def test_coletar_grava_arquivos(tmp_path, monkeypatch):
    a = amostra("estadual_rj_presenca")
    doc_url = f"{rj.PRESENCA_BASE}/ordemdia.nsf/x/abc?OpenDocument"
    planilha = rj.TRANSPARENCIA + "/download-spic?file=planilha"
    pagina_emendas = (b'<div id="collapse-2026"><a href="/download-spic?file=planilha"><i><span>excel</span></i></a></div>')
    cab = {"A": "Emenda", "B": "Autor", "D": "Valor", "M": "Objeto"}
    sessao = Sessao({
        rj.PRESENCA_URL: b'<a href="/ordemdia.nsf/x/abc?OpenDocument">10/15/2026</a>',
        doc_url: a["html"].encode("utf-8"),
        rj.EMENDAS_URL: pagina_emendas,
        planilha: xlsx([cab, {"A": "1", "B": "Alan Lopes", "D": "1000", "M": "Obra"}]),
    })
    tse = tmp_path / "RJ.json"
    tse.write_text(json.dumps([{"cargo": "DEPUTADO ESTADUAL", "situacao": "eleito", "sequencial": "9", "nome": "Alan Lopes Santana", "urna": "Alan Lopes", "partido": "PL"}]), encoding="utf-8")
    monkeypatch.setattr(rj, "TSE_ARQUIVO", tse)
    monkeypatch.setattr(comum, "DADOS", tmp_path / "estaduais")
    monkeypatch.setattr(comum, "sessao", lambda: sessao)
    rj.coletar()
    pasta = tmp_path / "estaduais" / "RJ"
    deputados = json.loads((pasta / "deputados.json").read_text(encoding="utf-8"))
    assert deputados["host"] is None and deputados["deputados"][0]["id"] == "9"
    presenca = json.loads((pasta / "presenca.json").read_text(encoding="utf-8"))["itens"]
    assert presenca == [{"ausente": 1, "fonte": doc_url, "idDeputado": "9", "licenca": None, "periodo": "2026-09", "presente": 13, "totalSessoes": 14}]
    emendas = json.loads((pasta / "emendas_2026.json").read_text(encoding="utf-8"))["itens"]
    assert emendas[0]["idDeputado"] == "9" and emendas[0]["valor"] == 1000.0 and emendas[0]["objeto"] == "Obra"
