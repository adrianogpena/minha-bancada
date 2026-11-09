import json
import zipfile
from datetime import date
from io import BytesIO

import pytest
import requests

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


@pytest.fixture(autouse=True)
def sem_pausa(monkeypatch):
    monkeypatch.setattr(rj, "PAUSA", 0)
    monkeypatch.setattr(rj, "ESPERA_QUEDA", 0)


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
    abas = comum.xlsx_abas(xlsx([{"A": "Emenda", "B": "Autor"}, {"A": "7", "B": "Alan Lopes"}]))
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


def test_decodificar_utf8_cp1252_e_dupla_codificacao():
    assert rj.decodificar("Comissão".encode("utf-8")) == "Comissão"
    assert rj.decodificar("Comissão".encode("cp1252")) == "Comissão"
    assert rj.decodificar("Comissão".encode("utf-8").decode("cp1252").encode("utf-8")) == "Comissão"
    assert rj.decodificar("NÂº 5".encode("utf-8")) == "Nº 5"


def test_datas_e_horas_do_domino():
    assert rj.data_us_iso("10/14/2026") == "2026-10-14"
    assert rj.data_us_iso("13/14/2026") is None and rj.data_us_iso("") is None
    assert rj.hora_24("03:00:00 PM") == "15:00" and rj.hora_24("10:30:00 AM") == "10:30" and rj.hora_24("12:00:00 AM") == "00:00"


def test_url_busca_e_consulta_nome():
    assert rj.consulta_nome("Dr. Pedro Ricardo") == '"pedro ricardo"'
    assert rj.consulta_nome("Fred Pacheco Banda Dom") == '"fred pacheco"'
    url = rj.url_busca("/contlei.nsf/abc", '2026 AND "Verônica Lima"')
    assert url.endswith("SearchMax=0&SearchOrder=4&Query=2026+AND+%22Veronica+Lima%22") and url.startswith(rj.BASE + "/contlei.nsf/abc?SearchView")


def test_parse_normas_do_contrato():
    a = amostra("estadual_rj_normas")
    leis = rj.parse_normas(a["lei"], "lei")
    assert [(n["numero"], n["ano"], n["situacao"]) for n in leis] == [(11347, 2026, "Em Vigor"), (11346, 2026, "Em Vigor"), (11345, 2026, "Em Vigor")]
    assert leis[0]["autoria"] == ["Carlos Minc"] and leis[1]["autoria"] == ["Martha Rocha", "Tia Ju"]
    assert leis[0]["url"].startswith(rj.BASE + "/contlei.nsf/") and "Highlight" not in leis[0]["url"] and leis[0]["url"].endswith("?OpenDocument")
    assert "CAPOEIRA" in leis[0]["ementa"]
    decretos = rj.parse_normas(a["dec"], "dec")
    assert decretos[0]["numero"] == 3 and decretos[0]["ementa"].startswith("APROVA AS CONTAS") and decretos[0]["situacao"] is None
    assert rj.parse_normas(a["res"], "res")[0]["autoria"] == ["Tia Ju"]
    assert rj.data_da_norma(a["documento"]) == "2026-10-14"
    assert rj._conferir_normas(a) == ([], [])


def test_nomes_de_deputados_ignora_orgaos():
    assert rj.nomes_de_deputados(["Tia Ju", "COMISSÃO DE ORÇAMENTO", "Mesa Diretora", "PODER EXECUTIVO"]) == ["Tia Ju"]


def test_id_norma_e_estavel():
    assert rj.id_norma("lei", 11347, 2026) == rj.id_norma("lei", 11347, 2026)
    assert rj.id_norma("lei", 11347, 2026) != rj.id_norma("lc", 11347, 2026) and rj.id_norma("lei", 1, 2026).startswith("nor_")


