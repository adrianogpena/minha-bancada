"""Coletor da Assembleia do Ceará (scripts/coletar_estadual_ce.py) contra amostras reais em tests/fixtures/contratos/."""
import base64
import json
import re
from datetime import date

import pytest

import coletar_estadual_ce as ce
import estaduais_comum as comum
import identidades
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"


def fixture(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))


def amostra(nome):
    return fixture(nome)["amostra"]


DEPUTADOS = [
    {"id": "agenor-neto", "nome": "Agenor Neto", "nomeCivil": "Agenor Gomes de Araújo Neto"},
    {"id": "ap-luiz-henrique", "nome": "Ap Luiz Henrique", "nomeCivil": "Luiz Henrique Castelo Lima"},
    {"id": "dra-silvana", "nome": "Dra. Silvana", "nomeCivil": "Silvana Oliveira de Sousa"},
    {"id": "larissa-gaspar", "nome": "Larissa Gaspar", "nomeCivil": "Larissa Maria Fernandes Gaspar da Costa"},
    {"id": "jeova-mota", "nome": "Jeová Mota", "nomeCivil": "Jeová Mota"},
]


def test_contratos_registrados():
    assert [c["nome"] for c in ce.CONTRATOS] == [f"estadual_ce_{x}" for x in
                                                 ("deputados", "vdp", "pessoal", "diarias", "votacoes_lista", "votacao_xlsx", "proposicoes")]
    for c in ce.CONTRATOS:
        falhas, _ = c["html"](amostra(c["nome"]))
        assert falhas == [], c["nome"]


def test_cartoes_titulares_e_suplentes():
    lista = ce.cartoes(amostra("estadual_ce_deputados")["lista"])
    assert lista[0] == {"id": "agenor-neto", "nome": "Agenor Neto", "foto": "https://www.al.ce.gov.br/image/389109",
                        "partido": "MDB", "titular": True}
    assert [d["titular"] for d in lista] == [True, True, True, False, False]


def test_ficha():
    dados = ce.ficha(amostra("estadual_ce_deputados")["ficha"])
    assert dados == {"nomeCivil": "Agenor Gomes de Araújo Neto", "email": "gabdepagenor.neto@al.ce.gov.br"}


def test_ligar_ignora_pontos():
    ligados = ce.ligar(["DEP AGENOR NETO", "AP. LUIZ HENRIQUE", "DRA.SILVANA", "Gulherme Landim"], DEPUTADOS)
    assert ligados == {"DEP AGENOR NETO": "agenor-neto", "AP. LUIZ HENRIQUE": "ap-luiz-henrique", "DRA.SILVANA": "dra-silvana"}


def test_vdp_itens():
    linhas = ce.linhas_csv(amostra("estadual_ce_vdp")["csv"], "DEPUTADO")
    ligacao = ce.ligar({linha["DEPUTADO"] for linha in linhas}, DEPUTADOS)
    itens, sem_par = ce.itens_vdp(linhas, ligacao, "http://fonte")
    assert itens[0]["idDeputado"] == "agenor-neto" and itens[0]["mes"] == 10 and itens[0]["valor"] == 4000.0
    assert itens[0]["categoria"].startswith("REFERE-SE A DISPONIBILIZACAO DO BENEFICIO ALIMENTACAO") and itens[0]["cnpj"] == "47866934000174" and itens[0]["fonte"] == "http://fonte"
    assert sem_par == set() or "AGENOR NETO" not in sem_par


def test_vdp_sem_par_e_cabecalho_sem_dados():
    itens, sem_par = ce.itens_vdp([{"DEPUTADO": "DEP FULANO", "PERIODO": "10/2026", "VALOR": "1,00"}], {}, "f")
    assert itens == [] and sem_par == {"FULANO"}
    assert ce.linhas_csv(";;;\nDEPUTADO;PERIODO;EMPENHO;DESCRICAO;CNPJ;CREDOR;VALOR\n", "DEPUTADO") == []


def test_remuneracao_so_deputados():
    linhas = ce.linhas_csv(amostra("estadual_ce_pessoal")["csv"], "NOME")
    ligacao = ce.ligar({linha["NOME"] for linha in linhas}, DEPUTADOS)
    itens, _ = ce.itens_remuneracao(linhas, ligacao, 2026, 9)
    assert itens[0]["idDeputado"] == "agenor-neto" and itens[0]["bruto"] == 39993.14 and itens[0]["liquido"] == 30621.93
    assert itens[0]["componentes"]["descontosLegais"] == 9371.21 and itens[0]["mes"] == 9
    assert itens[0]["fonte"].endswith("pessoal?mes=09&ano=2026")


def test_diarias():
    linhas = ce.linhas_csv(amostra("estadual_ce_diarias")["csv"], "BENEFICIARIO")
    nome = linhas[0]["BENEFICIARIO"]
    itens, sem_par = ce.itens_diarias(linhas, {nome: "agenor-neto"}, 2026)
    assert itens[0]["idDeputado"] == "agenor-neto" and itens[0]["data"] == "2026-10-19" and itens[0]["valor"] == 360.0
    assert nome not in sem_par and len(sem_par) == len({linha["BENEFICIARIO"] for linha in linhas}) - 1


def test_votacoes_da_pagina():
    lista = ce.votacoes_da_pagina(amostra("estadual_ce_votacoes_lista")["html"] + "</td></tr>")
    assert lista[0]["data"] == "2026-07-14" and lista[0]["sessao"].startswith("63")
    assert lista[0]["xlsx"].endswith(".xlsx") and lista[0]["pdf"].endswith(".pdf") and lista[0]["id"] in lista[0]["xlsx"]


