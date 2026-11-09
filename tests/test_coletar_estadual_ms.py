import io
import json
from datetime import date

import pytest

import coletar_estadual_ms as ms
import estaduais_comum as comum
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


HOJE = date(2026, 11, 3)


def fixar_hoje(monkeypatch, ano=2026, mes=11, dia=3):
    class Hoje(date):
        @classmethod
        def today(cls):
            return date(ano, mes, dia)

    monkeypatch.setattr(ms, "date", Hoje)


def avisos(capsys):
    return capsys.readouterr().err


CABECALHO_CEAP = "Deputado;Ano;Mes;Categoria;CPF/CNPJ;Fornecedor;Documento;Emissao;\"Valor (R$)\";Comprovante\n"


def csv_ceap(ano, linhas=True):
    texto = f"\"Portal\"\n\n{CABECALHO_CEAP}"
    if linhas:
        texto += f"\"DEP. HASHIOKA\";{ano};Janeiro;Software;16.551.514/0001-75;Provedor Ltda;BOL-1;10/01/{ano};\"R$ 99,90\";http://x/{ano}.pdf\n"
        texto += f"\"Dep. Fulano\";{ano};Janeiro;Software;;Outro Ltda;BOL-2;11/01/{ano};\"R$ 1,00\";\n"
    return texto


def test_decodificar():
    assert ms.decodificar("ação".encode("utf-8")) == "ação"
    assert ms.decodificar("ação".encode("cp1252")) == "ação"