def test_parse_proposicoes_do_contrato():
    a = amostra("estadual_rj_proposicoes")
    linhas = rj.parse_proposicoes(a["busca"])
    assert linhas[0]["cadastro"] == "20260600691" and linhas[0]["data"] == "2026-08-26" and linhas[0]["autor"] == "Carlos Minc"
    assert "=>" not in linhas[0]["ementa"] and linhas[0]["url"].endswith("?OpenDocument") and "Highlight" not in linhas[0]["url"]
    assert [l["cadastro"] for l in rj.parse_proposicoes(a["lista"])][:2] == ["20260308467", "20260308466"]
    assert rj._conferir_proposicoes(a) == ([], [])


def test_juntar_e_item_proposicao():
    a = amostra("estadual_rj_proposicoes")
    registros = {}
    rj.juntar_proposicoes(registros, rj.parse_proposicoes(a["busca"]))
    rj.juntar_proposicoes(registros, [{"cadastro": "20260700001", "url": "u", "ementa": "x", "data": None, "autor": "Alan Lopes"}])
    assert "20260700001" not in registros
    r = registros["20240600292"]
    assert r["autores"][:2] == ["Jair Bittencourt", "Carlos Minc"]
    item = rj.item_proposicao(r, {"Jair Bittencourt": "2", "Carlos Minc": "9"})
    assert item["tipo"] == "INDLEG" and item["numero"] == 292 and item["ano"] == 2024 and item["idsDeputados"] == ["2", "9"]
    assert item["dataApresentacao"] == "2024-05-23" and item["fonte"] == r["url"] and item["idsAutores"] == r["autores"]


def test_parse_pautas_do_contrato():
    a = amostra("estadual_rj_pautas")
    pauta = rj.parse_pautas(a["ordem-do-dia"], "ordem-do-dia")
    assert (pauta[0]["data"], pauta[0]["titulo"], pauta[0]["hora"]) == ("2026-11-05", "Sessão Plenária 10:30", "10:30")
    assert pauta[0]["arquivos"] == [{"nome": "Pauta da sessão", "url": pauta[0]["fonte"]}] and len(pauta[0]["id"]) == 32
    comissao = rj.parse_pautas(a["ata-comissao"], "ata-comissao")
    assert comissao[0]["comissao"].startswith("Comissão de Agricultura") and comissao[0]["titulo"] == "1ª Reunião EXTRAORDINÁRIA"
    assert rj.parse_pautas(a["ata-comissao-temporaria"], "ata-comissao-temporaria")[0]["titulo"] == "ATA DA 4ª AUDIÊNCIA PÚBLICA"
    assert rj._conferir_pautas(a) == ([], [])


def test_links_relatorio_e_itens_do_orgao():
    a = amostra("estadual_rj_orgao")
    contratos, atas = rj.links_relatorio(a["contratos"]), rj.links_relatorio(a["atas"])
    assert {l["ano"] for l in contratos} >= {2026, 2025} and all(l["url"].startswith(rj.TRANSPARENCIA + "/download-spic?file=") for l in contratos)
    itens = [i for ano in rj.itens_orgao(contratos, atas).values() for i in ano.values()]
    assert {i["tipo"] for i in itens} == {"contrato", "ata_registro"}
    ata = next(i for i in itens if i["tipo"] == "ata_registro")
    assert ata["numero"] and ata["objeto"] and ata["arquivos"][0]["url"].startswith("https://") and ata["fornecedor"] is None
    assert all(i["fonte"].startswith(rj.TRANSPARENCIA) for i in itens)
    assert not any("Convênios" in (i["objeto"] or "") for i in itens)
    assert rj._conferir_orgao(a) == ([], [])


class SessaoRoteada:
    def __init__(self, rotas):
        self.rotas = rotas
        self.pedidos = []

    def get(self, url, timeout=None):
        self.pedidos.append(url)
        for trecho, conteudo in self.rotas:
            if trecho in url:
                if isinstance(conteudo, Exception):
                    raise conteudo
                return Resposta(conteudo if isinstance(conteudo, bytes) else conteudo.encode("utf-8"))
        raise AssertionError(f"url fora das rotas: {url}")