def test_votacao_do_xlsx():
    dados = ce.votacao_do_xlsx(amostra("estadual_ce_votacao_xlsx")["linhas"])
    assert dados["data"] == "2026-07-14" and dados["aprovada"] is True and dados["tipo"] == "PL"
    assert (dados["numero"], dados["ano"]) == ("69", 2026)
    assert dados["apuracao"] == {"sim": "23", "nao": "6", "abstencao": "1"}
    assert ("LARISSA GASPAR", "PT", "não") in dados["votos"] and ("DE ASSIS DINIZ", "PT", "sim") in dados["votos"]
    assert all(nome != "ROMEU ALDIGUERI" for nome, _, _ in dados["votos"])


def test_votacao_data_com_espacos():
    linhas = [{"A": "Presidente: X   Data: 03 /03/2026   Horário: 12:18"}, {"A": "Processo: NOMINAL   Resultado: REJEITADO"},
              {"A": "MATÉRIA - 03/2026 - Projeto de Lei Complementar oriundo da Mensagem"},
              {"A": "1", "B": "AGENOR NETO", "C": "MDB", "E": "NÃO (V)"}]
    dados = ce.votacao_do_xlsx(linhas)
    assert dados["data"] == "2026-03-03" and dados["aprovada"] is False and dados["tipo"] == "PLC"
    assert ce.votacao_do_xlsx(linhas[:3]) is None


@pytest.mark.parametrize("texto,esperado", [
    ("AUTORIA: DEPUTADO BRUNO PEDROSA, COAUTORIA: DEPUTADO SIMÃO PEDRO", ["BRUNO PEDROSA", "SIMÃO PEDRO"]),
    ("Autoria: Deputado Danniel Oliveira.", ["Danniel Oliveira"]),
    ("ALMIR BIE COAUTORIA SÉRGIO AGUIAR", ["ALMIR BIE", "SÉRGIO AGUIAR"]),
    ("DRA. SILVANA", ["DRA. SILVANA"]),
    ("A / B E C", ["A", "B", "C"]),
])
def test_autores(texto, esperado):
    assert ce.autores(texto) == esperado


def test_proposicoes_da_pagina():
    html = amostra("estadual_ce_proposicoes")["html"]
    assert ce.ultima_pagina(html) > 1
    itens = ce.proposicoes_da_pagina(html)
    assert itens[0]["numero"] == 2 and itens[0]["ano"] == 2023 and itens[0]["autor"] == "LEONARDO PINHEIRO"
    assert itens[0]["dataApresentacao"] == "2023-02-02" and itens[0]["situacao"] == "Lei 18.393"
    assert itens[0]["linkTexto"].endswith("pl2_23.htm")


def test_tipo_da_materia():
    assert ce.tipo_da_materia("Projeto de Lei Complementar oriundo da Mensagem")[0] == "PLC"
    assert ce.tipo_da_materia("Proposta de Emenda à Constituição n.º 1")[0] == "PEC"
    assert ce.tipo_da_materia("algo sem tipo") == ("MAT", None)


class Resposta:
    def __init__(self, conteudo):
        self.content = conteudo.encode("utf-8") if isinstance(conteudo, str) else conteudo

    def raise_for_status(self):
        pass


class SessaoFalsa:
    def __init__(self, paginas):
        self.paginas = paginas

    def get(self, url, timeout=None):
        return Resposta(self.paginas[url])


def test_coletar_deputados_grava_no_formato_comum(tmp_path, monkeypatch):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    amostras = amostra("estadual_ce_deputados")
    paginas = {ce.LISTA_URL: amostras["lista"]}
    for d in ce.cartoes(amostras["lista"]):
        paginas[f"{ce.SITE}/deputados/{d['id']}"] = amostras["ficha"]
    deputados = ce.coletar_deputados(SessaoFalsa(paginas))
    gravado = json.loads((tmp_path / "deputados.json").read_text(encoding="utf-8"))
    assert gravado["host"] is None and gravado["fonte"] == ce.LISTA_URL and len(gravado["deputados"]) == len(deputados) == 5
    primeiro = gravado["deputados"][0]
    assert primeiro["id"] == "agenor-neto" and primeiro["nomeCivil"] == "Agenor Gomes de Araújo Neto" and primeiro["fonte"].endswith("/deputados/agenor-neto")
    assert identidades.ligar_nomes(["DEP AGENOR NETO"], gravado["deputados"]) == {"DEP AGENOR NETO": "agenor-neto"}


def test_coletar_votacoes_grava_votos_ligados(tmp_path, monkeypatch):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    lista_html = amostra("estadual_ce_votacoes_lista")["html"] + "</td></tr>"
    primeira = ce.votacoes_da_pagina(lista_html)[0]
    monkeypatch.setattr(ce.comum, "xlsx_linhas", lambda conteudo: amostra("estadual_ce_votacao_xlsx")["linhas"])
    s = SessaoFalsa({ce.VOTACOES_URL: lista_html, **{v["xlsx"]: b"x" for v in ce.votacoes_da_pagina(lista_html)}})
    ce.coletar_votacoes(s, DEPUTADOS)
    votacoes = json.loads((tmp_path / "votacoes.json").read_text(encoding="utf-8"))["votacoes"]
    v = votacoes[primeira["id"]]
    assert v["sim"] == 23 and v["nao"] == 6 and v["abstencoes"] == 1 and v["aprovada"] is True and v["fonte"] == primeira["pdf"]
    assert ["larissa-gaspar", "não"] in v["votos"] and ["jeova-mota", "sim"] in v["votos"]
    materias = json.loads((tmp_path / "materias_votadas.json").read_text(encoding="utf-8"))
    assert materias[primeira["id"]]["tipo"] == "PL" and materias[primeira["id"]]["numero"] == "69"


