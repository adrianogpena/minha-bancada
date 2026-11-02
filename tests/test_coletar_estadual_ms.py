import json

import coletar_estadual_ms as ms
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"

DEPUTADOS = [
    {"id": "1", "nome": "Roberto Hashioka", "nomeCivil": "Roberto Hashioka Soler"},
    {"id": "2", "nome": "Coronel David", "nomeCivil": "Carlos Alberto David dos Santos"},
    {"id": "3", "nome": "Pedrossian Neto", "nomeCivil": "Pedro Pedrossian Neto"},
    {"id": "4", "nome": "Zeca do Pt", "nomeCivil": "José Orcírio Miranda dos Santos"},
]


def amostra(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


def test_contratos_registrados():
    assert [c["nome"] for c in ms.CONTRATOS] == ["estadual_ms_ceap", "estadual_ms_diarias", "estadual_ms_pauta", "estadual_ms_ordem_do_dia",
                                                  "estadual_ms_portal", "estadual_ms_folha"]
    for c in ms.CONTRATOS:
        falhas, _ = c["html"](amostra(c["nome"]))
        assert falhas == [], c["nome"]


def test_ligar_apelidos_e_prefixo_sem_espaco():
    nomes = ["DEP. HASHIOKA", "Dep. Cel. David", "Dep.Pedrossian Neto", "Dep. Zeca do PT", "Dep. Fulano"]
    assert ms.ligar(nomes, DEPUTADOS) == {"DEP. HASHIOKA": "1", "Dep. Cel. David": "2", "Dep.Pedrossian Neto": "3", "Dep. Zeca do PT": "4"}


def test_linhas_csv_pula_metadados():
    linhas = ms.linhas_csv(amostra("estadual_ms_ceap")["csv"], "DEPUTADO")
    assert linhas and linhas[0]["DEPUTADO"] == "DEP. HASHIOKA" and "VALOR (R$)" in linhas[0]


def test_itens_ceap():
    linhas = ms.linhas_csv(amostra("estadual_ms_ceap")["csv"], "DEPUTADO")
    ligacao = ms.ligar({linha["DEPUTADO"] for linha in linhas}, DEPUTADOS)
    itens, sem_par = ms.itens_ceap(linhas, ligacao, "http://pagina")
    assert itens[0]["idDeputado"] == "1" and itens[0]["mes"] == 1 and itens[0]["valor"] == 99.9
    assert itens[0]["cnpj"] == "16551514000175" and itens[0]["emissao"] == "2026-01-10"
    assert itens[0]["fonte"].startswith("http://www.transparencia.al.ms.gov.br/arquivo/") and itens[0]["fonte"].endswith(".pdf")
    assert sem_par == set()


def test_sem_par_e_sem_comprovante():
    itens, sem_par = ms.itens_ceap([{"DEPUTADO": "Dep. Fulano", "VALOR (R$)": "R$ 1,00"},
                                    {"DEPUTADO": "DEP. HASHIOKA", "MES": "Março", "VALOR (R$)": "R$ 1.000,50", "COMPROVANTE": ""}],
                                   {"DEP. HASHIOKA": "1"}, "http://pagina")
    assert sem_par == {"Fulano"}
    assert itens == [{"idDeputado": "1", "mes": 3, "categoria": None, "fornecedor": None, "cnpj": None, "valor": 1000.5,
                      "documento": None, "emissao": None, "fonte": "http://pagina"}]


def test_diarias_sem_despesa():
    assert ms.linhas_diarias(amostra("estadual_ms_diarias")["csv"]) == []
    texto = "Mês;Ano;Informação\nJaneiro;2024;Viagem a Brasília\nFevereiro;2024;\"Não houve despesa com a concessão de diárias nesse período.\"\n"
    assert [linha["MES"] for linha in ms.linhas_diarias(texto)] == ["Janeiro"]


def test_emissao_iso():
    assert ms.emissao_iso("10/01/2026") == "2026-01-10"
    assert ms.emissao_iso("") is None


DEPUTADOS_PAUTA = [
    {"id": "10", "nome": "Antonio Vaz", "nomeCivil": "Antonio Vaz"},
    {"id": "11", "nome": "Caravina", "nomeCivil": "Carlos Caravina"},
    {"id": "12", "nome": "Roberto Hashioka", "nomeCivil": "Roberto Hashioka Soler"},
    {"id": "13", "nome": "Londres Machado", "nomeCivil": "Londres Machado"},
]


def test_pauta_com_prazo_de_emendas_e_autores():
    blocos = ms.ler_pagina(amostra("estadual_ms_pauta")["html"])
    primeiro = blocos[0]
    assert primeiro["prazoEmendas"] == "2026-10-29" and "ART. 206" in primeiro["titulo"]
    assert [(p["tipo"], p["numero"], p["processo"], p["autor"]) for p in primeiro["processos"]] == [
        ("Projeto de Lei", "151", "289/2026", "Deputado ANTONIO VAZ"), ("Projeto de Resolução", "119", "285/2026", "Deputado CARAVINA")]
    assert primeiro["processos"][0]["ementa"].startswith("Declara de Utilidade Pública")
    assert any(p["autor"] == "PODER EXECUTIVO" for b in blocos for p in b["processos"])


def test_ordem_do_dia_com_fase_e_link_do_projeto():
    blocos = ms.ler_pagina(amostra("estadual_ms_ordem_do_dia")["html"])
    assert len(blocos) == 1 and blocos[0]["sessao"] == "2026-10-28"
    assert [(p["numero"], p["fase"]) for p in blocos[0]["processos"]] == [("354", "2ª Discussão"), ("047", "2ª Discussão"), ("268", "1ª Discussão")]
    assert blocos[0]["processos"][0]["fonte"].endswith("idProposicao=319861")


def test_itens_da_pagina_ligam_so_deputado():
    html = amostra("estadual_ms_pauta")["html"]
    itens = ms.itens_da_pagina(ms.ler_pagina(html), ms.PAUTA_PAGINA, DEPUTADOS_PAUTA)
    chave = "pauta|Período de pauta em discussão única (ART. 206 DO RIAL)|2026-10-29"
    assert itens[chave]["idsDeputados"] == ["10", "11"] and itens[chave]["data"] is None and itens[chave]["tipo"] == "pauta"
    executivo = [p for i in itens.values() for p in i["processos"] if p["autor"] == "PODER EXECUTIVO"]
    assert executivo and all(p["idsDeputados"] == [] for p in executivo)
    ordem = ms.itens_da_pagina(ms.ler_pagina(amostra("estadual_ms_ordem_do_dia")["html"]), ms.ORDEM_PAGINA, DEPUTADOS_PAUTA)
    assert ordem["ordem-do-dia|2026-10-28"]["idsDeputados"] == ["12"] and ordem["ordem-do-dia|2026-10-28"]["data"] == "2026-10-28"


def test_coletar_pautas_junta_com_o_que_ja_foi_guardado(monkeypatch, tmp_path):
    monkeypatch.setattr(ms, "PASTA", tmp_path)
    paginas = {ms.PAUTA_PAGINA: amostra("estadual_ms_pauta")["html"], ms.ORDEM_PAGINA: amostra("estadual_ms_ordem_do_dia")["html"]}
    monkeypatch.setattr(ms, "baixar_html", lambda s, url: paginas[url])
    antigo = {"id": "2026-10-27", "tipo": "ordem-do-dia", "data": "2026-10-27", "prazoEmendas": None}
    (tmp_path / "pautas_2026.json").write_text(json.dumps({"itens": {"ordem-do-dia|2026-10-27": antigo}}), encoding="utf-8")
    ms.coletar_pautas(None, DEPUTADOS_PAUTA)
    itens = json.loads((tmp_path / "pautas_2026.json").read_text(encoding="utf-8"))["itens"]
    assert "ordem-do-dia|2026-10-27" in itens and "ordem-do-dia|2026-10-28" in itens and len(itens) == 6


def linhas_folha():
    return amostra("estadual_ms_folha")["texto"].split("\n")


def test_folha_do_pdf_fecha_a_conta():
    referencia, folha, deputados = ms.folha_do_pdf(linhas_folha())
    assert referencia == (2026, 9) and folha == "Deputado Estadual"
    assert [d["ok"] for d in deputados] == [True, True, True]
    primeiro = deputados[0]
    assert primeiro["nome"] == "LONDRES MACHADO" and primeiro["matricula"] == "01-000150"
    assert primeiro["creditos"] == {"SUBSÍDIO": 34774.64, "PLANO DE ASSIST. MEDICO-SOCIAL": 13425.82}
    assert primeiro["debitos"]["INSS"] == 988.09 and primeiro["totalDebito"] == 9492.39 and primeiro["liquido"] == 38708.07


def test_folha_conta_que_nao_fecha_nao_vira_dado():
    texto = amostra("estadual_ms_folha")["texto"].replace("38.708,07", "38.708,00").split("\n")
    _, _, deputados = ms.folha_do_pdf(texto)
    assert [d["ok"] for d in deputados] == [False, False, True]


def test_folha_com_subtotal_partido_em_duas_linhas():
    linhas = ["Referência : Junho/2024   Folha : Deputado Estadual", "ZECA TESTE" + " " * 60 + "01-000999", "",
              "    Evento" + " " * 40 + "Crédito" + " " * 20 + "Débito",
              "    SUBSÍDIO" + " " * 40 + "100,00", "    INSS" + " " * 70 + "10,00",
              "    FAP/UNALE - 35ª CHAMADA DO" + " " * 50 + "5,00", "    FAP  Sub Total >>>" + " " * 60 + "85,00",
              " " * 50 + "100,00" + " " * 21 + "15,00"]
    referencia, _, deputados = ms.folha_do_pdf(linhas)
    assert referencia == (2024, 6) and deputados[0]["ok"] and "FAP/UNALE - 35ª CHAMADA DO FAP" in deputados[0]["debitos"]


def test_itens_remuneracao_liga_pelo_nome():
    _, _, pdf = ms.folha_do_pdf(linhas_folha())
    arquivo = {"mes": 9, "id": "abc", "url": "https://x/uploads/abc.pdf"}
    itens = ms.itens_remuneracao(pdf, arquivo, DEPUTADOS_PAUTA)
    assert [i["idDeputado"] for i in itens] == ["13"]
    assert itens[0]["bruto"] == 48200.46 and itens[0]["liquido"] == 38708.07 and itens[0]["fonte"] == "https://x/uploads/abc.pdf"
    assert itens[0]["componentes"]["Subsídio"] == 34774.64 and itens[0]["componentes"]["descontos"] == 9492.39


def test_ler_pasta_do_portal():
    anos, meses = amostra("estadual_ms_portal")["anos"], amostra("estadual_ms_portal")["meses"]
    assert ms.ler_pasta(anos)[0][:2] == [("1202", "2020"), ("1302", "2021")]
    assert ms.ler_pasta(meses)[1][0] == ("Setembro", "https://www.transparencia.al.ms.gov.br/uploads/0971a140a253946b7edbb77d3bec3fd5.pdf")


def test_coletar_remuneracao_so_le_pdf_novo(monkeypatch, tmp_path):
    monkeypatch.setattr(ms, "PASTA", tmp_path)
    monkeypatch.setattr(ms, "PAUSA", 0)
    monkeypatch.setattr(ms, "ANO_INICIAL", 2026)
    monkeypatch.setattr(ms, "arquivos_da_folha", lambda s, ano: [{"ano": ano, "mes": 9, "id": "abc", "url": "https://x/uploads/abc.pdf"}])
    lidos = []
    monkeypatch.setattr(ms.comum, "baixar", lambda s, url, **kw: lidos.append(url) or b"")
    monkeypatch.setattr(ms, "texto_do_pdf", lambda conteudo: linhas_folha())
    hoje = ms.date(2026, 11, 2)
    ms.coletar_remuneracao(None, DEPUTADOS_PAUTA, hoje)
    dados = json.loads((tmp_path / "remuneracao_2026.json").read_text(encoding="utf-8"))
    assert dados["pdfs"] == {"abc": 9} and [i["idDeputado"] for i in dados["itens"]] == ["13"]
    ms.coletar_remuneracao(None, DEPUTADOS_PAUTA, hoje)
    assert lidos == ["https://x/uploads/abc.pdf"]


def test_contrato_so_com_documento_de_contrato():
    docs = [("01 - ETP - INEX 001-2026", "https://x/uploads/a.pdf"), ("03 - CONTRATO ADMINISTRATIVO Nº 004-2026", "https://x/uploads/b.pdf")]
    iid, item = ms.item_contrato("Inexigibilidade", 2026, "001", "5293", docs)
    assert iid.startswith("ctr_") and item["tipo"] == "contrato" and item["numero"] == "001/2026" and item["fornecedor"] is None and item["cnpj"] is None
    assert item["arquivos"][1]["url"] == "https://x/uploads/b.pdf" and item["fonte"].endswith("/gerdocumento/5293")
    assert ms.item_contrato("Inexigibilidade", 2026, "002", "5294", docs[:1] + [("MINUTA DE CONTRATO", "https://x/uploads/c.pdf")]) is None
    assert ms.item_contrato("Pregão", 2026, "001", "5307", docs[:1]) is None


def test_ata_de_sessao_e_ata_de_adesao():
    chave, ata = ms.item_ata("ATA ORDINÁRIA 19-08-2026", "https://x/uploads/44ae.pdf", 2026)
    assert chave == "atas|44ae" and ata["data"] == "2026-08-19" and ata["arquivos"][0]["url"] == "https://x/uploads/44ae.pdf"
    assert ms.item_ata("ATA ORDINÁRIA 19-08-2025", "https://x/uploads/44af.pdf", 2026)[1]["data"] is None
    iid, adesao = ms.item_ata_adesao(2026, "Atas de Adesão 2026", "https://x/uploads/022f.pdf", "5325")
    assert iid.startswith("ctr_") and adesao["tipo"] == "ata_adesao" and adesao["cnpj"] is None


def test_regras_da_verba_como_link(monkeypatch, tmp_path):
    monkeypatch.setattr(ms, "PASTA", tmp_path)
    monkeypatch.setattr(ms, "pasta_do_portal", lambda s, pasta: ([], [("ATO 52-2019 - MESA DIRETORA - CEAP", "https://x/uploads/ato.pdf")]))
    ms.coletar_regras(None)
    regra = json.loads((tmp_path / "regras_ressarcimento.json").read_text(encoding="utf-8"))
    assert regra["url"] == "https://x/uploads/ato.pdf" and [d["url"] for d in regra["documentos"]] == [ms.CEAP_PAGINA, "https://x/uploads/ato.pdf"]