def linha_norma(numero, ano, autoria, unid):
    return (f'<tr valign="top"><td align="center"></td><td><a href="/contlei.nsf/v/{unid}?OpenDocument&amp;Highlight=0,{ano}">{numero}</a></td>'
            f'<td>{ano}</td><td></td><td>Em Vigor</td><td>EMENTA {numero}</td><td>{autoria}</td></tr>')


def pagina(*linhas):
    return "<table>" + "".join(linhas) + "</table>"


DEPUTADOS_NOMES = [{"id": "1", "nome": "Alan Lopes", "nomeCivil": "Alan Lopes Santana"}, {"id": "2", "nome": "Tia Ju", "nomeCivil": "Julia Silva"}]


def test_coletar_normas_le_so_anos_abertos_e_a_data_uma_vez(tmp_path):
    pasta = tmp_path / "RJ"
    pasta.mkdir()
    comum.salvar(pasta / "normas_2023.json", {"normas": {}})
    sessao = SessaoRoteada([
        (rj.NORMAS["lei"]["visao"] + "?SearchView", pagina(linha_norma(5, 2026, "Alan Lopes,Tia Ju", "b" * 32), linha_norma(4, 2025, "Mesa Diretora", "a" * 32))),
        ("/contlei.nsf/a99e", pagina()),
        ("/contlei.nsf/1103", pagina()),
        ("/contlei.nsf/8037", pagina()),
        ("/contlei.nsf/v/", "<b>Data da Lei</b> 10/14/2026"),
    ])
    rj.coletar_normas(sessao, DEPUTADOS_NOMES, pasta, date(2026, 11, 2))
    assert not any("Query=2023" in u for u in sessao.pedidos)
    arq = json.loads((pasta / "normas_2026.json").read_text(encoding="utf-8"))["normas"]
    n = arq[rj.id_norma("lei", 5, 2026)]
    assert n["idsDeputados"] == ["1", "2"] and n["data"] == "2026-10-14" and n["tipo"] == "Lei ordinária" and n["fonte"].endswith("?OpenDocument")
    assert rj.id_norma("lei", 4, 2026) not in arq
    outros = json.loads((pasta / "normas_2025.json").read_text(encoding="utf-8"))["normas"]
    assert outros[rj.id_norma("lei", 4, 2025)]["idsDeputados"] == [] and outros[rj.id_norma("lei", 4, 2025)]["autoria"] == ["Mesa Diretora"]
    antes = len(sessao.pedidos)
    rj.coletar_normas(sessao, DEPUTADOS_NOMES, pasta, date(2026, 11, 2))
    assert not any("OpenDocument" in u for u in sessao.pedidos[antes:])


def test_normas_do_ano_divide_a_busca_no_teto(monkeypatch):
    monkeypatch.setattr(rj, "LIMITE_BUSCA", 2)
    sessao = SessaoRoteada([
        ("Query=2026+AND+%22alan+lopes%22", pagina(linha_norma(7, 2026, "Alan Lopes", "c" * 32))),
        ("Query=2026", pagina(linha_norma(8, 2026, "Tia Ju", "d" * 32), linha_norma(9, 2026, "Tia Ju", "e" * 32))),
    ])
    normas = rj.normas_do_ano(sessao, "res", 2026, [DEPUTADOS_NOMES[0]])
    assert [n["numero"] for n in normas] == [9, 8, 7] and len(sessao.pedidos) == 2


def test_pegar_repete_depois_de_conexao_derrubada():
    class Instavel:
        def __init__(self):
            self.n = 0

        def get(self, url, timeout=None):
            self.n += 1
            if self.n < 3:
                raise requests.ConnectionError("Remote end closed connection")
            return Resposta("ok".encode("utf-8"))

    s = Instavel()
    assert rj.pegar(s, "http://x") == "ok" and s.n == 3
    with pytest.raises(requests.ConnectionError):
        rj.pegar(SessaoRoteada([("x", requests.ConnectionError("fim"))]), "http://x")