def fixar_hoje(monkeypatch, ano, mes, dia=10):
    class Hoje(date):
        @classmethod
        def today(cls):
            return date(ano, mes, dia)

    monkeypatch.setattr(ce, "date", Hoje)


def avisos(capsys):
    return capsys.readouterr().err


def baixar_falso(monkeypatch, tratador):
    monkeypatch.setattr(ce, "baixar", lambda s, url, params=None, timeout=None: tratador(url, params))


class RespostaJson:
    def __init__(self, dados):
        self.dados = dados

    def raise_for_status(self):
        pass

    def json(self):
        return self.dados


class SessaoJson:
    def __init__(self, paginas):
        self.paginas = paginas
        self.pedidos = []

    def get(self, url, timeout=None, params=None):
        self.pedidos.append(params)
        return RespostaJson(self.paginas[params["page"]])


def test_decodificar():
    assert ce.decodificar("ação".encode("utf-8-sig")) == "ação"
    assert ce.decodificar("ação".encode("cp1252")) == "ação"
    assert ce.decodificar("ação".encode("cp1252"), "cp1252") == "ação"
    assert ce.decodificar("ação".encode("utf-8"), "latin-1") == "aÃ§Ã£o"


def test_meses_do_ano(monkeypatch):
    fixar_hoje(monkeypatch, 2026, 4)
    assert list(ce.meses_do_ano(2026)) == [1, 2, 3, 4]
    assert list(ce.meses_do_ano(2025)) == list(range(1, 13))


def test_coletar_deputados_sem_cartoes_levanta(tmp_path, monkeypatch):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    with pytest.raises(RuntimeError, match="sem cartões"):
        ce.coletar_deputados(SessaoFalsa({ce.LISTA_URL: "<html></html>"}))
    assert not (tmp_path / "deputados.json").exists()


