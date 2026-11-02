import json
from datetime import date

import pytest

import coletar_estadual_se as se
import estaduais_comum as comum
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"


def amostra(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


def test_deputados_da_pagina_do_contrato():
    deputados = se.deputados_da_pagina(amostra("estadual_se_deputados")["trecho"])
    assert len(deputados) == 3
    d = deputados[0]
    assert d["id"].isdigit() and d["nome"] and d["partido"] and d["foto"].startswith("https://")
    assert d["fonte"] == se.FICHA.format(d["id"]) and d["titular"] is True and d["email"] is None


def test_conferir_contrato_deputados():
    assert se._conferir_deputados(amostra("estadual_se_deputados")) == ([], [])
    falhas, _ = se._conferir_deputados({"trecho": "<html></html>"})
    assert falhas


def test_cartao_repetido_conta_uma_vez():
    cartao = ('<article class="qodef-portfolio-item mix"><a href="https://aleselegis.al.se.leg.br/spl/parlamentar.aspx?id=7"><img src="https://x/f.jpg"></a>'
              '<h4 class="qodef-item-title"><a href="x"> Fulano </a></h4><div class="qodef-ptf-category-holder"><span>PT</span></div></article>')
    deputados = se.deputados_da_pagina(cartao + cartao)
    assert [d["id"] for d in deputados] == ["7"] and deputados[0]["nome"] == "Fulano" and deputados[0]["partido"] == "PT"


def test_completar_com_tse_preenche_nome_civil_quando_um_so_casa():
    deputados = [{"nome": "Carminha Paiva", "nomeCivil": "Carminha Paiva"}, {"nome": "Luizão Donatrampi", "nomeCivil": "Luizão Donatrampi"},
                 {"nome": "Paulo Júnior", "nomeCivil": "Paulo Júnior"}, {"nome": "Kitty Lima", "nomeCivil": "Kitty Lima"},
                 {"nome": "Luciano Silva", "nomeCivil": "Luciano Silva"}]
    eleitos = [{"urna": "Carminha", "nome": "Maria do Carmo Paiva da Silva"}, {"urna": "Luizao Dona Trampi", "nome": "Jose Luiz da Mota Cruz"},
               {"urna": "Paulo Jr", "nome": "Paulo Roberto de Santana Junior"}, {"urna": "Luciano Bispo", "nome": "Luciano Bispo de Lima"},
               {"urna": "Luciano Pimentel", "nome": "Luciano Azevedo Pimentel"}]
    se.completar_com_tse(deputados, eleitos)
    assert [d["nomeCivil"] for d in deputados] == ["Maria do Carmo Paiva da Silva", "Jose Luiz da Mota Cruz", "Paulo Roberto de Santana Junior",
                                                    "Kitty Lima", "Luciano Silva"]


def test_coletar_grava_deputados(tmp_path, monkeypatch):
    html = amostra("estadual_se_deputados")["trecho"]

    class Resp:
        text = html

        def raise_for_status(self):
            pass

    class Sessao:
        def get(self, url, timeout=None):
            return Resp()

    eleitos = [{"cargo": "DEPUTADO ESTADUAL", "situacao": "eleito", "urna": "Adailton Martins", "nome": "Adailton Martins de Oliveira Filho"}]
    (tmp_path / "SE.json").write_text(json.dumps(eleitos), encoding="utf-8")
    monkeypatch.setattr(se, "TSE_ARQUIVO", tmp_path / "SE.json")
    monkeypatch.setattr(comum, "DADOS", tmp_path)
    monkeypatch.setattr(comum, "sessao", Sessao)
    for etapa in ("coletar_ressarcimento", "coletar_folha", "coletar_contratos"):
        monkeypatch.setattr(se, etapa, lambda *a, **k: None)
    se.coletar()
    info = json.loads((tmp_path / "SE" / "deputados.json").read_text(encoding="utf-8"))
    assert info["host"] is None and info["fonte"] == se.HOME and len(info["deputados"]) == 3
    assert any(d["nomeCivil"] == "Adailton Martins de Oliveira Filho" for d in info["deputados"])


DEPUTADOS = [{"id": "545", "nome": "Adailton Martins", "nomeCivil": "Adailton Martins de Oliveira Filho"},
             {"id": "562", "nome": "Áurea Ribeiro", "nomeCivil": "Josefa Aurea de Souza Ribeiro"},
             {"id": "574", "nome": "Pato Maravilha", "nomeCivil": "Carlos Alexandre Santos Costa"},
             {"id": "572", "nome": "Neto Batalha", "nomeCivil": "José Batalha de Goes Neto"},
             {"id": "548", "nome": "Ibrain de Valmir", "nomeCivil": "Ibrain Silva Monteiro"}]
ARQ = {"ano": 2026, "mes": 1, "id": "186576", "slug": "ressarcimento-dos-deputados-120"}


def test_arquivos_da_pagina_usa_o_rotulo_da_aba_e_o_ano():
    achados = se.arquivos_da_pagina(amostra("estadual_se_ressarcimento")["html"])
    assert achados == [{"ano": 2026, "mes": 1, "id": "186576", "slug": "ressarcimento-dos-deputados-120"},
                       {"ano": 2026, "mes": 2, "id": "186680", "slug": "ressarcimento-dos-deputados-121"}]
    assert se.url_pdf(achados[0]) == "https://al.se.leg.br/download/ressarcimento-dos-deputados-120/?wpdmdl=186576"


def test_blocos_ressarcimento_do_contrato():
    pagamento, blocos = se.blocos_ressarcimento(amostra("estadual_se_ressarcimento")["linhas"])
    assert pagamento == (2026, 1)
    assert blocos[0]["deputado"] == "Adailton Martins" and blocos[0]["competencia"] == (2025, 12) and blocos[0]["total"] == 44384.63
    assert [v for _, v in blocos[0]["itens"]] == [27210.0, 4174.63, 13000.0]
    assert blocos[0]["itens"][0][0] == "Art. 4º I - Contratação de assessoria e consultoria"
    assert se._conferir_ressarcimento(amostra("estadual_se_ressarcimento")) == ([], [])


def test_ressarcimento_sem_r_cifrao_e_bloco_que_nao_fecha(capsys):
    linhas = ["Mês/Ano de Pagamento: 03/2023", "Deputado: Adailton Martins", "Competência: 02/2023",
              "1 Art. 4º I - Contratação de assessoria e consultoria 30.210,00", "2 Art. 4º VI - Locação de veículos automotores 9.300,00",
              "Total: 39.510,00", "Deputado: Áurea Ribeiro", "Competência: 02/2023", "3 Art. 4º I - Contratação de assessoria e consultoria 15.000,00",
              "Total: 20.000,00"]
    pagamento, blocos = se.blocos_ressarcimento(linhas)
    assert pagamento == (2023, 3) and [b["deputado"] for b in blocos] == ["Adailton Martins"]
    assert "Áurea Ribeiro descartado" in capsys.readouterr().err


def test_itens_ressarcimento_liga_e_confere_o_mes():
    itens = se.itens_ressarcimento(amostra("estadual_se_ressarcimento")["linhas"], ARQ, DEPUTADOS)
    assert {i["idDeputado"] for i in itens} == {"545", "562"}
    primeiro = itens[0]
    assert primeiro["mes"] == 1 and primeiro["competencia"] == "2025-12" and primeiro["valor"] == 27210.0 and primeiro["fornecedor"] is None
    assert primeiro["fonte"] == se.url_pdf(ARQ) and primeiro["pdf"] == "186576"
    with pytest.raises(RuntimeError, match="a aba diz 2026-02"):
        se.itens_ressarcimento(amostra("estadual_se_ressarcimento")["linhas"], {**ARQ, "mes": 2}, DEPUTADOS)


def test_servidores_da_folha_do_contrato():
    referencia, servidores = se.servidores_da_folha(amostra("estadual_se_folha")["linhas"])
    assert referencia == (2026, 1) and len(servidores) == 4
    adailton = servidores[0]
    assert adailton["matricula"] == "012746" and adailton["admissao"] == "2019-02-01" and adailton["cargo"] == "Deputado"
    assert (adailton["bruto"], adailton["descontos"], adailton["liquido"]) == (46407.03, 11697.13, 34709.9)
    assert adailton["lotacao"] == "GABINETE DO DEPUTADO ADAILTON MARTINS"
    assert se._conferir_folha(amostra("estadual_se_folha")) == ([], [])


def test_folha_lotacao_quebrada_em_varias_linhas():
    linhas = ["DETALHAMENTO DA FOLHA DE PAGAMENTO", "Referente a:", "JANEIRO/2026",
              "000587 JADSON MOYSES ARAUJO SALES 5.637,428.146,91 0,00 0,00 0,0027/05/1988", "COORDENADORIA GERAL DE ", "PAGAMENTO DE PESSOAL - ",
              "COGEPAG", "0,00 0,00 0,00 2.576,90 16.361,23 1.804,34 3.685,96 5.490,30 10.870,93Técnico Legislativo",
              "Página 3", "000588 JADSON SANTOS ALVES 4.718,488.146,91 0,00 0,00 0,0002/02/1987 CEDIDOS 0,00 0,00 0,00 1.408,33 14.273,72 1.801,15 "
              "2.133,93 3.935,08 10.338,64Técnico Legislativo"]
    referencia, servidores = se.servidores_da_folha(linhas)
    assert referencia == (2026, 1)
    assert servidores[0]["lotacao"] == "COORDENADORIA GERAL DE PAGAMENTO DE PESSOAL - COGEPAG" and servidores[0]["liquido"] == 10870.93
    assert servidores[1]["lotacao"] == "CEDIDOS"


def test_folha_descarta_linha_cujos_totais_nao_fecham():
    linha = ("000588 JADSON SANTOS ALVES 4.718,488.146,91 0,00 0,00 0,0002/02/1987 CEDIDOS 0,00 0,00 0,00 1.408,33 14.273,72 1.801,15 "
             "2.133,93 3.935,08 10.000,00Técnico Legislativo")
    assert se.servidores_da_folha(["JANEIRO/2026", linha])[1] == []


def test_remuneracao_dos_deputados_liga_por_nome_civil_ou_lotacao():
    _, servidores = se.servidores_da_folha(amostra("estadual_se_folha")["linhas"])
    itens = se.itens_remuneracao(servidores, {"ano": 2026, "mes": 1, "id": "184481", "slug": "subsidios-e-remunera"}, DEPUTADOS)
    assert [(i["idDeputado"], i["mes"], i["bruto"], i["liquido"]) for i in itens] == [("545", 1, 46407.03, 34709.9), ("574", 1, 46407.03, 34762.04)]
    assert itens[0]["componentes"] == {"descontos": 11697.13} and itens[0]["fonte"].endswith("?wpdmdl=184481")


def test_gabinete_repara_palavra_partida_e_exclui_o_deputado():
    _, servidores = se.servidores_da_folha(amostra("estadual_se_folha")["linhas"])
    itens = se.servidores_do_gabinete(servidores, DEPUTADOS)
    assert [(i["idDeputado"], i["matricula"], i["nome"]) for i in itens] == [("548", "002333", "Adelson Rosendo Lima Ribeiro"),
                                                                           ("572", "005911", "Adeildo Laurentino da Silva")]
    assert itens[1]["cargo"] == "COM - AUXILIAR DE GABINETE PARLAMENTAR" and itens[1]["id"].startswith("srv_")
    assert itens[1]["id"] == se.servidores_do_gabinete(servidores, DEPUTADOS)[1]["id"]


def test_itens_contratos_do_contrato_com_links():
    html = amostra("estadual_se_contratos")["html"]
    assert se.anos_da_pagina(html) == [2026]
    itens = se.itens_contratos(html, 2026)
    assert len(itens) == 3 and all(k.startswith("ctr_") for k in itens)
    primeiro = next(iter(itens.values()))
    assert primeiro["tipo"] == "contrato" and primeiro["fornecedor"] is None and primeiro["objeto"].startswith("1 Aditivo ao Contarto n 066 2024")
    assert primeiro["arquivos"][0]["url"].endswith("/?wpdmdl=191473") and primeiro["idFonte"].startswith("1-aditivo-ao-contarto")
    assert se.itens_contratos(html, 2025) == {}
    assert se._conferir_contratos(amostra("estadual_se_contratos")) == ([], [])


def test_ata_de_registro_de_precos_pelo_titulo():
    html = ('<h2 class="elementor-heading-title elementor-size-default">2025</h2>'
            '<h3 class="package-title"><a href=\'https://al.se.leg.br/download/ata-1/\'>1 Aditivo Ata Registro de Precos n 01 2024 Alldoc</a></h3>'
            '<a data-downloadurl="https://al.se.leg.br/download/ata-1/?wpdmdl=9&#038;refresh=x">Download</a>')
    (item,) = se.itens_contratos(html, 2025).values()
    assert item["tipo"] == "ata_registro" and item["arquivos"][0]["url"] == "https://al.se.leg.br/download/ata-1/?wpdmdl=9"


def fingir_pdfs(monkeypatch, paginas, pdfs):
    chamadas = []
    monkeypatch.setattr(se, "buscar_pagina", lambda s, slug: (paginas[slug], "2026-04-08T09:35:54"))
    monkeypatch.setattr(se, "baixar_pdf", lambda s, arquivo: chamadas.append(arquivo["id"]) or pdfs[arquivo["id"]])
    return chamadas


def test_ressarcimento_incremental(tmp_path, monkeypatch):
    html = amostra("estadual_se_ressarcimento")["html"]
    linhas = amostra("estadual_se_ressarcimento")["linhas"]
    outro = [l.replace("01/2026", "02/2026") for l in linhas]
    chamadas = fingir_pdfs(monkeypatch, {"ressarcimento-dos-deputados": html}, {"186576": linhas, "186680": outro})
    monkeypatch.setattr(se, "PRIMEIRO_ANO", 2026)
    se.coletar_ressarcimento(object(), tmp_path, DEPUTADOS, date(2026, 6, 1))
    envelope = json.loads((tmp_path / "verbas_2026.json").read_text(encoding="utf-8"))
    assert chamadas == ["186576", "186680"] and envelope["pdfs"] == {"186576": 1, "186680": 2}
    assert {i["mes"] for i in envelope["itens"]} == {1, 2} and envelope["completaEm"] == "2026-06-01"
    se.coletar_ressarcimento(object(), tmp_path, DEPUTADOS, date(2026, 6, 2))
    assert chamadas == ["186576", "186680"]
    se.coletar_ressarcimento(object(), tmp_path, DEPUTADOS, date(2026, 6, 20))
    assert chamadas == ["186576", "186680"]


def test_ressarcimento_pdf_com_mes_diferente_da_aba_nao_entra(tmp_path, monkeypatch, capsys):
    html = amostra("estadual_se_ressarcimento")["html"]
    linhas = amostra("estadual_se_ressarcimento")["linhas"]
    fingir_pdfs(monkeypatch, {"ressarcimento-dos-deputados": html}, {"186576": linhas, "186680": linhas})
    monkeypatch.setattr(se, "PRIMEIRO_ANO", 2026)
    se.coletar_ressarcimento(object(), tmp_path, DEPUTADOS, date(2026, 6, 1))
    envelope = json.loads((tmp_path / "verbas_2026.json").read_text(encoding="utf-8"))
    assert envelope["pdfs"] == {"186576": 1} and "a aba diz 2026-02" in capsys.readouterr().err


def test_ano_encerrado_nao_e_baixado_de_novo(tmp_path, monkeypatch):
    html = amostra("estadual_se_ressarcimento")["html"].replace(">2026<", ">2023<")
    (tmp_path / "verbas_2023.json").write_text("{}", encoding="utf-8")
    chamadas = fingir_pdfs(monkeypatch, {"ressarcimento-dos-deputados": html}, {})
    monkeypatch.setattr(se, "PRIMEIRO_ANO", 2023)
    se.coletar_ressarcimento(object(), tmp_path, DEPUTADOS, date(2026, 6, 1))
    assert chamadas == [] and (tmp_path / "verbas_2023.json").read_text(encoding="utf-8") == "{}"


def test_folha_grava_remuneracao_e_gabinete_do_ultimo_pdf(tmp_path, monkeypatch):
    html = amostra("estadual_se_folha")["html"]
    linhas = amostra("estadual_se_folha")["linhas"]
    fevereiro = [l.replace("JANEIRO/2026", "FEVEREIRO/2026") for l in linhas]
    chamadas = fingir_pdfs(monkeypatch, {"subsidio-e-remuneracoes": html}, {"184481": linhas, "186255": fevereiro})
    monkeypatch.setattr(se, "PRIMEIRO_ANO_FOLHA", 2026)
    se.coletar_folha(object(), tmp_path, DEPUTADOS, date(2026, 6, 1))
    rem = json.loads((tmp_path / "remuneracao_2026.json").read_text(encoding="utf-8"))
    assert rem["pdfs"] == {"184481": 1, "186255": 2}
    assert sorted((i["idDeputado"], i["mes"]) for i in rem["itens"]) == [("545", 1), ("545", 2), ("574", 1), ("574", 2)]
    gab = json.loads((tmp_path / "gabinete.json").read_text(encoding="utf-8"))
    assert gab["pdf"] == "186255" and gab["referencia"] == "2026-02" and len(gab["itens"]) == 2
    se.coletar_folha(object(), tmp_path, DEPUTADOS, date(2026, 6, 2))
    assert chamadas == ["184481", "186255"]


def test_contratos_por_ano_so_quando_a_pagina_mudou(tmp_path, monkeypatch):
    html = amostra("estadual_se_contratos")["html"]
    monkeypatch.setattr(se, "PRIMEIRO_ANO", 2026)
    monkeypatch.setattr(se, "buscar_pagina", lambda s, slug: (html, "2026-07-13T10:00:00"))
    se.coletar_contratos(object(), tmp_path, date(2026, 8, 1))
    envelope = json.loads((tmp_path / "orgao_2026.json").read_text(encoding="utf-8"))
    assert len(envelope["itens"]) == 3 and envelope["modificadoEm"] == "2026-07-13T10:00:00"
    envelope["itens"] = {}
    (tmp_path / "orgao_2026.json").write_text(json.dumps(envelope), encoding="utf-8")
    se.coletar_contratos(object(), tmp_path, date(2026, 8, 2))
    assert json.loads((tmp_path / "orgao_2026.json").read_text(encoding="utf-8"))["itens"] == {}
    monkeypatch.setattr(se, "buscar_pagina", lambda s, slug: (html, "2026-08-01T10:00:00"))
    se.coletar_contratos(object(), tmp_path, date(2026, 8, 3))
    assert len(json.loads((tmp_path / "orgao_2026.json").read_text(encoding="utf-8"))["itens"]) == 3


def test_contratos_do_modulo():
    assert [c["nome"] for c in se.CONTRATOS] == [f"estadual_se_{x}" for x in ("deputados", "ressarcimento", "folha", "contratos")]
    for c in se.CONTRATOS:
        assert c["fonte"].startswith("https://al.se.leg.br") and callable(c["buscar"]) and callable(c["html"])
        assert (FIX / f"{c['nome']}.json").exists()