def test_coletar_proposicoes_so_le_quando_ha_novidade(tmp_path):
    a = amostra("estadual_rj_proposicoes")
    pasta = tmp_path / "RJ"
    pasta.mkdir()
    deputados = [{"id": "9", "nome": "Carlos Minc", "nomeCivil": "Carlos Minc"}, {"id": "2", "nome": "Jair Bittencourt", "nomeCivil": "Jair Bittencourt"}]
    sessao = SessaoRoteada([("Internet/", a["lista"]), (rj.PROPOSICOES_VISAO, a["busca"])])
    buscas = lambda inicio: len([u for u in sessao.pedidos[inicio:] if "SearchView" in u])  # noqa: E731
    rj.coletar_proposicoes(sessao, deputados, pasta, date(2026, 11, 2))
    assert buscas(0) == 2 and len([u for u in sessao.pedidos if "Internet/" in u]) == len(rj.PROPOSICOES_LISTAS)
    materias = json.loads((pasta / "materias_2024.json").read_text(encoding="utf-8"))["materias"]
    assert materias["20240600292"]["idsDeputados"] == ["2", "9"] and materias["20240600292"]["numero"] == 292
    estado = json.loads((pasta / "proposicoes_estado.json").read_text(encoding="utf-8"))
    assert estado["completaEm"] == "2026-11-02" and "20260308467" in estado["topo"] and set(estado["deputados"]) == {"9", "2"}
    for ano in (2023, 2025):
        comum.salvar(pasta / f"materias_{ano}.json", {"materias": {}})
    antes = len(sessao.pedidos)
    rj.coletar_proposicoes(sessao, deputados, pasta, date(2026, 11, 3))
    assert buscas(antes) == 0
    rj.coletar_proposicoes(sessao, deputados, pasta, date(2026, 11, 10))
    assert buscas(antes) == 2


def test_coletar_proposicoes_le_quando_o_topo_traz_cadastro_novo(tmp_path):
    a = amostra("estadual_rj_proposicoes")
    pasta = tmp_path / "RJ"
    pasta.mkdir()
    deputados = [{"id": "9", "nome": "Carlos Minc", "nomeCivil": "Carlos Minc"}]
    sessao = SessaoRoteada([("Internet/", a["lista"]), (rj.PROPOSICOES_VISAO, a["busca"])])
    rj.coletar_proposicoes(sessao, deputados, pasta, date(2026, 11, 2))
    for ano in (2023, 2025):
        comum.salvar(pasta / f"materias_{ano}.json", {"materias": {}})
    estado = json.loads((pasta / "proposicoes_estado.json").read_text(encoding="utf-8"))
    estado["topo"] = ["20260308466"]
    comum.salvar(pasta / "proposicoes_estado.json", estado)
    antes = len(sessao.pedidos)
    rj.coletar_proposicoes(sessao, deputados, pasta, date(2026, 11, 3))
    assert len([u for u in sessao.pedidos[antes:] if "SearchView" in u]) == 1


def test_coletar_pautas_grava_por_ano_e_pula_ano_encerrado(tmp_path):
    a = amostra("estadual_rj_pautas")
    pasta = tmp_path / "RJ"
    pasta.mkdir()
    comum.salvar(pasta / "pautas_2023.json", {"itens": {}})
    sessao = SessaoRoteada([(rj.PAUTAS[t]["visao"], a[t]) for t in rj.PAUTAS])
    rj.coletar_pautas(sessao, pasta, date(2026, 11, 2))
    assert not any("Query=2023" in u for u in sessao.pedidos)
    itens = json.loads((pasta / "pautas_2026.json").read_text(encoding="utf-8"))["itens"]
    chaves = [k for k in itens if k.startswith("ordem-do-dia|")]
    assert len(chaves) == 3 and itens[chaves[0]]["arquivos"][0]["nome"] == "Pauta da sessão"
    assert any(i["tipo"] == "ata-comissao" for i in itens.values()) and any(i["tipo"] == "ata-comissao-temporaria" for i in itens.values())
    assert json.loads((pasta / "pautas_2024.json").read_text(encoding="utf-8"))["itens"] == {}