def test_coletar_deputados_ficha_com_falha_avisa_e_segue(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    amostras = amostra("estadual_ce_deputados")
    cartoes = ce.cartoes(amostras["lista"])
    paginas = {ce.LISTA_URL: amostras["lista"]}
    for d in cartoes[1:]:
        paginas[f"{ce.SITE}/deputados/{d['id']}"] = amostras["ficha"]
    deputados = ce.coletar_deputados(SessaoFalsa(paginas))
    assert deputados[0]["nomeCivil"] is None and deputados[0]["email"] is None and deputados[0]["id"] == cartoes[0]["id"]
    assert deputados[1]["nomeCivil"] == "Agenor Gomes de Araújo Neto"
    assert f"CE: ficha de {cartoes[0]['id']}" in avisos(capsys)


def csv_vdp(periodos):
    linhas = [";;;", "DEPUTADO;PERIODO;EMPENHO;DESCRICAO;CNPJ;CREDOR;VALOR"]
    for periodo in periodos:
        linhas.append(f"DEP AGENOR NETO;{periodo};2026NE1;ALIMENTACAO;47866934000174;TICKET SERVICOS S/A;4.000,00")
        linhas.append(f"DEP FULANO DE TAL;{periodo};2026NE2;COMBUSTIVEL;;POSTO X;1,00")
    return "\n".join(linhas) + "\n"


def test_coletar_por_ano_pula_ano_passado_gravado_e_grava_atual(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    fixar_hoje(monkeypatch, 2026, 3)
    (tmp_path / "x_2025.json").write_text("{}", encoding="utf-8")
    chamadas = []

    def baixar_periodo(s, ano, mes):
        chamadas.append((ano, mes))
        if mes == 2:
            raise RuntimeError("fora do ar")
        return f"{ano}-{mes}"

    def montar(ano, mes, texto):
        return [{"mes": mes, "texto": texto}], {f"sem-{mes}"}

    sem_par = ce.coletar_por_ano("s", "x", "http://fonte", 2025, True, baixar_periodo, montar)
    assert sorted(chamadas) == [(2026, 1), (2026, 2), (2026, 3)]
    assert sem_par == {"sem-1", "sem-3"}
    gravado = json.loads((tmp_path / "x_2026.json").read_text(encoding="utf-8"))
    assert gravado["coletadoEm"] == "2026-03-10" and gravado["fonte"] == "http://fonte"
    assert sorted(i["mes"] for i in gravado["itens"]) == [1, 3]
    assert (tmp_path / "x_2025.json").read_text(encoding="utf-8") == "{}"
    assert "CE: x 2026-02: fora do ar" in avisos(capsys)


def test_coletar_por_ano_sem_itens_so_grava_o_ano_corrente(tmp_path, monkeypatch):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    fixar_hoje(monkeypatch, 2026, 3)
    chamadas = []

    def baixar_periodo(s, ano, mes):
        chamadas.append((ano, mes))
        return ""

    ce.coletar_por_ano("s", "y", "f", 2025, False, baixar_periodo, lambda ano, mes, texto: ([], set()))
    assert chamadas == [(2025, None), (2026, None)]
    assert not (tmp_path / "y_2025.json").exists()
    assert json.loads((tmp_path / "y_2026.json").read_text(encoding="utf-8"))["itens"] == []


def test_coletar_por_ano_prazo_esgotado_vira_aviso(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    fixar_hoje(monkeypatch, 2026, 1)

    def baixar_periodo(s, ano, mes):
        raise comum.PrazoEsgotado("prazo de coleta esgotado")

    ce.coletar_por_ano("s", "z", "f", 2026, False, baixar_periodo, lambda ano, mes, texto: ([], set()))
    assert "CE: z 2026: prazo de coleta esgotado" in avisos(capsys)
    assert json.loads((tmp_path / "z_2026.json").read_text(encoding="utf-8"))["itens"] == []


def test_coletar_vdp_grava_um_arquivo_por_ano_e_avisa_sem_par(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    monkeypatch.setattr(ce, "ANO_VDP", 2025)
    fixar_hoje(monkeypatch, 2026, 2)
    urls = []

    def tratador(url, params):
        urls.append(url)
        mes, ano = re.search(r"mes=(\d+)&ano=(\d+)", url).groups()
        return csv_vdp([f"{mes}/{ano}"]).encode("utf-8")

    baixar_falso(monkeypatch, tratador)
    ce.coletar_vdp("s", DEPUTADOS)
    v2025 = json.loads((tmp_path / "verbas_2025.json").read_text(encoding="utf-8"))
    v2026 = json.loads((tmp_path / "verbas_2026.json").read_text(encoding="utf-8"))
    assert len(v2025["itens"]) == 12 and len(v2026["itens"]) == 2
    assert {i["idDeputado"] for i in v2025["itens"]} == {"agenor-neto"}
    assert sorted(i["mes"] for i in v2026["itens"]) == [1, 2]
    assert v2026["itens"][0]["valor"] == 4000.0 and v2026["itens"][0]["cnpj"] == "47866934000174"
    assert v2026["itens"][0]["fonte"].startswith(f"{ce.VDP_PAGINA}?mes=")
    assert "VDP sem deputado atual (1): ['FULANO DE TAL']" in avisos(capsys)
    urls.clear()
    ce.coletar_vdp("s", DEPUTADOS)
    assert len(urls) == 2 and all("ano=2026" in u for u in urls)


def test_coletar_remuneracao_so_deputados_ligados(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    monkeypatch.setattr(ce, "ANO_REMUNERACAO", 2026)
    fixar_hoje(monkeypatch, 2026, 2)
    csv_texto = ("MATRICULA;NOME;CATEGORIA;DESCONTOS LEGAIS;REMUNERACAO BRUTA;REMUNERACAO LIQUIDA\n"
                 "1;AGENOR GOMES DE ARAUJO NETO;DEPUTADOS;1.000,00;10.000,00;9.000,00\n"
                 "2;FULANO DE TAL;DEPUTADOS;1,00;2,00;1,00\n"
                 "3;BELTRANO;SERVIDOR;1,00;2,00;1,00\n")
    pedidos = []

    def tratador(url, params):
        pedidos.append(url)
        return csv_texto.encode("utf-8")

    baixar_falso(monkeypatch, tratador)
    ce.coletar_remuneracao("s", DEPUTADOS)
    assert sorted(pedidos) == [f"{ce.PESSOAL_PAGINA}/csv?mes=01&ano=2026", f"{ce.PESSOAL_PAGINA}/csv?mes=02&ano=2026"]
    itens = json.loads((tmp_path / "remuneracao_2026.json").read_text(encoding="utf-8"))["itens"]
    assert sorted(i["mes"] for i in itens) == [1, 2] and {i["idDeputado"] for i in itens} == {"agenor-neto"}
    assert itens[0]["bruto"] == 10000.0 and itens[0]["liquido"] == 9000.0 and itens[0]["componentes"] == {"descontosLegais": 1000.0}
    assert "remuneração sem deputado atual (1): ['FULANO DE TAL']" in avisos(capsys)


def test_itens_remuneracao_nome_sem_par_e_outra_categoria():
    linhas = [{"NOME": "SEM PAR", "CATEGORIA": "DEPUTADOS"}, {"NOME": "X", "CATEGORIA": "SERVIDOR"}]
    assert ce.itens_remuneracao(linhas, {}, 2026, 1) == ([], {"SEM PAR"})


def test_coletar_diarias_um_arquivo_por_ano(tmp_path, monkeypatch):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    monkeypatch.setattr(ce, "ANO_REMUNERACAO", 2025)
    fixar_hoje(monkeypatch, 2026, 1)
    pedidos = []

    def tratador(url, params):
        pedidos.append(url)
        return ("BENEFICIARIO;DESCRICAO;DATA PAGAMENTO;EMPENHO;VALOR\n"
                "DEP AGENOR NETO;DIARIA PARA   BRASILIA;19/10/2025;2025NE9;360.00\n"
                "OUTRO SERVIDOR;DIARIA;19/10/2025;2025NE8;100.00\n").encode("utf-8")

    baixar_falso(monkeypatch, tratador)
    ce.coletar_diarias("s", DEPUTADOS)
    assert sorted(pedidos) == [f"{ce.DIARIAS_PAGINA}?ano=2025&export=csv", f"{ce.DIARIAS_PAGINA}?ano=2026&export=csv"]
    for ano in (2025, 2026):
        itens = json.loads((tmp_path / f"diarias_{ano}.json").read_text(encoding="utf-8"))["itens"]
        assert len(itens) == 1 and itens[0]["idDeputado"] == "agenor-neto" and itens[0]["motivo"] == "DIARIA PARA BRASILIA"
        assert itens[0]["data"] == "2025-10-19" and itens[0]["valor"] == 360.0 and itens[0]["fonte"] == f"{ce.DIARIAS_PAGINA}?ano={ano}"


def test_itens_diarias_sem_par_e_valor_invalido():
    itens, sem_par = ce.itens_diarias([{"BENEFICIARIO": "A", "DATA PAGAMENTO": "xx", "VALOR": "abc"},
                                       {"BENEFICIARIO": "B"}], {"A": "dep-a"}, 2026)
    assert sem_par == {"B"} and itens[0]["data"] is None and itens[0]["valor"] is None and itens[0]["motivo"] is None


def bloco_proposicao(numero, autor, entrada="02.02.25", ementa="Ementa", movimento="Em 02.02.25 - Leitura"):
    return ("N&ordm; do Proj.:</b></font><br><font face='Verdana'>" + numero + " </font></td>"
            "<font><b>Autor:</b></font><br><font face='Verdana'>" + autor + "</font></td>"
            "<font><b>Entrada:</b></font><br><font face='Verdana'>" + entrada + "</font></td>"
            "<font><b>Ementa:</b></font><br><font face='Verdana'><a href='http://x/" + numero.replace("/", "_") + ".htm'>" + ementa + "</a></font>"
            "<font><b>Localiza&ccedil;&atilde;o:</b></font>&nbsp;<font>LEGIS</font><br><font face='Verdana'>" + movimento + "</font>")


def test_proposicoes_da_pagina_sem_numero_e_sem_localizacao():
    html = "N&ordm; do Proj.:</b></font><br><font>sem numero</font>" + bloco_proposicao("7/25", "A").replace("Localiza", "Outro")
    itens = ce.proposicoes_da_pagina(html)
    assert len(itens) == 1 and itens[0]["numero"] == 7 and itens[0]["ano"] == 2025 and itens[0]["situacao"] is None
    assert ce.campo_proposicao("sem campo", "Autor:") == ""
    assert ce.ultima_pagina("sem paginacao") == 1


def test_coletar_proposicoes_grava_por_ano_separa_governo_e_avisa(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    fixar_hoje(monkeypatch, 2026, 11, 3)
    ultima = "<a href='x?absolutepage=2'>&Uacute;ltima</a>"
    paginas = {
        ("projeto_lei", "T", None): ultima + bloco_proposicao("10/2025", "AGENOR NETO") + bloco_proposicao("11/2025", "FULANO ALHEIO")
                                   + bloco_proposicao("5/2020", "AGENOR NETO") + bloco_proposicao("99/2099", "AGENOR NETO", entrada="03.04.25"),
        ("projeto_lei", "T", "2"): bloco_proposicao("12/2025", "AGENOR NETO, COAUTORIA: DRA. SILVANA"),
        ("projeto_lei", "D", None): bloco_proposicao("10/2025", "AGENOR NETO", movimento="EM 07.06.25 - Plenário, Aprovado"),
        ("projeto_mens", "T", None): bloco_proposicao("3/2025", "PODER EXECUTIVO"),
    }

    def tratador(url, params):
        tabela, opcao = re.search(r"tabela=(\w+)&opcao=(\w)", url).groups()
        if tabela == "projeto_indi" and opcao == "D":
            raise RuntimeError("fora do ar")
        pagina = re.search(r"absolutepage=(\d+)", url)
        return paginas.get((tabela, opcao, pagina.group(1) if pagina else None), "").encode("utf-8")

    baixar_falso(monkeypatch, tratador)
    ce.coletar_proposicoes("s", DEPUTADOS)
    materias = json.loads((tmp_path / "materias_2025.json").read_text(encoding="utf-8"))["materias"]
    assert set(materias) == {"PL-10-2025", "PL-12-2025", "PL-99-2025"}
    assert materias["PL-10-2025"]["emTramitacao"] is False and materias["PL-10-2025"]["situacao"] == "EM 07.06.25 - Plenário, Aprovado"
    assert materias["PL-10-2025"]["idsDeputados"] == ["agenor-neto"] and materias["PL-10-2025"]["dataApresentacao"] == "2025-02-02"
    assert materias["PL-12-2025"]["idsAutores"] == ["agenor-neto", "dra-silvana"] and materias["PL-12-2025"]["emTramitacao"] is True
    assert materias["PL-99-2025"]["ano"] == 2025 and materias["PL-10-2025"]["linkTexto"] == "http://x/10_2025.htm"
    governo = json.loads((tmp_path / "governo_2025.json").read_text(encoding="utf-8"))["materias"]
    assert set(governo) == {"MSG-3-2025"} and "idsDeputados" not in governo["MSG-3-2025"]
    assert not (tmp_path / "materias_2020.json").exists()
    err = avisos(capsys)
    assert "proposições projeto_indi/D: fora do ar" in err and "autores sem deputado da lista (1): ['FULANO ALHEIO']" in err


def test_coletar_proposicoes_pagina_com_falha_avisa(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    fixar_hoje(monkeypatch, 2026, 11, 3)

    def tratador(url, params):
        if "tabela=projeto_lei&opcao=T" in url and "absolutepage=2" in url:
            raise RuntimeError("página caiu")
        if "tabela=projeto_lei&opcao=T" in url:
            return ("<a href='x?absolutepage=2'>&Uacute;ltima</a>" + bloco_proposicao("1/2025", "AGENOR NETO")).encode("utf-8")
        return b""

    baixar_falso(monkeypatch, tratador)
    ce.coletar_proposicoes("s", DEPUTADOS)
    assert "proposições projeto_lei/T página 2: página caiu" in avisos(capsys)
    assert set(json.loads((tmp_path / "materias_2025.json").read_text(encoding="utf-8"))["materias"]) == {"PL-1-2025"}


def linha_contrato(**extra):
    base = {"id_contrato": 7, "especie_contrato": "CONTRATO", "contratado_contrato": "EMPRESA  X LTDA", "cpfcnpj_contrato": "47866934000174",
            "valorvencedor_contrato": "1.000,50", "objeto_contrato": "Servico  de teste", "iniciovigencia_contrato": "01/02/2025",
            "fimvigencia_contrato": "31/01/2026", "numero_contrato": "10", "ano_contrato": 2025, "aditivos": [{}, {}]}
    return {**base, **extra}


def test_tipo_orgao():
    assert ce.tipo_orgao("ATA DE REGISTRO DE PRECOS") == "ata_registro"
    assert ce.tipo_orgao("Ata  de  registro") == "ata_registro"
    assert ce.tipo_orgao("CONTRATO") == "contrato"
    assert ce.tipo_orgao(None) == "contrato"


def test_itens_do_orgao_contrato_ata_e_repeticao_por_lote():
    linhas = [linha_contrato(), linha_contrato(), linha_contrato(id_contrato=8, especie_contrato="ATA DE REGISTRO DE PRECO", cpfcnpj_contrato="123"),
              {"numero_contrato": "1"}, linha_contrato(id_contrato=None)]
    itens = ce.itens_do_orgao(linhas)
    assert len(itens) == 2
    contrato = next(i for i in itens.values() if i["idFonte"] == "7")
    ata = next(i for i in itens.values() if i["idFonte"] == "8")
    assert contrato["tipo"] == "contrato" and contrato["numero"] == "10/2025" and contrato["fornecedor"] == "EMPRESA X LTDA"
    assert contrato["cnpj"] == "47866934000174" and contrato["valor"] == 1000.5 and contrato["inicio"] == "2025-02-01" and contrato["fim"] == "2026-01-31"
    assert contrato["aditivos"] == 2 and contrato["objeto"] == "Servico de teste" and contrato["fonte"] == ce.CONTRATOS_PAGINA
    assert ata["tipo"] == "ata_registro" and ata["cnpj"] is None
    assert all(k.startswith("ctr_") for k in itens)


def test_contratos_do_ano_pagina_ate_a_ultima():
    s = SessaoJson({1: {"data": [{"id_contrato": 1}], "pagination": {"last_page": 2}}, 2: {"data": [{"id_contrato": 2}], "pagination": {"last_page": 2}}})
    assert ce.contratos_do_ano(s, 2025) == [{"id_contrato": 1}, {"id_contrato": 2}]
    assert s.pedidos == [{"ano_contrato": 2025, "page": 1}, {"ano_contrato": 2025, "page": 2}]
    assert ce.contratos_do_ano(SessaoJson({1: {"data": None}}), 2025) == []


def test_coletar_orgao_ano_encerrado_lista_vazia_e_gravacao(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    fixar_hoje(monkeypatch, 2026, 11, 3)
    (tmp_path / "orgao_2023.json").write_text('{"itens":{"a":{}}}', encoding="utf-8")
    (tmp_path / "orgao_2025.json").write_text('{"itens":{"a":{}}}', encoding="utf-8")
    pedidos = []

    def contratos(s, ano):
        pedidos.append(ano)
        return [linha_contrato()] if ano in (2024, 2026) else []

    monkeypatch.setattr(ce, "contratos_do_ano", contratos)
    ce.coletar_orgao("s")
    assert pedidos == [2024, 2025, 2026]
    assert json.loads((tmp_path / "orgao_2023.json").read_text(encoding="utf-8")) == {"itens": {"a": {}}}
    assert json.loads((tmp_path / "orgao_2025.json").read_text(encoding="utf-8")) == {"itens": {"a": {}}}
    for ano in (2024, 2026):
        gravado = json.loads((tmp_path / f"orgao_{ano}.json").read_text(encoding="utf-8"))
        assert gravado["coletadoEm"] == "2026-11-03" and len(gravado["itens"]) == 1 and gravado["fonte"] == ce.CONTRATOS_PAGINA
    assert "contratos 2025: API devolveu lista vazia" in avisos(capsys)


def test_coletar_orgao_erro_da_api_propaga(tmp_path, monkeypatch):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    fixar_hoje(monkeypatch, 2026, 11, 3)

    def contratos(s, ano):
        raise RuntimeError("API fora")

    monkeypatch.setattr(ce, "contratos_do_ano", contratos)
    with pytest.raises(RuntimeError, match="API fora"):
        ce.coletar_orgao("s")


PAGINA_VDP = ('<ul><li><a href="/atos/343.pdf">Ato Normativo 343/2024</a> (vigente)</li>'
              '<li><a href="/atos/200.pdf">Ato Normativo 200/2020</a>&nbsp;(revogado)</li>'
              '<li><a href="/atos/400.pdf">Ato sem ano</a> (vigente)</li></ul>')


def test_regras_da_vdp():
    regra = ce.regras_da_vdp(PAGINA_VDP)
    assert regra["url"] == "/atos/343.pdf" and regra["ano"] == 2024 and regra["titulo"] == "Ato Normativo 343/2024"
    assert [d["vigente"] for d in regra["documentos"]] == [True, False, True] and regra["documentos"][2]["ano"] is None
    assert ce.regras_da_vdp("<li><a href='/x.pdf'>Ato 2020</a> (revogado)</li>") is None
    assert ce.regras_da_vdp("") is None


def test_coletar_regras_grava_e_sem_vigente_levanta(tmp_path, monkeypatch):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    baixar_falso(monkeypatch, lambda url, params: PAGINA_VDP.encode("utf-8"))
    ce.coletar_regras("s")
    assert json.loads((tmp_path / "regras_ressarcimento.json").read_text(encoding="utf-8"))["ano"] == 2024
    (tmp_path / "regras_ressarcimento.json").unlink()
    baixar_falso(monkeypatch, lambda url, params: b"<html></html>")
    with pytest.raises(RuntimeError, match="nenhum normativo vigente"):
        ce.coletar_regras("s")
    assert not (tmp_path / "regras_ressarcimento.json").exists()


def modal(matricula, nome, lotacao, cargo="ASSESSOR", nivel="- DNS-3", ano=2026, mes=9):
    campos = [matricula, nome, lotacao, "EM EXERCICIO", cargo, nivel, "x", "y", str(ano), str(mes), "doc"]
    return f'<tr data-bs-remuneracao="{base64.b64encode("_".join(campos).encode("latin-1")).decode()}"></tr>'


def test_registros_pessoal_ignora_base64_invalido_e_registro_curto():
    curto = base64.b64encode(b"a_b_c").decode()
    html = modal("1", "A", "L") + f'<tr data-bs-remuneracao="{curto}"></tr><tr data-bs-remuneracao="@@@"></tr>'
    registros = ce.registros_pessoal(html)
    assert len(registros) == 1 and registros[0][:3] == ["1", "A", "L"] and registros[0][8:10] == ["2026", "9"]


def test_ultima_pagina_pessoal():
    assert ce.ultima_pagina_pessoal('<a href="?mes=09&amp;ano=2026&amp;page=3">3</a><a href="?page=12">') == 12
    assert ce.ultima_pagina_pessoal("sem links") == 1


def test_servidores_do_gabinete_liga_deputado_id_estavel_e_ordena():
    registros = ce.registros_pessoal(
        modal("20", "Maria  Souza", "GABINETE DEPUTADO AGENOR NETO", cargo="CHEFE", nivel="- DNS-1")
        + modal("10", "Joao Lima", "GABINETE DEPUTADA DRA. SILVANA", nivel="")
        + modal("30", "Ana Alheia", "GABINETE DEPUTADO FULANO INEXISTENTE")
        + modal("40", "Beto Diretoria", "DIRETORIA ADMINISTRATIVA")
        + modal("20", "Maria  Souza", "GABINETE DEPUTADO AGENOR NETO", cargo="CHEFE", nivel="- DNS-1"))
    itens = ce.servidores_do_gabinete(registros, DEPUTADOS)
    assert [i["matricula"] for i in itens] == ["20", "10"]
    assert itens[0] == {"idDeputado": "agenor-neto", "matricula": "20", "nome": "Maria Souza", "simbolo": "DNS-1", "cargo": "CHEFE"}
    assert itens[1]["idDeputado"] == "dra-silvana" and itens[1]["simbolo"] == "ASSESSOR"
    assert ce.servidores_do_gabinete(registros, []) == []


def gabinete_paginas(mes=9):
    p1 = '<a href="?page=2">2</a>' + modal("20", "Maria Souza", "GABINETE DEPUTADO AGENOR NETO", mes=mes)
    p2 = modal("10", "Joao Lima", "GABINETE DEPUTADA DRA. SILVANA", mes=mes) + modal("40", "Beto", "DIRETORIA", mes=mes)

    def tratador(url, params):
        if params is None:
            return modal("1", "Sem", "DIRETORIA", mes=mes).encode("latin-1")
        assert params["mes"] == f"{mes:02d}" and params["ano"] == 2026
        return (p1 if params["page"] == 1 else p2).encode("latin-1")

    return tratador


def test_coletar_gabinete_pagina_e_grava(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    fixar_hoje(monkeypatch, 2026, 11, 3)
    baixar_falso(monkeypatch, gabinete_paginas())
    ce.coletar_gabinete("s", DEPUTADOS)
    gravado = json.loads((tmp_path / "gabinete.json").read_text(encoding="utf-8"))
    assert gravado["ano"] == 2026 and gravado["mes"] == 9 and gravado["coletadoEm"] == "2026-11-03"
    assert gravado["fonte"] == f"{ce.PESSOAL_PAGINA}?mes=09&ano=2026"
    assert {i["idDeputado"] for i in gravado["itens"]} == {"agenor-neto", "dra-silvana"} and len(gravado["itens"]) == 2
    assert "gabinetes 2 servidores de 2 deputados (09/2026)" in capsys.readouterr().out


def test_coletar_gabinete_mes_ja_coletado_recente_nao_rele(tmp_path, monkeypatch):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    fixar_hoje(monkeypatch, 2026, 11, 3)
    (tmp_path / "gabinete.json").write_text(json.dumps({"ano": 2026, "mes": 9, "coletadoEm": "2026-10-20", "itens": [{"x": 1}]}), encoding="utf-8")
    pedidos = []
    tratador = gabinete_paginas()
    baixar_falso(monkeypatch, lambda url, params: pedidos.append(params) or tratador(url, params))
    ce.coletar_gabinete("s", DEPUTADOS)
    assert pedidos == [None]
    assert json.loads((tmp_path / "gabinete.json").read_text(encoding="utf-8"))["itens"] == [{"x": 1}]


def test_coletar_gabinete_foto_velha_ou_mes_novo_rele(tmp_path, monkeypatch):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    fixar_hoje(monkeypatch, 2026, 11, 3)
    baixar_falso(monkeypatch, gabinete_paginas())
    (tmp_path / "gabinete.json").write_text(json.dumps({"ano": 2026, "mes": 9, "coletadoEm": "2026-09-01", "itens": []}), encoding="utf-8")
    ce.coletar_gabinete("s", DEPUTADOS)
    assert json.loads((tmp_path / "gabinete.json").read_text(encoding="utf-8"))["coletadoEm"] == "2026-11-03"
    (tmp_path / "gabinete.json").write_text(json.dumps({"ano": 2026, "mes": 8, "coletadoEm": "2026-11-02", "itens": []}), encoding="utf-8")
    ce.coletar_gabinete("s", DEPUTADOS)
    assert json.loads((tmp_path / "gabinete.json").read_text(encoding="utf-8"))["mes"] == 9


def test_coletar_gabinete_sem_registros_ou_sem_servidor_ligado_mantem_arquivo(tmp_path, monkeypatch):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    fixar_hoje(monkeypatch, 2026, 11, 3)
    (tmp_path / "gabinete.json").write_text('{"itens":[1]}', encoding="utf-8")
    baixar_falso(monkeypatch, lambda url, params: b"<html></html>")
    with pytest.raises(RuntimeError, match="sem registros"):
        ce.coletar_gabinete("s", DEPUTADOS)
    baixar_falso(monkeypatch, gabinete_paginas())
    with pytest.raises(RuntimeError, match="nenhum servidor ligado"):
        ce.coletar_gabinete("s", [{"id": "outro", "nome": "Outro Nome", "nomeCivil": "Outro Nome Civil"}])
    assert json.loads((tmp_path / "gabinete.json").read_text(encoding="utf-8")) == {"itens": [1]}


def test_coletar_votacoes_ja_lida_nao_baixa_e_xlsx_invalido_avisa(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    lista_html = amostra("estadual_ce_votacoes_lista")["html"] + "</td></tr>"
    lista = ce.votacoes_da_pagina(lista_html)
    (tmp_path / "votacoes.json").write_text(json.dumps({"votacoes": {lista[0]["id"]: {"sim": 1}}}), encoding="utf-8")
    baixados = []

    def xlsx_linhas(conteudo):
        raise ValueError("xlsx quebrado")

    monkeypatch.setattr(ce.comum, "xlsx_linhas", xlsx_linhas)
    baixar_falso(monkeypatch, lambda url, params: baixados.append(url) or (lista_html.encode("utf-8") if url == ce.VOTACOES_URL else b"x"))
    ce.coletar_votacoes("s", DEPUTADOS)
    assert lista[0]["xlsx"] not in baixados and lista[1]["xlsx"] in baixados
    assert f"CE: votação {lista[1]['id']}: xlsx quebrado" in avisos(capsys)
    votacoes = json.loads((tmp_path / "votacoes.json").read_text(encoding="utf-8"))["votacoes"]
    assert votacoes == {lista[0]["id"]: {"sim": 1}}


def test_coletar_votacoes_pagina_sem_materias_levanta(tmp_path, monkeypatch):
    monkeypatch.setattr(ce, "PASTA", tmp_path)
    with pytest.raises(RuntimeError, match="sem matérias"):
        ce.coletar_votacoes(SessaoFalsa({ce.VOTACOES_URL: "<html></html>"}), DEPUTADOS)


ETAPAS_CE = ["coletar_vdp", "coletar_votacoes", "coletar_proposicoes", "coletar_remuneracao", "coletar_diarias", "coletar_orgao", "coletar_regras",
             "coletar_gabinete"]


def test_coletar_roda_etapas_na_ordem_e_isola_erro(monkeypatch, capsys):
    chamadas = []
    monkeypatch.setattr(ce.comum, "sessao", lambda: "sessao")
    monkeypatch.setattr(ce, "coletar_deputados", lambda s: chamadas.append(("deputados", s)) or ["dep"])
    for nome in ETAPAS_CE:
        def etapa(*args, nome=nome):
            chamadas.append((nome, args))
            if nome == "coletar_votacoes":
                raise RuntimeError("votações fora")

        monkeypatch.setattr(ce, nome, etapa)
    ce.coletar()
    assert [c[0] for c in chamadas] == ["deputados"] + ETAPAS_CE
    assert chamadas[1] == ("coletar_vdp", ("sessao", ["dep"])) and chamadas[6] == ("coletar_orgao", ("sessao",))
    assert "CE: votações: votações fora" in avisos(capsys)


def test_coletar_sem_deputados_nao_roda_etapas(monkeypatch):
    chamadas = []
    monkeypatch.setattr(ce.comum, "sessao", lambda: "sessao")

    def sem_deputados(s):
        raise RuntimeError("página de deputados sem cartões")

    monkeypatch.setattr(ce, "coletar_deputados", sem_deputados)
    monkeypatch.setattr(ce, "coletar_vdp", lambda *a: chamadas.append("vdp"))
    with pytest.raises(RuntimeError, match="sem cartões"):
        ce.coletar()
    assert chamadas == []