def test_coletar_ceap_pula_ano_passado_gravado_e_avisa_sem_par(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(ms, "PASTA", tmp_path)
    monkeypatch.setattr(ms, "ANO_INICIAL", 2025)
    fixar_hoje(monkeypatch)
    (tmp_path / "verbas_2025.json").write_text('{"itens":[]}', encoding="utf-8")
    pedidos = []

    def baixar(s, url):
        pedidos.append(url)
        return csv_ceap(2026)

    monkeypatch.setattr(ms, "baixar", baixar)
    ms.coletar_ceap(None, DEPUTADOS)
    assert pedidos == [ms.CEAP_CSV.format(ano=2026)]
    gravado = json.loads((tmp_path / "verbas_2026.json").read_text(encoding="utf-8"))
    assert gravado["coletadoEm"] == "2026-11-03" and gravado["fonte"] == ms.CEAP_PAGINA and len(gravado["itens"]) == 1
    assert gravado["itens"][0]["idDeputado"] == "1" and gravado["itens"][0]["mes"] == 1 and gravado["itens"][0]["valor"] == 99.9
    assert gravado["itens"][0]["fonte"] == "http://x/2026.pdf"
    assert json.loads((tmp_path / "verbas_2025.json").read_text(encoding="utf-8")) == {"itens": []}
    assert "CEAP sem deputado eleito em 2022 (1): ['Fulano']" in avisos(capsys)


def test_coletar_ceap_ano_passado_sem_itens_nao_grava_e_atual_vazio_grava(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(ms, "PASTA", tmp_path)
    monkeypatch.setattr(ms, "ANO_INICIAL", 2025)
    fixar_hoje(monkeypatch)
    monkeypatch.setattr(ms, "baixar", lambda s, url: csv_ceap(0, linhas=False))
    ms.coletar_ceap(None, DEPUTADOS)
    assert not (tmp_path / "verbas_2025.json").exists()
    assert json.loads((tmp_path / "verbas_2026.json").read_text(encoding="utf-8"))["itens"] == []
    assert avisos(capsys) == ""


def test_coletar_ceap_erro_de_download_propaga_sem_gravar(monkeypatch, tmp_path):
    monkeypatch.setattr(ms, "PASTA", tmp_path)
    monkeypatch.setattr(ms, "ANO_INICIAL", 2026)
    fixar_hoje(monkeypatch)

    def baixar(s, url):
        raise comum.PrazoEsgotado("prazo de coleta esgotado")

    monkeypatch.setattr(ms, "baixar", baixar)
    with pytest.raises(comum.PrazoEsgotado):
        ms.coletar_ceap(None, DEPUTADOS)
    assert list(tmp_path.iterdir()) == []


def test_coletar_diarias_so_conta_e_avisa_quando_ha_dados(monkeypatch, capsys):
    fixar_hoje(monkeypatch)
    sem_despesa = "Mês;Ano;Informação\nJaneiro;{a};\"Não houve despesa\"\n"
    com_despesa = "Mês;Ano;Informação\nJaneiro;{a};Viagem a Brasília\nFevereiro;{a};Viagem a Corumbá\n"
    pedidos = []

    def baixar(s, url):
        pedidos.append(url)
        return (com_despesa if "ano=2026" in url else sem_despesa).format(a=2026)

    monkeypatch.setattr(ms, "baixar", baixar)
    ms.coletar_diarias(None)
    assert pedidos == [ms.DIARIAS_CSV.format(ano=2025), ms.DIARIAS_CSV.format(ano=2026)]
    saida = capsys.readouterr()
    assert "MS: diárias 2025: 0 lançamentos (portal: sem despesa)" in saida.out and "MS: diárias 2026: 2 lançamentos" in saida.out
    assert "diárias 2026 têm 2 linhas" in saida.err and "2025 têm" not in saida.err


def tabela_portal(monkeypatch, paginas):
    chamadas = []

    def pasta_do_portal(s, pasta):
        chamadas.append(str(pasta))
        valor = paginas[str(pasta)]
        if isinstance(valor, Exception):
            raise valor
        pastas, arquivos = valor
        return list(pastas), list(arquivos)

    monkeypatch.setattr(ms, "pasta_do_portal", pasta_do_portal)
    return chamadas


def test_pasta_do_ano_acha_ou_devolve_none(monkeypatch):
    tabela_portal(monkeypatch, {str(ms.ATAS_SESSAO): ([("1202", "2020"), ("1500", " 2026 ")], [])})
    assert ms.pasta_do_ano(None, ms.ATAS_SESSAO, 2026) == "1500"
    assert ms.pasta_do_ano(None, ms.ATAS_SESSAO, 2031) is None


def test_pdf_arquivo_e_id_do_pdf():
    assert ms.pdf_arquivo("Titulo", "https://x/uploads/abc.pdf") == {"nome": "Titulo", "url": "https://x/uploads/abc.pdf", "data": None}
    assert ms.id_do_pdf("https://x/uploads/abc.pdf") == "abc"


def test_ler_pasta_vazia_e_pdf_sem_celula_de_titulo():
    assert ms.ler_pasta("<html></html>") == ([], [])
    assert ms.ler_pasta("<tbody><tr><td><a href=\"https://x/uploads/a.pdf\">a</a></td></tr></tbody>") == ([], [])


def test_pdfs_sob_profundidade_e_pasta_vazia(monkeypatch):
    chamadas = tabela_portal(monkeypatch, {"raiz": ([("sub", "Sub")], [("A", "u/a.pdf")]), "sub": ([("fundo", "Fundo")], [("B", "u/b.pdf")]),
                                           "fundo": ([], [("C", "u/c.pdf")]), "vazia": ([], [])})
    assert ms.pdfs_sob(None, "raiz", 0) == [("A", "u/a.pdf")]
    assert chamadas == ["raiz"]
    assert ms.pdfs_sob(None, "raiz", 1) == [("A", "u/a.pdf"), ("B", "u/b.pdf")]
    assert ms.pdfs_sob(None, "raiz", 2) == [("A", "u/a.pdf"), ("B", "u/b.pdf"), ("C", "u/c.pdf")]
    assert ms.pdfs_sob(None, "vazia") == []


def test_arquivos_da_folha_ordena_por_mes_e_ignora_titulo_sem_mes(monkeypatch):
    tabela_portal(monkeypatch, {str(ms.REMUNERACAO): ([("1302", "2025"), ("1500", "2026")], []),
                                "1500": ([], [("Setembro", "https://x/uploads/b.pdf"), ("Janeiro", "https://x/uploads/z.pdf"),
                                              ("Janeiro", "https://x/uploads/a.pdf"), ("Resumo", "https://x/uploads/c.pdf")])})
    assert ms.arquivos_da_folha(None, 2026) == [
        {"ano": 2026, "mes": 1, "id": "a", "url": "https://x/uploads/a.pdf"}, {"ano": 2026, "mes": 1, "id": "z", "url": "https://x/uploads/z.pdf"},
        {"ano": 2026, "mes": 9, "id": "b", "url": "https://x/uploads/b.pdf"}]
    assert ms.arquivos_da_folha(None, 2031) == []


def test_texto_do_pdf_le_paginas_e_rejeita_arquivo_invalido():
    pypdf = pytest.importorskip("pypdf")
    escritor = pypdf.PdfWriter()
    escritor.add_blank_page(width=200, height=200)
    saida = io.BytesIO()
    escritor.write(saida)
    assert ms.texto_do_pdf(saida.getvalue()) == [""]
    with pytest.raises(Exception):
        ms.texto_do_pdf(b"isto nao e um pdf")


def test_autor_e_ementa_e_nomes_do_autor():
    assert ms.autor_e_ementa("Deputado X") == ("Deputado X", None)
    assert ms.autor_e_ementa("Deputado X - Dispõe sobre Y - Z") == ("Deputado X", "Dispõe sobre Y - Z")
    assert ms.nomes_do_autor("Deputadas Ana Souza e Bia Lima, Cida Reis") == ["Ana Souza", "Bia Lima", "Cida Reis"]
    assert ms.nomes_do_autor("PODER EXECUTIVO") == [] and ms.nomes_do_autor("Comissão de Saúde") == []


def test_ler_pagina_sem_linhas_e_linhas_da_pagina_vazia():
    assert ms.linhas_da_pagina("<html><body></body></html>") == []
    assert ms.ler_pagina("<html><body></body></html>") == []


def test_coletar_pautas_pagina_sem_projeto_levanta_e_nao_grava(monkeypatch, tmp_path):
    monkeypatch.setattr(ms, "PASTA", tmp_path)
    monkeypatch.setattr(ms, "baixar_html", lambda s, url: "<html></html>")
    with pytest.raises(RuntimeError, match="sem nenhum projeto lido"):
        ms.coletar_pautas(None, DEPUTADOS_PAUTA)
    assert list(tmp_path.iterdir()) == []


def test_coletar_pautas_falha_de_download_propaga(monkeypatch, tmp_path):
    monkeypatch.setattr(ms, "PASTA", tmp_path)

    def baixar_html(s, url):
        raise OSError("fora do ar")

    monkeypatch.setattr(ms, "baixar_html", baixar_html)
    with pytest.raises(OSError):
        ms.coletar_pautas(None, DEPUTADOS_PAUTA)


def configurar_atas(monkeypatch, tmp_path, paginas, anos):
    monkeypatch.setattr(ms, "PASTA", tmp_path)
    monkeypatch.setattr(ms, "ANO_INICIAL", 2024)
    monkeypatch.setattr(ms, "pasta_do_ano", lambda s, raiz, ano: anos.get(ano))
    return tabela_portal(monkeypatch, paginas)


def test_coletar_atas_pula_ano_encerrado_avisa_pasta_ausente_e_rele_so_recentes(monkeypatch, tmp_path, capsys):
    antigo = {"id": "x", "tipo": "pauta"}
    (tmp_path / "pautas_2024.json").write_text(json.dumps({"atasEm": "2025-01-01", "itens": {}}), encoding="utf-8")
    (tmp_path / "pautas_2026.json").write_text(json.dumps({"fonte": "f", "itens": {"k": antigo},
                                                           "atasMeses": {"2026-08": "2026-09-01", "2026-10": "2026-10-20"}}), encoding="utf-8")
    chamadas = configurar_atas(monkeypatch, tmp_path, {
        "P26": ([("m08", "Agosto"), ("m09", "Setembro"), ("m10", "Outubro"), ("doc", "Documentos")], []),
        "m09": ([], [("ATA ORDINARIA 15-09-2026", "https://x/uploads/aaa.pdf")]),
        "m10": ([], [("ATA ORDINARIA 07-10-2026", "https://x/uploads/bbb.pdf")])}, {2026: "P26"})
    ms.coletar_atas(None, HOJE)
    assert chamadas == ["P26", "m09", "m10"]
    gravado = json.loads((tmp_path / "pautas_2026.json").read_text(encoding="utf-8"))
    assert gravado["itens"]["k"] == antigo and gravado["itens"]["atas|aaa"]["data"] == "2026-09-15" and gravado["itens"]["atas|bbb"]["data"] == "2026-10-07"
    assert gravado["atasMeses"] == {"2026-08": "2026-09-01", "2026-09": "2026-11-03", "2026-10": "2026-11-03"}
    assert gravado["atasEm"] == "2026-11-03" and gravado["fonte"] == "f"
    assert json.loads((tmp_path / "pautas_2024.json").read_text(encoding="utf-8")) == {"atasEm": "2025-01-01", "itens": {}}
    assert "pasta de atas 2025 não achada" in avisos(capsys)


def test_coletar_atas_erro_no_meio_grava_o_que_leu_e_propaga(monkeypatch, tmp_path):
    configurar_atas(monkeypatch, tmp_path, {
        "P26": ([("m09", "Setembro"), ("m10", "Outubro")], []),
        "m09": ([], [("ATA 15-09-2026", "https://x/uploads/aaa.pdf")]),
        "m10": RuntimeError("portal caiu")}, {2026: "P26"})
    with pytest.raises(RuntimeError, match="portal caiu"):
        ms.coletar_atas(None, HOJE)
    gravado = json.loads((tmp_path / "pautas_2026.json").read_text(encoding="utf-8"))
    assert set(gravado["itens"]) == {"atas|aaa"} and list(gravado["atasMeses"]) == ["2026-09"]


def configurar_folha(monkeypatch, tmp_path, ano_inicial=2026):
    monkeypatch.setattr(ms, "PASTA", tmp_path)
    monkeypatch.setattr(ms, "PAUSA", 0)
    monkeypatch.setattr(ms, "ANO_INICIAL", ano_inicial)
    monkeypatch.setattr(ms, "texto_do_pdf", lambda conteudo: linhas_folha())
    lidos = []
    monkeypatch.setattr(ms.comum, "baixar", lambda s, url, **kw: lidos.append(url) or b"")
    return lidos


def test_coletar_remuneracao_ano_encerrado_nao_e_relido_e_sem_pdf_avisa(monkeypatch, tmp_path, capsys):
    configurar_folha(monkeypatch, tmp_path, 2024)
    (tmp_path / "remuneracao_2024.json").write_text("{}", encoding="utf-8")
    anos = []
    monkeypatch.setattr(ms, "arquivos_da_folha", lambda s, ano: anos.append(ano) or [])
    ms.coletar_remuneracao(None, DEPUTADOS_PAUTA, HOJE)
    assert anos == [2025, 2026]
    err = avisos(capsys)
    assert "remuneração 2025: nenhum PDF mensal" in err and "remuneração 2026: nenhum PDF mensal" in err
    assert sorted(p.name for p in tmp_path.iterdir()) == ["remuneracao_2024.json"]


def test_coletar_remuneracao_pdf_de_outro_mes_vira_falha_sem_dado(monkeypatch, tmp_path, capsys):
    lidos = configurar_folha(monkeypatch, tmp_path)
    monkeypatch.setattr(ms, "arquivos_da_folha", lambda s, ano: [{"ano": 2026, "mes": 8, "id": "abc", "url": "https://x/uploads/abc.pdf"}])
    ms.coletar_remuneracao(None, DEPUTADOS_PAUTA, HOJE)
    dados = json.loads((tmp_path / "remuneracao_2026.json").read_text(encoding="utf-8"))
    assert lidos == ["https://x/uploads/abc.pdf"] and dados["pdfs"] == {} and dados["itens"] == [] and dados["completaEm"] is None
    assert "PDF abc" in avisos(capsys)


def test_coletar_remuneracao_prazo_esgotado_grava_e_propaga(monkeypatch, tmp_path):
    configurar_folha(monkeypatch, tmp_path)
    monkeypatch.setattr(ms, "arquivos_da_folha", lambda s, ano: [{"ano": 2026, "mes": 9, "id": "abc", "url": "https://x/uploads/abc.pdf"}])

    def baixar(s, url, **kw):
        raise comum.PrazoEsgotado("prazo de coleta esgotado")

    monkeypatch.setattr(ms.comum, "baixar", baixar)
    with pytest.raises(comum.PrazoEsgotado):
        ms.coletar_remuneracao(None, DEPUTADOS_PAUTA, HOJE)
    dados = json.loads((tmp_path / "remuneracao_2026.json").read_text(encoding="utf-8"))
    assert dados["pdfs"] == {} and dados["completaEm"] is None


def test_coletar_remuneracao_rele_mes_recente_so_na_completa_velha(monkeypatch, tmp_path, capsys):
    lidos = configurar_folha(monkeypatch, tmp_path)
    monkeypatch.setattr(ms, "texto_do_pdf", lambda conteudo: [linha.replace("Setembro", "Outubro") for linha in linhas_folha()])
    monkeypatch.setattr(ms, "arquivos_da_folha", lambda s, ano: [{"ano": 2026, "mes": 10, "id": "abc", "url": "https://x/uploads/abc.pdf"}])
    guardado = {"coletadoEm": "2026-10-01", "completaEm": "2026-10-01", "pdfs": {"abc": 10}, "itens": [{"mes": 10, "idDeputado": "13", "pdf": "abc", "bruto": 1}]}
    (tmp_path / "remuneracao_2026.json").write_text(json.dumps(guardado), encoding="utf-8")
    ms.coletar_remuneracao(None, DEPUTADOS_PAUTA, HOJE)
    dados = json.loads((tmp_path / "remuneracao_2026.json").read_text(encoding="utf-8"))
    assert lidos == ["https://x/uploads/abc.pdf"] and dados["completaEm"] == "2026-11-03" and len(dados["itens"]) == 1
    assert dados["itens"][0]["bruto"] == 48200.46 and dados["itens"][0]["mes"] == 10
    assert "2 de 3 deputados do PDF ficaram de fora" in avisos(capsys)
    guardado["completaEm"] = "2026-11-01"
    (tmp_path / "remuneracao_2026.json").write_text(json.dumps(guardado), encoding="utf-8")
    ms.coletar_remuneracao(None, DEPUTADOS_PAUTA, HOJE)
    assert lidos == ["https://x/uploads/abc.pdf"]
    assert json.loads((tmp_path / "remuneracao_2026.json").read_text(encoding="utf-8")) == guardado


def configurar_orgao(monkeypatch, tmp_path, pdfs, pastas_ano):
    monkeypatch.setattr(ms, "PASTA", tmp_path)
    monkeypatch.setattr(ms, "ANO_INICIAL", 2024)
    monkeypatch.setattr(ms, "MODALIDADES", {"Dispensa": 1231, "Pregão": 1232})
    chamadas = {"ano": [], "pdfs": []}

    def pasta_do_ano(s, raiz, ano):
        chamadas["ano"].append((raiz, ano))
        return pastas_ano.get((raiz, ano))

    def pdfs_sob(s, pasta, profundidade=1):
        chamadas["pdfs"].append((pasta, profundidade))
        valor = pdfs[pasta]
        if isinstance(valor, Exception):
            raise valor
        return list(valor)

    monkeypatch.setattr(ms, "pasta_do_ano", pasta_do_ano)
    monkeypatch.setattr(ms, "pdfs_sob", pdfs_sob)
    return chamadas


PASTAS_ORGAO = {(1231, 2026): "A1", (ms.ATAS_ADESAO, 2026): "AD"}


def test_coletar_orgao_grava_contratos_e_atas_de_adesao_e_respeita_vistos(monkeypatch, tmp_path):
    (tmp_path / "orgao_2024.json").write_text('{"itens":{}}', encoding="utf-8")
    (tmp_path / "orgao_2026.json").write_text(json.dumps({"vistos": {"p3": "2026-11-02", "p4": "2026-09-01"}, "itens": {"velho": {"tipo": "contrato"}}}), encoding="utf-8")
    pdfs = {"p1": [("03 - CONTRATO Nº 1", "https://x/uploads/c1.pdf")], "p2": [("ETP", "https://x/uploads/e2.pdf")],
            "p4": [("CONTRATO Nº 4", "https://x/uploads/c4.pdf")], "AD": [("Ata de Adesão 1", "https://x/uploads/ad1.pdf")]}
    chamadas = configurar_orgao(monkeypatch, tmp_path, pdfs, PASTAS_ORGAO)
    tabela_portal(monkeypatch, {"A1": ([("p1", "001"), ("p2", "002"), ("p3", "003"), ("p4", "004")], [])})
    ms.coletar_orgao(None, HOJE)
    assert (ms.MODALIDADES["Dispensa"], 2024) not in chamadas["ano"] and (1231, 2025) in chamadas["ano"] and (1232, 2026) in chamadas["ano"]
    assert chamadas["pdfs"] == [("p1", 0), ("p2", 0), ("p4", 0), ("AD", 1)]
    gravado = json.loads((tmp_path / "orgao_2026.json").read_text(encoding="utf-8"))
    assert gravado["coletadoEm"] == "2026-11-03" and gravado["fonte"] == ms.PORTAL.format(52)
    assert gravado["vistos"] == {"p1": "2026-11-03", "p2": "2026-11-03", "p3": "2026-11-02", "p4": "2026-11-03"}
    tipos = sorted(i["tipo"] for i in gravado["itens"].values())
    assert tipos == ["ata_adesao", "contrato", "contrato", "contrato"]
    numeros = {i["numero"] for i in gravado["itens"].values() if i.get("modalidade") == "Dispensa"}
    assert numeros == {"001/2026", "004/2026"}
    assert not (tmp_path / "orgao_2025.json").exists()


def test_coletar_orgao_segunda_rodada_no_mesmo_dia_so_le_adesao(monkeypatch, tmp_path):
    pdfs = {"p1": [("CONTRATO Nº 1", "https://x/uploads/c1.pdf")], "AD": []}
    chamadas = configurar_orgao(monkeypatch, tmp_path, pdfs, PASTAS_ORGAO)
    tabela_portal(monkeypatch, {"A1": ([("p1", "001")], [])})
    ms.coletar_orgao(None, HOJE)
    chamadas["pdfs"].clear()
    ms.coletar_orgao(None, HOJE)
    assert chamadas["pdfs"] == [("AD", 1)]


def test_coletar_orgao_erro_no_meio_grava_o_lido_e_propaga(monkeypatch, tmp_path):
    pdfs = {"p1": [("CONTRATO Nº 1", "https://x/uploads/c1.pdf")], "p2": RuntimeError("pdf quebrado")}
    configurar_orgao(monkeypatch, tmp_path, pdfs, PASTAS_ORGAO)
    tabela_portal(monkeypatch, {"A1": ([("p1", "001"), ("p2", "002")], [])})
    with pytest.raises(RuntimeError, match="pdf quebrado"):
        ms.coletar_orgao(None, HOJE)
    gravado = json.loads((tmp_path / "orgao_2026.json").read_text(encoding="utf-8"))
    assert len(gravado["itens"]) == 1 and list(gravado["vistos"]) == ["p1"]


def test_coletar_regras_sem_ato_levanta_e_mantem_arquivo(monkeypatch, tmp_path):
    monkeypatch.setattr(ms, "PASTA", tmp_path)
    (tmp_path / "regras_ressarcimento.json").write_text('{"ano":1}', encoding="utf-8")
    tabela_portal(monkeypatch, {str(ms.REGRAS_PASTA): ([], [])})
    with pytest.raises(RuntimeError, match="nenhum ato da CEAP"):
        ms.coletar_regras(None)
    assert json.loads((tmp_path / "regras_ressarcimento.json").read_text(encoding="utf-8")) == {"ano": 1}


ETAPAS_MS = ["coletar_ceap", "coletar_diarias", "coletar_pautas", "coletar_atas", "coletar_remuneracao", "coletar_orgao", "coletar_regras"]


def test_coletar_sem_deputados_so_avisa(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(ms, "PASTA", tmp_path)
    monkeypatch.setattr(ms.comum, "sessao", lambda: "sessao")
    monkeypatch.setattr(ms, "deputados_do_tse", lambda: [])
    chamadas = []
    monkeypatch.setattr(ms, "coletar_ceap", lambda *a: chamadas.append("ceap"))
    ms.coletar()
    assert chamadas == [] and list(tmp_path.iterdir()) == []
    assert "sem eleitos de 2022" in avisos(capsys)


def test_coletar_grava_deputados_roda_etapas_na_ordem_e_isola_erro(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(ms, "PASTA", tmp_path)
    fixar_hoje(monkeypatch)
    monkeypatch.setattr(ms.comum, "sessao", lambda: "sessao")
    monkeypatch.setattr(ms, "deputados_do_tse", lambda: DEPUTADOS)
    chamadas = []
    for nome in ETAPAS_MS:
        def etapa(*args, nome=nome):
            chamadas.append((nome, args))
            if nome == "coletar_pautas":
                raise RuntimeError("pauta fora")

        monkeypatch.setattr(ms, nome, etapa)
    ms.coletar()
    assert [c[0] for c in chamadas] == ETAPAS_MS
    assert chamadas[0][1] == ("sessao", DEPUTADOS) and chamadas[1][1] == ("sessao",) and chamadas[3][1] == ("sessao", HOJE)
    assert chamadas[4][1] == ("sessao", DEPUTADOS, HOJE)
    gravado = json.loads((tmp_path / "deputados.json").read_text(encoding="utf-8"))
    assert gravado["legislatura"] == "2023-2027" and gravado["host"] is None and gravado["deputados"] == DEPUTADOS
    assert "MS: pautas: pauta fora" in avisos(capsys)