def test_coletar_orgao_grava_links_por_ano(tmp_path):
    a = amostra("estadual_rj_orgao")
    pasta = tmp_path / "RJ"
    pasta.mkdir()

    class SessaoHttp(SessaoRoteada):
        def get(self, url, timeout=None):
            r = super().get(url, timeout)
            r.text = r.content.decode("utf-8")
            return r

    rj.coletar_orgao(SessaoHttp([("report/118", a["contratos"]), ("report/51", a["atas"])]), pasta, date(2026, 11, 2))
    env = json.loads((pasta / "orgao_2026.json").read_text(encoding="utf-8"))
    assert env["fonte"] == rj.CONTRATOS_URL and any(i["tipo"] == "contrato" for i in env["itens"].values())
    assert any(i["tipo"] == "ata_registro" for f in pasta.glob("orgao_*.json") for i in json.loads(f.read_text(encoding="utf-8"))["itens"].values())


def avisos(capsys):
    return capsys.readouterr().err


def test_parsers_com_entrada_vazia_ou_incompleta():
    assert rj.hora_24(None) is None and rj.hora_24("sem hora") is None and rj.hora_24("12:30:00 PM") == "12:30"
    assert rj.data_us_iso(None) is None
    assert rj.consulta_nome("Yuri") == '"yuri"'
    assert rj.url_documento("http://x/y?OpenDocument&amp;Highlight=0,2026") == "http://x/y?OpenDocument"
    assert rj.url_documento("/a/b?OpenDocument") == rj.BASE + "/a/b?OpenDocument"
    assert rj.unid_documento("http://x/a?OpenDocument") is None and rj.unid_documento(None) is None
    assert rj.unid_documento(f"http://x/{'a' * 32}?OpenDocument") == "a" * 32
    assert rj.limpar_ementa(None) is None and rj.limpar_ementa("Dispõe   sobre => outra coisa") == "Dispõe sobre"
    assert rj.parse_normas("", "lei") == [] and rj.parse_proposicoes("<html></html>") == []
    assert rj.data_da_norma("<p>sem data</p>") is None and rj.data_da_norma("Data da promulgação 10/14/2026") == "2026-10-14"
    assert rj.links_emendas("<html></html>") == {} and rj.emendas_da_aba([{"A": "Emenda", "B": "Valor"}]) == []


def test_celulas_de_linha_com_colunas_a_menos():
    linha = '<tr valign="top"><td><a href="/contlei.nsf/v/' + "a" * 32 + '?OpenDocument">12</a></td><td>2026</td></tr>'
    normas = rj.parse_normas("<table>" + linha + "</table>", "lei")
    assert normas == [{"numero": 12, "ano": 2026, "situacao": None, "ementa": None, "autoria": [], "url": rj.BASE + "/contlei.nsf/v/" + "a" * 32 + "?OpenDocument"}]
    assert rj.celulas("<td>sem link</td>") == (["sem link"], None, None)


def test_itens_presenca_sem_total_de_sessoes():
    doc = {"periodo": "2026-09", "totalSessoes": None, "faltas": {"ALAN LOPES": 2}}
    item = rj.itens_presenca(doc, "u", DEPUTADOS)[0]
    assert item["presente"] is None and item["ausente"] == 2 and item["totalSessoes"] is None


class RespostaComErro(Resposta):
    def __init__(self, conteudo, erro):
        super().__init__(conteudo)
        self.erro = erro

    def raise_for_status(self):
        raise self.erro


class SessaoContada:
    def __init__(self, resposta=None, erro=None):
        self.resposta, self.erro, self.n = resposta, erro, 0

    def get(self, url, timeout=None):
        self.n += 1
        if self.erro:
            raise self.erro
        return self.resposta


def test_pegar_nao_repete_erro_http_nem_timeout_de_conexao():
    http = SessaoContada(RespostaComErro(b"", requests.HTTPError("403")))
    with pytest.raises(requests.HTTPError):
        rj.pegar(http, "http://x")
    assert http.n == 1
    lenta = SessaoContada(erro=requests.ConnectTimeout("sem conexão"))
    with pytest.raises(requests.ConnectTimeout):
        rj.pegar(lenta, "http://x")
    assert lenta.n == 1
    caida = SessaoContada(erro=requests.ConnectionError("derrubada"))
    with pytest.raises(requests.ConnectionError):
        rj.pegar(caida, "http://x")
    assert caida.n == rj.TENTATIVAS


def test_coletar_normas_falha_de_uma_norma_avisa_e_grava_sem_data(tmp_path, capsys):
    pasta = tmp_path / "RJ"
    pasta.mkdir()
    for ano in (2023, 2024):
        comum.salvar(pasta / f"normas_{ano}.json", {"normas": {}})
    sessao = SessaoRoteada([
        (rj.NORMAS["lei"]["visao"] + "?SearchView", pagina(linha_norma(5, 2026, "Alan Lopes", "b" * 32))),
        ("/contlei.nsf/a99e", pagina()), ("/contlei.nsf/1103", pagina()), ("/contlei.nsf/8037", pagina()),
        ("/contlei.nsf/v/", requests.ConnectionError("derrubada"))])
    rj.coletar_normas(sessao, DEPUTADOS_NOMES, pasta, date(2026, 11, 2))
    normas = json.loads((pasta / "normas_2026.json").read_text(encoding="utf-8"))["normas"]
    assert normas[rj.id_norma("lei", 5, 2026)]["data"] is None and normas[rj.id_norma("lei", 5, 2026)]["idsDeputados"] == ["1"]
    assert "RJ: data da norma" in avisos(capsys)
    assert json.loads((pasta / "normas_2025.json").read_text(encoding="utf-8"))["normas"] == {}


def test_coletar_pautas_do_ano_recente_nao_duplica_ao_reler(tmp_path):
    a = amostra("estadual_rj_pautas")
    pasta = tmp_path / "RJ"
    pasta.mkdir()
    sessao = SessaoRoteada([(rj.PAUTAS[t]["visao"], a[t]) for t in rj.PAUTAS])
    rj.coletar_pautas(sessao, pasta, date(2026, 11, 2))
    primeira = json.loads((pasta / "pautas_2026.json").read_text(encoding="utf-8"))["itens"]
    rj.coletar_pautas(sessao, pasta, date(2026, 11, 3))
    segunda = json.loads((pasta / "pautas_2026.json").read_text(encoding="utf-8"))
    assert segunda["itens"] == primeira and segunda["coletadoEm"] == "2026-11-03"


class SessaoHtml(SessaoRoteada):
    def get(self, url, timeout=None):
        r = super().get(url, timeout)
        r.text = r.content.decode("utf-8")
        return r


def test_coletar_orgao_junta_com_o_arquivo_anterior(tmp_path):
    a = amostra("estadual_rj_orgao")
    pasta = tmp_path / "RJ"
    pasta.mkdir()
    comum.salvar(pasta / "orgao_2026.json", {"coletadoEm": "2026-10-01", "itens": {"antigo": {"tipo": "contrato"}}})
    rj.coletar_orgao(SessaoHtml([("report/118", a["contratos"]), ("report/51", a["atas"])]), pasta, date(2026, 11, 2))
    env = json.loads((pasta / "orgao_2026.json").read_text(encoding="utf-8"))
    assert env["itens"]["antigo"] == {"tipo": "contrato"} and len(env["itens"]) > 1 and env["coletadoEm"] == "2026-11-02"


def test_coletar_orgao_erro_http_nao_grava(tmp_path):
    pasta = tmp_path / "RJ"
    pasta.mkdir()
    sessao = SessaoHtml([("report/118", requests.ConnectionError("fora do ar"))])
    with pytest.raises(requests.ConnectionError):
        rj.coletar_orgao(sessao, pasta, date(2026, 11, 2))
    assert list(pasta.iterdir()) == []


def test_coletar_presenca_le_cada_documento_e_sem_links_grava_vazio(tmp_path):
    a = amostra("estadual_rj_presenca")
    pasta = tmp_path / "RJ"
    pasta.mkdir()
    indice = '<a href="/ordemdia.nsf/x/abc?OpenDocument">10/15/2026</a><a href="/ordemdia.nsf/x/def?OpenDocument">09/20/2025</a>'
    sessao = SessaoRoteada([("presint", indice), ("x/abc", a["html"]), ("x/def", a["html"])])
    rj.coletar_presenca(sessao, DEPUTADOS, pasta, date(2026, 11, 2))
    gravado = json.loads((pasta / "presenca.json").read_text(encoding="utf-8"))
    assert gravado["coletadoEm"] == "2026-11-02" and gravado["fonte"] == rj.PRESENCA_URL
    assert sorted((i["periodo"], i["idDeputado"]) for i in gravado["itens"]) == [("2025-09", "1"), ("2025-09", "2"), ("2026-09", "1"), ("2026-09", "2")]
    assert {i["fonte"] for i in gravado["itens"]} == {f"{rj.PRESENCA_BASE}/ordemdia.nsf/x/abc?OpenDocument", f"{rj.PRESENCA_BASE}/ordemdia.nsf/x/def?OpenDocument"}
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    rj.coletar_presenca(SessaoRoteada([("presint", "<html></html>")]), DEPUTADOS, vazio, date(2026, 11, 2))
    assert json.loads((vazio / "presenca.json").read_text(encoding="utf-8"))["itens"] == []


def test_coletar_presenca_erro_http_nao_grava(tmp_path):
    class SessaoErro:
        def get(self, url, timeout=None):
            return RespostaComErro(b"", requests.HTTPError("500"))

    with pytest.raises(requests.HTTPError):
        rj.coletar_presenca(SessaoErro(), DEPUTADOS, tmp_path, date(2026, 11, 2))
    assert list(tmp_path.iterdir()) == []


def test_coletar_presenca_documento_com_erro_aborta_sem_gravar(tmp_path):
    a = amostra("estadual_rj_presenca")
    indice = '<a href="/ordemdia.nsf/x/abc?OpenDocument">10/15/2026</a><a href="/ordemdia.nsf/x/def?OpenDocument">09/20/2025</a>'
    sessao = SessaoRoteada([("presint", indice), ("x/abc", a["html"]), ("x/def", requests.ConnectionError("fora do ar"))])
    with pytest.raises(requests.ConnectionError):
        rj.coletar_presenca(sessao, DEPUTADOS, tmp_path, date(2026, 11, 2))
    assert list(tmp_path.iterdir()) == []


def pagina_de_emendas(*anos):
    return "".join(f'<div id="collapse-{ano}"><a href="/download-spic?file=ano{ano}"><i><span>excel</span></i></a></div>' for ano in anos)


CABECALHO_EMENDAS = {"A": "Emenda", "B": "Autor", "D": "Valor", "M": "Objeto"}


def test_coletar_emendas_pula_ano_encerrado_e_grava_os_demais(tmp_path):
    pasta = tmp_path / "RJ"
    pasta.mkdir()
    comum.salvar(pasta / "emendas_2023.json", {"itens": ["guardado"]})
    sessao = SessaoRoteada([("report/121", pagina_de_emendas(2023, 2026)),
                            ("file=ano2026", xlsx([CABECALHO_EMENDAS, {"A": "1", "B": "Alan Lopes", "D": "1000", "M": "Obra"},
                                                   {"A": "2", "B": "Desconhecido", "D": "5", "M": "Outra"}]))])
    rj.coletar_emendas(sessao, DEPUTADOS, pasta, date(2026, 11, 2))
    assert not any("ano2023" in u for u in sessao.pedidos)
    assert json.loads((pasta / "emendas_2023.json").read_text(encoding="utf-8")) == {"itens": ["guardado"]}
    gravado = json.loads((pasta / "emendas_2026.json").read_text(encoding="utf-8"))
    assert gravado["coletadoEm"] == "2026-11-02" and gravado["fonte"] == rj.EMENDAS_URL
    assert [(i["idDeputado"], i["numero"], i["valor"]) for i in gravado["itens"]] == [("1", "1", 1000.0)]


def test_coletar_emendas_planilha_sem_aba_impositivas_grava_lista_vazia(tmp_path, monkeypatch):
    pasta = tmp_path / "RJ"
    pasta.mkdir()
    monkeypatch.setattr(rj.comum, "xlsx_abas", lambda conteudo: {"Outra": [{"A": "x"}]})
    sessao = SessaoRoteada([("report/121", pagina_de_emendas(2026)), ("file=ano2026", b"x")])
    rj.coletar_emendas(sessao, DEPUTADOS, pasta, date(2026, 11, 2))
    assert json.loads((pasta / "emendas_2026.json").read_text(encoding="utf-8"))["itens"] == []


def test_coletar_emendas_pagina_sem_links_nao_grava_e_erro_http_propaga(tmp_path):
    rj.coletar_emendas(SessaoRoteada([("report/121", "<html></html>")]), DEPUTADOS, tmp_path, date(2026, 11, 2))
    assert list(tmp_path.iterdir()) == []

    class SessaoErro:
        def get(self, url, timeout=None):
            return RespostaComErro(b"", requests.HTTPError("503"))

    with pytest.raises(requests.HTTPError):
        rj.coletar_emendas(SessaoErro(), DEPUTADOS, tmp_path, date(2026, 11, 2))


ETAPAS_RJ = ["coletar_presenca", "coletar_emendas", "coletar_normas", "coletar_proposicoes", "coletar_pautas", "coletar_orgao"]


def test_coletar_sem_deputados_so_avisa_e_nao_roda_etapas(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(comum, "DADOS", tmp_path / "estaduais")
    monkeypatch.setattr(comum, "sessao", lambda: "sessao")
    monkeypatch.setattr(rj, "deputados_do_tse", lambda: [])
    chamadas = []
    monkeypatch.setattr(rj, "coletar_presenca", lambda *a: chamadas.append("presenca"))
    rj.coletar()
    assert chamadas == [] and not (tmp_path / "estaduais").exists()
    assert "sem eleitos de 2022" in avisos(capsys)


def test_coletar_roda_etapas_na_ordem_e_isola_erro(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(comum, "DADOS", tmp_path / "estaduais")
    monkeypatch.setattr(comum, "sessao", lambda: "sessao")
    monkeypatch.setattr(rj, "deputados_do_tse", lambda: DEPUTADOS)
    chamadas = []
    for nome in ETAPAS_RJ:
        def etapa(*args, nome=nome):
            chamadas.append((nome, args))
            if nome == "coletar_emendas":
                raise RuntimeError("planilha fora")

        monkeypatch.setattr(rj, nome, etapa)
    rj.coletar()
    assert [c[0] for c in chamadas] == ETAPAS_RJ
    pasta = tmp_path / "estaduais" / "RJ"
    hoje = date.today()
    assert chamadas[0][1] == ("sessao", DEPUTADOS, pasta, hoje) and chamadas[4][1] == ("sessao", pasta, hoje) and chamadas[5][1] == ("sessao", pasta, hoje)
    gravado = json.loads((pasta / "deputados.json").read_text(encoding="utf-8"))
    assert gravado["legislatura"] == "2023-2027" and gravado["host"] is None and gravado["deputados"] == DEPUTADOS
    saida = capsys.readouterr()
    assert "RJ: emendas: planilha fora" in saida.err and "RJ: 4 deputados" in saida.out
